import os
import json
from typing import List, Dict, Optional, Tuple
from flask import Blueprint, request, jsonify
from openai import OpenAI
from pinecone import Pinecone as PineconeClient

# Uvoz hybrid retriever in system prompt
from src.hybrid_retriever import LegalHybridRetriever
from src.prompts.legal_system_prompt import LEGAL_SYSTEM_PROMPT

rag_bp = Blueprint('rag', __name__)

# Pot do parsiranih chunk-ov
LEGAL_KB_PATH = os.environ.get(
    'LEGAL_KB_PATH',
    '/Users/klemen_mac/Documents/PodiaWeb/ai-institut/ds-rs-knowledge-base/parsed/all_chunks.json'
)
# Tudi relativna pot znotraj projekta
LEGAL_KB_PATH_ALT = os.path.join(
    os.path.dirname(__file__), '..', '..', 'knowledge_base', 'all_chunks.json'
)


def _load_legal_chunks() -> List[Dict]:
    """Naloži parsirane pravne chunk-e."""
    for path in [LEGAL_KB_PATH, LEGAL_KB_PATH_ALT]:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            with open(abs_path, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            print(f"Naloženih {len(chunks)} pravnih chunk-ov iz {abs_path}")
            return chunks
    print("⚠️  Pravni chunk-i niso najdeni, hybrid retriever ne bo na voljo")
    return []


# Naloži chunk-e ob zagonu modula
_legal_chunks = _load_legal_chunks()


class ProjectBasedRAGSystem:
    def __init__(self):
        self.api_keys_file = os.path.join(os.path.dirname(__file__), '..', 'api_keys.json')
        self._hybrid_retriever = None

    def _load_api_keys(self) -> Dict[str, str]:
        """Naloži API ključe iz okoljskih spremenljivk ali datoteke"""
        # Najprej preveri okoljske spremenljivke (za Railway deployment)
        env_keys = {
            "openai_api_key": os.environ.get("OPENAI_API_KEY"),
            "pinecone_api_key": os.environ.get("PINECONE_API_KEY"),
            "pinecone_environment": os.environ.get("PINECONE_ENVIRONMENT"),
            "google_api_key": os.environ.get("GOOGLE_API_KEY"),
            "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY")
        }

        # Če so osnovni ključi v okoljskih spremenljivkah, jih uporabi
        if env_keys["openai_api_key"] and env_keys["pinecone_api_key"]:
            return {k: v for k, v in env_keys.items() if v is not None}

        # Sicer preberi iz datoteke (za lokalni razvoj)
        try:
            with open(self.api_keys_file, 'r') as f:
                file_keys = json.load(f)
                for key, value in env_keys.items():
                    if value and key not in file_keys:
                        file_keys[key] = value
                return file_keys
        except FileNotFoundError:
            raise FileNotFoundError(f"API ključi niso najdeni v {self.api_keys_file} ali okoljskih spremenljivkah")

    def _get_hybrid_retriever(self, api_keys: Dict) -> Optional[LegalHybridRetriever]:
        """Vrne ali inicializira hybrid retriever."""
        if self._hybrid_retriever is None and _legal_chunks:
            openai_client = OpenAI(api_key=api_keys["openai_api_key"])
            pc = PineconeClient(api_key=api_keys["pinecone_api_key"])
            index = pc.Index("klemenklon")
            self._hybrid_retriever = LegalHybridRetriever(
                pinecone_index=index,
                openai_client=openai_client,
                all_chunks=_legal_chunks,
                namespace="ds-rs",
                k=15
            )
        return self._hybrid_retriever

    def query(self, question: str, provider: str = "openai", model: str = None, project_id: int = None) -> Dict:
        """Izvede RAG poizvedbo z hibridnim iskanjem"""
        try:
            # Naloži API ključe
            api_keys = self._load_api_keys()

            # Hibridno iskanje (semantic + BM25 + article matching)
            hybrid = self._get_hybrid_retriever(api_keys)
            if hybrid:
                docs = hybrid.retrieve(question)
            else:
                # Fallback na navadno Pinecone iskanje
                openai_client = OpenAI(api_key=api_keys["openai_api_key"])
                pc = PineconeClient(api_key=api_keys["pinecone_api_key"])
                index = pc.Index("klemenklon")
                # Semantic search
                resp = openai_client.embeddings.create(
                    input=[question], model="text-embedding-3-small"
                )
                query_emb = resp.data[0].embedding
                results = index.query(
                    vector=query_emb, top_k=15, namespace="ds-rs",
                    include_metadata=True
                )
                from src.hybrid_retriever import Document
                docs = []
                for match in results.get("matches", []):
                    meta = match.get("metadata", {})
                    text = meta.pop("text", "")
                    docs.append(Document(page_content=text, metadata=meta))

            if not docs:
                return {
                    "answer": "Žal nisem našel relevantnih informacij v bazi znanja za vaše vprašanje.",
                    "sources": [],
                    "provider": provider,
                    "model": model
                }

            # Pripravi kontekst z izvorom za vsak chunk
            context_parts = []
            for doc in docs:
                meta = doc.metadata
                doc_name = meta.get('document_name', meta.get('document_abbreviation', 'Neznani dokument'))
                art_num = meta.get('article_number', 0)
                source_label = f"[{doc_name}"
                if art_num and art_num > 0:
                    source_label += f", {art_num}. člen"
                source_label += "]"
                context_parts.append(f"--- {source_label} ---\n{doc.page_content}")
            context = "\n\n".join(context_parts)

            # Seznam dokumentov v bazi za system prompt
            if hybrid:
                available_documents = hybrid.get_available_documents()
            else:
                available_documents = "Ni podatka o dokumentih v bazi."

            # Ustvari prompt z izboljšanim system promptom
            prompt = LEGAL_SYSTEM_PROMPT.format(
                available_documents=available_documents,
                context=context,
                question=question
            )

            # Ustvari LLM odgovor
            if provider == "openai":
                if not api_keys.get("openai_api_key"):
                    raise ValueError("OpenAI API ključ ni na voljo")
                client = OpenAI(api_key=api_keys["openai_api_key"])
                response = client.chat.completions.create(
                    model=model or "gpt-4-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                answer = response.choices[0].message.content

            elif provider == "gemini":
                if not api_keys.get("google_api_key"):
                    raise ValueError("Google API ključ ni na voljo")
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=api_keys["google_api_key"])
                    gemini = genai.GenerativeModel(model or "gemini-pro")
                    response = gemini.generate_content(prompt)
                    answer = response.text
                except ImportError:
                    raise ValueError("google-generativeai paket ni nameščen")

            elif provider == "anthropic":
                if not api_keys.get("anthropic_api_key"):
                    raise ValueError("Anthropic API ključ ni na voljo")
                try:
                    import anthropic
                    client = anthropic.Anthropic(api_key=api_keys["anthropic_api_key"])
                    response = client.messages.create(
                        model=model or "claude-sonnet-4-20250514",
                        max_tokens=4096,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1
                    )
                    answer = response.content[0].text
                except ImportError:
                    raise ValueError("anthropic paket ni nameščen")
            else:
                raise ValueError(f"Nepodprt ponudnik: {provider}")

            # Pripravi vire
            sources = []
            for i, doc in enumerate(docs):
                sources.append({
                    "index": i + 1,
                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "metadata": doc.metadata
                })

            return {
                "answer": answer,
                "sources": sources,
                "provider": provider,
                "model": model
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "error": str(e),
                "provider": provider,
                "model": model
            }

# Globalna instanca RAG sistema
rag_system = ProjectBasedRAGSystem()

# API endpoints
@rag_bp.route('/query', methods=['POST'])
def query_rag():
    """Izvede RAG poizvedbo"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        provider = data.get('provider', 'openai')
        model = data.get('model', 'gpt-4-turbo')
        project_id = data.get('project_id')

        if not question:
            return jsonify({
                "success": False,
                "error": "Vprašanje je obvezno"
            }), 400

        # Izvedi poizvedbo
        result = rag_system.query(question, provider, model, project_id)

        if "error" in result:
            return jsonify({
                "success": False,
                "error": result["error"]
            }), 500

        return jsonify({
            "success": True,
            "answer": result["answer"],
            "sources": result["sources"],
            "provider": result["provider"],
            "model": result["model"]
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@rag_bp.route('/providers', methods=['GET'])
def get_providers():
    """Vrne dostopne LLM ponudnike"""
    try:
        api_keys = rag_system._load_api_keys()
        providers = []

        if api_keys.get("openai_api_key"):
            providers.append("openai")
        if api_keys.get("google_api_key"):
            providers.append("gemini")
        if api_keys.get("anthropic_api_key"):
            providers.append("anthropic")

        provider_models = {
            "openai": ["gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"],
            "gemini": ["gemini-pro", "gemini-pro-vision"],
            "anthropic": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"]
        }

        available_providers = {}
        for provider in providers:
            available_providers[provider] = provider_models.get(provider, [])

        return jsonify({
            "success": True,
            "providers": available_providers
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@rag_bp.route('/health', methods=['GET'])
def check_health():
    """Preveri stanje RAG sistema"""
    try:
        try:
            api_keys = rag_system._load_api_keys()
            has_openai = bool(api_keys.get("openai_api_key"))
            has_pinecone = bool(api_keys.get("pinecone_api_key"))
        except:
            has_openai = False
            has_pinecone = False

        return jsonify({
            "success": True,
            "api_keys": {
                "openai": has_openai,
                "pinecone": has_pinecone
            },
            "legal_kb_loaded": len(_legal_chunks) > 0,
            "legal_kb_chunks": len(_legal_chunks),
            "ready": has_openai and has_pinecone
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
