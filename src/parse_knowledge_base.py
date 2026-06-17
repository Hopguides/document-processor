#!/usr/bin/env python3
"""
Skripta za parsiranje vseh pravnih dokumentov DS RS v strukturirane JSON chunk-e.

Uporaba:
    python3 src/parse_knowledge_base.py

Prebere datoteke iz DS/ mape, jih parsira po členih,
in shrani v ds-rs-knowledge-base/parsed/all_chunks.json
"""
import json
import os
import sys

# Dodaj src/ v path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from legal_parser import SlovenianLegalParser, parse_mixed_md_file

# Poti
DS_DIR = "/Users/klemen_mac/Documents/PodiaWeb/DS"
OUTPUT_DIR = "/Users/klemen_mac/Documents/PodiaWeb/ai-institut/ds-rs-knowledge-base/parsed"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "all_chunks.json")

# Konfiguracija dokumentov z metapodatki
DOCUMENT_CONFIG = [
    {
        "filename_pattern": "POSL76_NPB5",
        "meta": {
            "document_name": "Poslovnik Državnega sveta (PoDS-1)",
            "document_abbreviation": "PoDS-1",
            "document_type": "poslovnik",
        }
    },
    {
        "filename_pattern": "Pravilnik_o_poslovnem_in_delovnem",
        "meta": {
            "document_name": "Pravilnik o poslovnem in delovnem času v službi DS RS",
            "document_abbreviation": "Pravilnik-delovni-cas",
            "document_type": "pravilnik",
        }
    },
    {
        "filename_pattern": "dodano-14-9-2025-QA",
        "meta": {
            "document_name": "Vprašanja in odgovori o DS RS",
            "document_abbreviation": "DS-QA",
            "document_type": "qa",
        }
    },
    {
        "filename_pattern": "ZJN3-javna_narocanja",
        "meta": {
            "document_name": "Zakon o javnem naročanju (ZJN-3)",
            "document_abbreviation": "ZJN-3",
            "document_type": "zakon",
        }
    },
    {
        "filename_pattern": "Povzetek_Zakona_o_javnem",
        "meta": {
            "document_name": "Povzetek Zakona o javnem naročanju",
            "document_abbreviation": "ZJN-povzetek",
            "document_type": "povzetek",
        }
    },
    {
        "filename_pattern": "zakon_o_javnih_usluzbencih",
        "meta": {
            "document_name": "Zakon o javnih uslužbencih (ZJU)",
            "document_abbreviation": "ZJU",
            "document_type": "zakon",
        }
    },
]


def find_file(directory: str, pattern: str) -> str | None:
    """Najde datoteko v direktoriju ki vsebuje pattern v imenu."""
    for fname in os.listdir(directory):
        if pattern in fname and not fname.startswith('.'):
            return os.path.join(directory, fname)
    return None


def main():
    parser = SlovenianLegalParser()
    all_chunks = []
    stats = []

    print("=" * 60)
    print("PARSIRANJE BAZE ZNANJA DRŽAVNEGA SVETA RS")
    print("=" * 60)

    # 1. Parsiraj mešano MD datoteko (drzavnisvet.md)
    md_file = os.path.join(DS_DIR, "drzavnisvet.md")
    if os.path.exists(md_file):
        print(f"\n📄 Parsiram: drzavnisvet.md (mešana datoteka)")
        md_chunks = parse_mixed_md_file(md_file, parser)
        all_chunks.extend(md_chunks)
        stats.append(("drzavnisvet.md", len(md_chunks)))
        print(f"   → {len(md_chunks)} chunk-ov")
    else:
        print(f"⚠️  drzavnisvet.md ne obstaja na {md_file}")

    # 2. Parsiraj vse konfigurirane dokumente
    for config in DOCUMENT_CONFIG:
        filepath = find_file(DS_DIR, config["filename_pattern"])
        if not filepath:
            print(f"\n⚠️  Ni najdeno: {config['filename_pattern']}")
            continue

        fname = os.path.basename(filepath)
        print(f"\n📄 Parsiram: {fname}")
        print(f"   Tip: {config['meta']['document_type']}")

        try:
            chunks = parser.parse_document(filepath, config["meta"])
            all_chunks.extend(chunks)
            stats.append((config["meta"]["document_abbreviation"], len(chunks)))
            print(f"   → {len(chunks)} chunk-ov")

            # Izpiši primere chunk-ov
            article_chunks = [c for c in chunks if c["metadata"].get("article_number", 0) > 0]
            if article_chunks:
                first = article_chunks[0]
                print(f"   Primer: {first['chunk_id']} ({len(first['content'])} znakov)")
        except Exception as e:
            print(f"   ❌ Napaka: {e}")
            stats.append((config["meta"]["document_abbreviation"], 0))

    # 3. Shrani rezultate
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    # 4. Izpiši statistiko
    print("\n" + "=" * 60)
    print("STATISTIKA")
    print("=" * 60)
    print(f"\nSkupaj chunk-ov: {len(all_chunks)}")
    print(f"Izhodna datoteka: {OUTPUT_FILE}")
    print(f"\nPo dokumentih:")
    for name, count in stats:
        print(f"  {name:40s} {count:>5d} chunk-ov")

    # Velikostna analiza
    sizes = [len(c["content"]) for c in all_chunks]
    if sizes:
        print(f"\nVelikost chunk-ov:")
        print(f"  Povprečje: {sum(sizes) // len(sizes)} znakov")
        print(f"  Min:       {min(sizes)} znakov")
        print(f"  Max:       {max(sizes)} znakov")
        print(f"  Nad 1500:  {sum(1 for s in sizes if s > 1500)} chunk-ov")

    # Seznam vseh dokumentov (za system prompt)
    doc_names = sorted(set(
        c["metadata"]["document_name"] for c in all_chunks
        if c["metadata"].get("document_name")
    ))
    print(f"\nDokumenti v bazi ({len(doc_names)}):")
    for name in doc_names:
        print(f"  - {name}")

    return all_chunks


if __name__ == "__main__":
    main()
