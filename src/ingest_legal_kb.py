#!/usr/bin/env python3
"""
Ingestion skripta: naloži parsirane pravne chunk-e v Pinecone.

Uporaba:
    python3 src/ingest_legal_kb.py

Prebere all_chunks.json in vstavi vse chunk-e v Pinecone vektorsko bazo
z bogatimi metapodatki. Uporablja openai in pinecone SDK direktno
(brez langchain wrapper-jev za zanesljivost).
"""
import json
import os
import sys
import time
import hashlib

from openai import OpenAI
from pinecone import Pinecone

# Poti
CHUNKS_FILE = "/Users/klemen_mac/Documents/PodiaWeb/ai-institut/ds-rs-knowledge-base/parsed/all_chunks.json"
API_KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'api_keys.json')
INDEX_NAME = "klemenklon"
NAMESPACE = "ds-rs"  # Ločen namespace za DS dokumente
EMBEDDING_MODEL = "text-embedding-3-small"


def load_api_keys():
    """Naloži API ključe."""
    # Najprej okoljske spremenljivke
    openai_key = os.environ.get("OPENAI_API_KEY")
    pinecone_key = os.environ.get("PINECONE_API_KEY")

    if openai_key and pinecone_key:
        return {"openai_api_key": openai_key, "pinecone_api_key": pinecone_key}

    # Potem datoteka
    with open(API_KEYS_FILE, 'r') as f:
        return json.load(f)


MAX_CHARS = 20000  # ~5000-6000 tokenov, varno pod 8192 limit za slo tekst


def truncate_text(text, max_chars=MAX_CHARS):
    """Obreži predolgo besedilo za embedding model."""
    if len(text) <= max_chars:
        return text
    # Obreži na zadnjem prelomu vrstice pred limito
    truncated = text[:max_chars]
    last_newline = truncated.rfind('\n')
    if last_newline > max_chars * 0.8:
        truncated = truncated[:last_newline]
    return truncated + "\n[... besedilo skrajšano za embedding ...]"


def get_embeddings(client, texts, model=EMBEDDING_MODEL):
    """Pridobi embeddings za seznam besedil preko OpenAI API."""
    # Obreži predolga besedila
    safe_texts = [truncate_text(t) for t in texts]
    try:
        response = client.embeddings.create(
            input=safe_texts,
            model=model
        )
        return [item.embedding for item in response.data]
    except Exception as e:
        if "maximum context length" in str(e):
            # Obdelaj posamezno da najdemo problematičen tekst
            print(f"\n   ⚠ Batch presega limit, obdelujem posamezno...")
            embeddings = []
            for idx, text in enumerate(safe_texts):
                try:
                    resp = client.embeddings.create(input=[text], model=model)
                    embeddings.append(resp.data[0].embedding)
                except Exception as e2:
                    # Še bolj agresivno obreži
                    short = text[:10000]
                    print(f"   ⚠ Chunk {idx} ({len(text)} znakov) še vedno prevelik, obrežem na 10k")
                    resp = client.embeddings.create(input=[short], model=model)
                    embeddings.append(resp.data[0].embedding)
            return embeddings
        raise


def make_vector_id(chunk_id):
    """Ustvari stabilen Pinecone vector ID iz chunk_id."""
    return hashlib.md5(chunk_id.encode()).hexdigest()


def main():
    print("=" * 60)
    print("INGESTION PRAVNE BAZE ZNANJA V PINECONE")
    print("=" * 60)

    # 1. Naloži chunk-e
    print(f"\n1. Nalagam chunk-e iz {CHUNKS_FILE}...")
    with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    print(f"   Naloženih: {len(chunks)} chunk-ov")

    # 2. Naloži API ključe
    print("\n2. Nalagam API ključe...")
    api_keys = load_api_keys()
    print("   OK")

    # 3. Nastavi OpenAI klient
    print("\n3. Nastavljam OpenAI klient...")
    openai_client = OpenAI(api_key=api_keys["openai_api_key"])
    # Test embeddings
    test_emb = get_embeddings(openai_client, ["test"])
    print(f"   Embedding dimenzija: {len(test_emb[0])}")

    # 4. Poveži se s Pinecone
    print(f"\n4. Povezujem se s Pinecone indeksom '{INDEX_NAME}'...")
    pc = Pinecone(api_key=api_keys["pinecone_api_key"])
    index = pc.Index(INDEX_NAME)

    # Statistike pred ingestion
    stats_before = index.describe_index_stats()
    print(f"   Trenutni vektorji: {stats_before.get('total_vector_count', 'N/A')}")
    ns_stats = stats_before.get('namespaces', {})
    if NAMESPACE in ns_stats:
        print(f"   Obstoječi vektorji v '{NAMESPACE}': {ns_stats[NAMESPACE].get('vector_count', 0)}")

    # 5. Pripravi metadata
    print(f"\n5. Pripravljam {len(chunks)} chunk-ov...")
    records = []
    for chunk in chunks:
        # Pinecone metadata - serializiraj sezname kot stringe
        meta = {"text": chunk["content"]}  # Shrani besedilo v metadata za retrieval
        for key, value in chunk["metadata"].items():
            if isinstance(value, list):
                meta[key] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, bool):
                meta[key] = value
            else:
                meta[key] = value
        meta["chunk_id"] = chunk["chunk_id"]
        records.append({
            "id": make_vector_id(chunk["chunk_id"]),
            "content": chunk["content"],
            "metadata": meta,
        })

    # 6. Vstavi v Pinecone (v batch-ih po 50 — OpenAI embedding limit)
    start_from = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    print(f"\n6. Vstavljam v Pinecone (embedding + upsert)...")
    if start_from > 0:
        print(f"   Nadaljujem od chunk-a {start_from}...")
    batch_size = 50
    total_batches = (len(records) + batch_size - 1) // batch_size
    total_upserted = start_from

    for i in range(start_from, len(records), batch_size):
        batch_num = i // batch_size + 1
        batch = records[i:i + batch_size]

        print(f"   Batch {batch_num}/{total_batches}: {len(batch)} chunk-ov...", end=" ", flush=True)

        # Pridobi embeddings
        texts = [r["content"] for r in batch]
        embeddings = get_embeddings(openai_client, texts)

        # Pripravi vektorje za upsert
        vectors = []
        for rec, emb in zip(batch, embeddings):
            vectors.append({
                "id": rec["id"],
                "values": emb,
                "metadata": rec["metadata"],
            })

        # Upsert v Pinecone
        index.upsert(vectors=vectors, namespace=NAMESPACE)
        total_upserted += len(vectors)
        print(f"OK ({total_upserted}/{len(records)})")

        # Kratka pavza za rate limiting
        if batch_num < total_batches:
            time.sleep(0.5)

    # 7. Počakaj da se indeks posodobi
    print(f"\n7. Čakam na posodobitev indeksa...")
    time.sleep(5)

    # 8. Verificiraj
    print(f"\n8. Verifikacija...")
    stats_after = index.describe_index_stats()
    total_after = stats_after.get('total_vector_count', 0)
    ns_after = stats_after.get('namespaces', {}).get(NAMESPACE, {}).get('vector_count', 0)
    print(f"   Skupni vektorji: {total_after}")
    print(f"   Vektorji v '{NAMESPACE}': {ns_after}")

    # 9. Testna poizvedba
    print(f"\n9. Testna poizvedba: 'naloge predsednika državnega sveta'...")
    query_emb = get_embeddings(openai_client, ["naloge predsednika državnega sveta"])[0]
    results = index.query(
        vector=query_emb,
        top_k=3,
        namespace=NAMESPACE,
        include_metadata=True,
    )
    for i, match in enumerate(results.get('matches', []), 1):
        meta = match.get('metadata', {})
        score = match.get('score', 0)
        text_preview = meta.get('text', '')[:100]
        print(f"   {i}. [{meta.get('document_abbreviation', '?')}, "
              f"čl. {meta.get('article_number', '?')}] "
              f"(score: {score:.3f}) {text_preview}...")

    print(f"\n{'=' * 60}")
    print(f"INGESTION KONČAN! Vstavljeno {total_upserted} chunk-ov.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
