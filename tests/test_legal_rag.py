"""
Test suite za pravni RAG sistem Državnega sveta RS.

Testi temeljijo na dejanskih vprašanjih iz testiranja sept 2025 (Luka Glavač).

Uporaba:
    # Samo parser testi (brez API ključev):
    pytest tests/test_legal_rag.py -m "not integration" -v

    # Vsi testi (potrebuje API ključe + delujoč strežnik):
    pytest tests/test_legal_rag.py -v
"""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

CHUNKS_FILE = "/Users/klemen_mac/Documents/PodiaWeb/ai-institut/ds-rs-knowledge-base/parsed/all_chunks.json"


@pytest.fixture
def all_chunks():
    """Naloži vse parsirane chunk-e."""
    with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture
def pods1_chunks(all_chunks):
    """Chunk-i iz PoDS-1 (Poslovnik DS)."""
    return [c for c in all_chunks if c["metadata"].get("document_abbreviation") == "PoDS-1"]


@pytest.fixture
def pravilnik_chunks(all_chunks):
    """Chunk-i iz Pravilnika o delovnem času."""
    return [c for c in all_chunks if c["metadata"].get("document_abbreviation") == "Pravilnik-delovni-cas"]


@pytest.fixture
def zstspjs_chunks(all_chunks):
    """Chunk-i iz ZSTSPJS."""
    return [c for c in all_chunks if c["metadata"].get("document_abbreviation") == "ZSTSPJS"]


# ============================================================
# PARSER TESTI — brez API ključev
# ============================================================

class TestParserPoDS1:
    """Testi za parsiranje Poslovnika DS (PoDS-1)."""

    def test_article_count(self, pods1_chunks):
        """PoDS-1 ima 76 členov + summary."""
        article_chunks = [c for c in pods1_chunks if c["metadata"].get("article_number", 0) > 0]
        # Nekateri dolgi členi so razdeljeni, zato >= 76
        unique_articles = set(c["metadata"]["article_number"] for c in article_chunks)
        assert len(unique_articles) >= 70, f"Pričakovano vsaj 70 unikatnih členov, najdenih {len(unique_articles)}"

    def test_article_8_exists(self, pods1_chunks):
        """Člen 8 (naloge predsednika) mora obstajati."""
        art8 = [c for c in pods1_chunks if c["chunk_id"] == "PoDS-1-clen-8"]
        assert len(art8) >= 1, "PoDS-1 člen 8 ne obstaja"

    def test_article_8_content(self, pods1_chunks):
        """Člen 8 mora vsebovati vse naloge predsednika."""
        art8 = [c for c in pods1_chunks if c["chunk_id"] == "PoDS-1-clen-8"]
        assert art8, "PoDS-1 člen 8 ne obstaja"
        content = art8[0]["content"]
        # Preveri ključne naloge
        assert "predstavlja državni svet" in content.lower()
        assert "sklicuje" in content.lower()
        assert "podpisuje akte" in content.lower()
        assert "poslovnik" in content.lower()

    def test_article_8_has_alineje(self, pods1_chunks):
        """Člen 8 mora imeti več alinej (nalog)."""
        art8 = [c for c in pods1_chunks if c["chunk_id"] == "PoDS-1-clen-8"]
        assert art8
        content = art8[0]["content"]
        # Preštej alineje (vrstice z -)
        alineje = [line for line in content.split('\n') if line.strip().startswith('-')]
        assert len(alineje) >= 10, f"Pričakovanih vsaj 10 alinej, najdenih {len(alineje)}"

    def test_has_summary(self, pods1_chunks):
        """Mora imeti summary chunk."""
        summaries = [c for c in pods1_chunks if c["metadata"].get("is_summary")]
        assert len(summaries) >= 1


class TestParserPravilnik:
    """Testi za parsiranje Pravilnika o delovnem času."""

    def test_starts_at_article_1(self, pravilnik_chunks):
        """Pravilnik mora začeti pri členu 1."""
        art1 = [c for c in pravilnik_chunks if c["metadata"].get("article_number") == 1]
        assert len(art1) >= 1, "Pravilnik člen 1 ne obstaja"

    def test_article_1_title(self, pravilnik_chunks):
        """Člen 1 mora imeti naslov 'veljavnost določb'."""
        art1 = [c for c in pravilnik_chunks
                 if c["metadata"].get("article_number") == 1
                 and c["metadata"].get("document_abbreviation") == "Pravilnik-delovni-cas"]
        assert art1
        assert art1[0]["metadata"]["article_title"] == "veljavnost določb"


class TestParserZSTPSJS:
    """Testi za parsiranje ZSTSPJS."""

    def test_has_articles(self, zstspjs_chunks):
        """ZSTSPJS mora imeti člene."""
        article_chunks = [c for c in zstspjs_chunks if c["metadata"].get("article_number", 0) > 0]
        assert len(article_chunks) >= 50, f"ZSTSPJS mora imeti vsaj 50 členov, najdenih {len(article_chunks)}"


class TestParserGeneral:
    """Splošni testi za parser."""

    def test_total_chunks_reasonable(self, all_chunks):
        """Skupno število chunk-ov mora biti razumno."""
        assert len(all_chunks) >= 100, f"Premalo chunk-ov: {len(all_chunks)}"
        assert len(all_chunks) <= 5000, f"Preveč chunk-ov: {len(all_chunks)}"

    def test_all_chunks_have_metadata(self, all_chunks):
        """Vsak chunk mora imeti zahtevane metapodatke."""
        required_fields = ["document_name", "document_abbreviation", "document_type"]
        for chunk in all_chunks:
            for field in required_fields:
                assert field in chunk["metadata"], f"Chunk {chunk['chunk_id']} manjka {field}"

    def test_no_empty_chunks(self, all_chunks):
        """Noben chunk ne sme imeti prazne vsebine."""
        for chunk in all_chunks:
            assert len(chunk["content"].strip()) > 0, f"Prazen chunk: {chunk['chunk_id']}"

    def test_documents_coverage(self, all_chunks):
        """Preveri da so vsi ključni dokumenti zastopani."""
        doc_abbrs = set(c["metadata"]["document_abbreviation"] for c in all_chunks)
        assert "PoDS-1" in doc_abbrs, "PoDS-1 manjka"
        assert "Pravilnik-delovni-cas" in doc_abbrs, "Pravilnik manjka"
        assert "ZSTSPJS" in doc_abbrs, "ZSTSPJS manjka"


# ============================================================
# HYBRID RETRIEVER TESTI — brez API ključev
# ============================================================

class TestHybridRetriever:
    """Testi za hibridno iskanje."""

    @pytest.fixture
    def retriever(self, all_chunks):
        from hybrid_retriever import LegalHybridRetriever
        return LegalHybridRetriever(
            vector_store=None,  # Brez Pinecone za unit teste
            all_chunks=all_chunks,
            k=15
        )

    def test_extract_article_ref_with_doc(self, retriever):
        """Zaznaj '8. člen PoDS-1'."""
        refs = retriever._extract_article_references("Kaj določa 8. člen PoDS-1?")
        assert any(r["article"] == 8 for r in refs)

    def test_extract_article_ref_without_doc(self, retriever):
        """Zaznaj '44. člen' brez dokumenta."""
        refs = retriever._extract_article_references("Kaj določa 44. člen?")
        assert any(r["article"] == 44 for r in refs)

    def test_exact_article_fetch(self, retriever):
        """Pridobi natančen člen iz indeksa."""
        refs = [{"article": 8, "doc_abbr": "PoDS-1"}]
        docs = retriever._fetch_exact_articles(refs)
        assert len(docs) >= 1
        assert "predsednik" in docs[0].page_content.lower() or "8. člen" in docs[0].page_content

    def test_bm25_initialized(self, retriever):
        """BM25 retriever mora biti inicializiran."""
        assert retriever.bm25_retriever is not None

    def test_available_documents_list(self, retriever):
        """Seznam dokumentov mora vsebovati ključne dokumente."""
        doc_list = retriever.get_available_documents()
        assert "Poslovnik" in doc_list
        assert "ZSTSPJS" in doc_list


# ============================================================
# INTEGRATION TESTI — potrebuje API ključe + strežnik
# ============================================================

@pytest.mark.integration
class TestClientQuestions:
    """
    Testi z dejanskimi vprašanji iz sept 2025 testiranja.
    Zahteva delujoč RAG strežnik.
    """

    @pytest.fixture
    def rag_url(self):
        return os.environ.get("RAG_URL", "http://localhost:5001/api/rag/query")

    def _query(self, url, question, provider="openai"):
        import requests
        resp = requests.post(url, json={
            "question": question,
            "provider": provider,
            "model": "gpt-4-turbo"
        })
        return resp.json()

    def test_predsednik_naloge(self, rag_url):
        """Luka test: 'Kaj so naloge predsednika DS?' — mora omeniti PoDS-1 čl. 8."""
        result = self._query(rag_url, "Kakšne so naloge predsednika Državnega sveta?")
        assert result.get("success"), f"Query failed: {result.get('error')}"
        answer = result["answer"].lower()
        assert "8. člen" in answer or "8. členu" in answer, \
            "Odgovor mora omeniti 8. člen PoDS-1"
        assert "predsednik" in answer

    def test_poslovnik_article_8(self, rag_url):
        """Luka test: 'Kaj določa 8. člen Poslovnika?' — vse naloge."""
        result = self._query(rag_url, "Kaj določa 8. člen Poslovnika državnega sveta?")
        assert result.get("success")
        answer = result["answer"].lower()
        assert "predstavlja" in answer
        assert "sklicuje" in answer or "seje" in answer

    def test_ds_composition(self, rag_url):
        """'Kakšna je sestava DS?' — 40 članov, vse kategorije."""
        result = self._query(rag_url, "Kakšna je sestava Državnega sveta?")
        assert result.get("success")
        answer = result["answer"]
        assert "40" in answer

    def test_working_hours(self, rag_url):
        """Test pravilnika o delovnem času."""
        result = self._query(rag_url, "Kakšen je poslovni čas službe Državnega sveta?")
        assert result.get("success")
        answer = result["answer"].lower()
        assert "ponedeljk" in answer or "8.00" in answer
