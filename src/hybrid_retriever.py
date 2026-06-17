"""
Hibridno iskanje za pravne dokumente.
Kombinira semantično iskanje (Pinecone), BM25 keyword iskanje
in natančno ujemanje člankov za pravne poizvedbe.

Brez langchain odvisnosti — uporablja pinecone + rank_bm25 direktno.
"""
import re
import json
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class Document:
    """Preprost dokument za RAG pipeline (zamenjava za LangChain Document)."""
    page_content: str
    metadata: Dict = field(default_factory=dict)


class LegalHybridRetriever:
    """
    Hibridni retriever za pravne dokumente DS RS.

    Kombinira:
    1. Pinecone semantic search — razume pomen vprašanja
    2. BM25 keyword search — ujame točne reference na člene ("8. člen")
    3. Article-number matching — natančno pridobi specifične člene iz metadata
    4. Cross-reference expansion — avtomatsko pridobi sklicevane člene
    """

    # Vzorci za zaznavanje referenc na člene
    ARTICLE_REF_PATTERNS = [
        # "8. člen PoDS-1", "44. člen ZDSve", "24. členu Pravilnika"
        re.compile(r'(\d+)\.\s*člen[uaom]*\s+([A-ZČŠŽa-zčšž][\w-]+)', re.IGNORECASE),
        # "člen 8", "člen 44"
        re.compile(r'člen[uaom]*\s+(\d+)', re.IGNORECASE),
        # "8. člen" standalone
        re.compile(r'(\d+)\.\s*člen\b', re.IGNORECASE),
    ]

    # Mapiranje imen dokumentov na okrajšave
    DOC_NAME_MAP = {
        'pods': 'PoDS-1', 'poslovnik': 'PoDS-1', 'pods-1': 'PoDS-1',
        'zdsve': 'ZDSve', 'zakon o državnem svetu': 'ZDSve',
        'zjn': 'ZJN-3', 'javno naročanje': 'ZJN-3', 'zjn-3': 'ZJN-3',
        'zju': 'ZJU', 'javni uslužbenci': 'ZJU',
        'zstspjs': 'ZSTSPJS', 'plače': 'ZSTSPJS',
        'pravilnik o poslovnem': 'Pravilnik-delovni-cas',
        'pravilnik o delovnem': 'Pravilnik-delovni-cas',
        'pravilnik o finančnem': 'Pravilnik-financno',
    }

    def __init__(self, pinecone_index, openai_client, all_chunks: List[Dict],
                 namespace: str = "ds-rs", embedding_model: str = "text-embedding-3-small",
                 k: int = 15):
        """
        Args:
            pinecone_index: Pinecone Index objekt
            openai_client: OpenAI klient za embeddings
            all_chunks: Vsi chunk-i iz all_chunks.json
            namespace: Pinecone namespace
            embedding_model: Embedding model ime
            k: Število dokumentov za pridobitev
        """
        self.pinecone_index = pinecone_index
        self.openai_client = openai_client
        self.namespace = namespace
        self.embedding_model = embedding_model
        self.k = k
        self.all_chunks = all_chunks

        # Indeks chunk-ov po chunk_id za hitro iskanje
        self.chunk_index = {c["chunk_id"]: c for c in all_chunks}

        # Indeks po (dokument, člen) za natančno pridobivanje
        self.article_index = {}
        for chunk in all_chunks:
            meta = chunk["metadata"]
            doc_abbr = meta.get("document_abbreviation", "")
            art_num = meta.get("article_number", 0)
            if art_num > 0:
                key = (doc_abbr, art_num)
                if key not in self.article_index:
                    self.article_index[key] = []
                self.article_index[key].append(chunk)

        # BM25 retriever
        self._init_bm25()

    def _init_bm25(self):
        """Inicializira BM25 retriever z rank_bm25 paketom."""
        try:
            from rank_bm25 import BM25Okapi
            # Tokeniziraj vsebino chunk-ov
            self.bm25_corpus = [
                chunk["content"].lower().split()
                for chunk in self.all_chunks
            ]
            self.bm25 = BM25Okapi(self.bm25_corpus)
            self.bm25_available = True
        except ImportError:
            print("⚠️  rank_bm25 ni na voljo, uporabljam samo semantic search")
            self.bm25 = None
            self.bm25_available = False

    def _get_embedding(self, text: str) -> List[float]:
        """Pridobi embedding za besedilo."""
        response = self.openai_client.embeddings.create(
            input=[text],
            model=self.embedding_model
        )
        return response.data[0].embedding

    def _semantic_search(self, query: str, k: int = 15) -> List[Document]:
        """Izvede semantično iskanje v Pinecone."""
        query_embedding = self._get_embedding(query)
        results = self.pinecone_index.query(
            vector=query_embedding,
            top_k=k,
            namespace=self.namespace,
            include_metadata=True,
        )
        docs = []
        for match in results.get("matches", []):
            meta = match.get("metadata", {})
            text = meta.pop("text", "")
            docs.append(Document(page_content=text, metadata=meta))
        return docs

    def _bm25_search(self, query: str, k: int = 15) -> List[Document]:
        """Izvede BM25 keyword iskanje."""
        if not self.bm25_available:
            return []
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)
        # Pridobi top-k indekse
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        docs = []
        for idx in top_indices:
            if scores[idx] > 0:
                chunk = self.all_chunks[idx]
                docs.append(self._chunk_to_document(chunk))
        return docs

    def retrieve(self, query: str) -> List[Document]:
        """
        Glavna retrieval funkcija.

        1. Zaznaj reference na specifične člene
        2. Pridobi natančne člene (article matching)
        3. Semantic search (Pinecone)
        4. BM25 keyword search
        5. Cross-reference expansion
        6. Merge, deduplicate, rank
        """
        # 1. Zaznaj reference na člene
        article_refs = self._extract_article_references(query)

        # 2. Natančni členi iz article index
        exact_docs = []
        if article_refs:
            exact_docs = self._fetch_exact_articles(article_refs)

        # 3. Semantic search
        semantic_docs = []
        if self.pinecone_index:
            try:
                semantic_docs = self._semantic_search(query, k=self.k)
            except Exception as e:
                print(f"⚠️  Semantic search napaka: {e}")

        # 4. BM25 search
        bm25_docs = self._bm25_search(query, k=self.k)

        # 5. Cross-reference expansion
        cross_ref_docs = self._expand_cross_references(exact_docs + semantic_docs[:5])

        # 6. Merge in rank
        all_docs = self._merge_and_rank(exact_docs, semantic_docs, bm25_docs, cross_ref_docs)

        return all_docs[:self.k]

    def _extract_article_references(self, query: str) -> List[Dict]:
        """
        Zaznava referenc na specifične člene v vprašanju.
        Vrne: [{"article": 8, "doc_abbr": "PoDS-1"}, ...]
        """
        refs = []

        # Vzorec 1: "8. člen PoDS-1" ali "44. člen ZDSve"
        for match in self.ARTICLE_REF_PATTERNS[0].finditer(query):
            article = int(match.group(1))
            doc_hint = match.group(2).lower()
            doc_abbr = self._resolve_doc_name(doc_hint)
            refs.append({"article": article, "doc_abbr": doc_abbr})

        # Vzorec 2: "člen 8"
        for match in self.ARTICLE_REF_PATTERNS[1].finditer(query):
            article = int(match.group(1))
            refs.append({"article": article, "doc_abbr": None})

        # Vzorec 3: "8. člen" (brez dokumenta)
        if not refs:
            for match in self.ARTICLE_REF_PATTERNS[2].finditer(query):
                article = int(match.group(1))
                refs.append({"article": article, "doc_abbr": None})

        return refs

    def _resolve_doc_name(self, hint: str) -> Optional[str]:
        """Razreši namig imena dokumenta v okrajšavo."""
        hint_lower = hint.lower().strip()
        # Direktno ujemanje
        if hint_lower in self.DOC_NAME_MAP:
            return self.DOC_NAME_MAP[hint_lower]
        # Delno ujemanje
        for key, value in self.DOC_NAME_MAP.items():
            if key in hint_lower or hint_lower in key:
                return value
        return None

    def _fetch_exact_articles(self, refs: List[Dict]) -> List[Document]:
        """Pridobi natančne člene iz article index."""
        docs = []
        seen = set()

        for ref in refs:
            article = ref["article"]
            doc_abbr = ref.get("doc_abbr")

            if doc_abbr:
                # Natančno ujemanje: specifičen dokument + člen
                key = (doc_abbr, article)
                if key in self.article_index:
                    for chunk in self.article_index[key]:
                        if chunk["chunk_id"] not in seen:
                            docs.append(self._chunk_to_document(chunk))
                            seen.add(chunk["chunk_id"])
            else:
                # Člen brez dokumenta — poišči v vseh dokumentih
                for (d, a), chunks in self.article_index.items():
                    if a == article:
                        for chunk in chunks:
                            if chunk["chunk_id"] not in seen:
                                docs.append(self._chunk_to_document(chunk))
                                seen.add(chunk["chunk_id"])

        return docs

    def _expand_cross_references(self, docs: List[Document]) -> List[Document]:
        """Pridobi člene iz cross-referenc najdenih dokumentov."""
        cross_docs = []
        seen = set()

        for doc in docs:
            cross_refs_raw = doc.metadata.get("cross_references", [])
            # cross_references so lahko JSON string ali list
            if isinstance(cross_refs_raw, str):
                try:
                    cross_refs = json.loads(cross_refs_raw)
                except (json.JSONDecodeError, TypeError):
                    cross_refs = []
            else:
                cross_refs = cross_refs_raw

            for ref_str in cross_refs:
                # Parsaj cross-referenco: "8. člen PoDS-1"
                match = re.match(r'(\d+)\.\s*člen\s*(\S*)', ref_str)
                if match:
                    article = int(match.group(1))
                    doc_hint = match.group(2) if match.group(2) else None
                    doc_abbr = self._resolve_doc_name(doc_hint) if doc_hint else None

                    if doc_abbr:
                        key = (doc_abbr, article)
                        if key in self.article_index:
                            for chunk in self.article_index[key]:
                                if chunk["chunk_id"] not in seen:
                                    cross_docs.append(self._chunk_to_document(chunk))
                                    seen.add(chunk["chunk_id"])

        return cross_docs

    def _merge_and_rank(
        self,
        exact_docs: List[Document],
        semantic_docs: List[Document],
        bm25_docs: List[Document],
        cross_ref_docs: List[Document],
    ) -> List[Document]:
        """
        Združi in rangiraj rezultate z deduplikacijo.

        Prioriteta:
        1. Exact article matches (highest)
        2. Cross-reference expansions
        3. BM25 + Semantic (interleaved)
        """
        seen_content = set()
        ranked = []

        def add_unique(doc: Document, source: str):
            # Dedupliciramo po vsebini (prvi 200 znakov)
            content_key = doc.page_content[:200]
            if content_key not in seen_content:
                seen_content.add(content_key)
                doc.metadata["_retrieval_source"] = source
                ranked.append(doc)

        # 1. Exact matches
        for doc in exact_docs:
            add_unique(doc, "exact")

        # 2. Cross-references
        for doc in cross_ref_docs:
            add_unique(doc, "cross_ref")

        # 3. Interleave BM25 and semantic
        max_len = max(len(bm25_docs), len(semantic_docs))
        for i in range(max_len):
            if i < len(semantic_docs):
                add_unique(semantic_docs[i], "semantic")
            if i < len(bm25_docs):
                add_unique(bm25_docs[i], "bm25")

        return ranked

    def _chunk_to_document(self, chunk: Dict) -> Document:
        """Pretvori chunk dict v Document."""
        return Document(
            page_content=chunk["content"],
            metadata={**chunk["metadata"], "chunk_id": chunk["chunk_id"]}
        )

    def get_available_documents(self) -> str:
        """Vrne formatiran seznam dokumentov za system prompt."""
        doc_names = sorted(set(
            c["metadata"]["document_name"]
            for c in self.all_chunks
            if c["metadata"].get("document_name")
        ))
        return '\n'.join(f"- {name}" for name in doc_names)
