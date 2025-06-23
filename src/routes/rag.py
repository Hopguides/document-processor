import os
import json
from typing import List, Dict, Optional, Tuple
from flask import Blueprint, request, jsonify
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_openai import ChatOpenAI
from langchain.schema import Document

# Uvoz za dodatne LLM ponudnike
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from langchain_anthropic import ChatAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

rag_bp = Blueprint('rag', __name__)

class ProjectBasedRAGSystem:
    def __init__(self):
        self.api_keys_file = os.path.join(os.path.dirname(__file__), '..', 'api_keys.json')
    
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
        if env_keys["openai_api_key"] and env_keys["pinecone_api_key"] and env_keys["pinecone_environment"]:
            print("Uporabljam API ključe iz okoljskih spremenljivk")
            return {k: v for k, v in env_keys.items() if v is not None}
        
        # Sicer preberi iz datoteke (za lokalni razvoj)
        try:
            with open(self.api_keys_file, 'r') as f:
                print("Uporabljam API ključe iz datoteke")
                file_keys = json.load(f)
                # Dodaj dodatne ključe iz okoljskih spremenljivk, če obstajajo
                for key, value in env_keys.items():
                    if value and key not in file_keys:
                        file_keys[key] = value
                return file_keys
        except FileNotFoundError:
            raise FileNotFoundError(f"API ključi niso najdeni v {self.api_keys_file} ali okoljskih spremenljivkah")
    
    def query(self, question: str, provider: str = "openai", model: str = None, project_id: int = None) -> Dict:
        """Izvede RAG poizvedbo"""
        try:
            # Naloži API ključe
            api_keys = self._load_api_keys()
            
            # Nastavi embeddings
            if not api_keys.get("openai_api_key"):
                raise ValueError("OpenAI API ključ je potreben za embeddings")
            
            embeddings = OpenAIEmbeddings(
                openai_api_key=api_keys["openai_api_key"],
                model="text-embedding-3-small"
            )
            
            # Nastavi Pinecone vector store
            if not api_keys.get("pinecone_api_key") or not api_keys.get("pinecone_environment"):
                raise ValueError("Pinecone API ključ in okolje sta potrebna")
            
            vector_store = PineconeVectorStore(
                index_name="klemenklon",  # Default indeks
                embedding=embeddings,
                pinecone_api_key=api_keys["pinecone_api_key"],
                environment=api_keys["pinecone_environment"]
            )
            
            # Poišči relevantne dokumente
            docs = vector_store.similarity_search(question, k=5)
            
            if not docs:
                return {
                    "answer": "Žal nisem našel relevantnih informacij v bazi znanja za vaše vprašanje.",
                    "sources": [],
                    "provider": provider,
                    "model": model
                }
            
            # Pripravi kontekst
            context = "\n\n".join([doc.page_content for doc in docs])
            
            # Ustvari prompt
            prompt = f"""Na podlagi naslednjega konteksta odgovori na vprašanje v slovenščini.

Kontekst:
{context}

Vprašanje: {question}

Odgovori na vprašanje na podlagi podanega konteksta. Če odgovora ni v kontekstu, to jasno povej.
"""
            
            # Ustvari LLM
            if provider == "openai":
                if not api_keys.get("openai_api_key"):
                    raise ValueError("OpenAI API ključ ni na voljo")
                llm = ChatOpenAI(
                    openai_api_key=api_keys["openai_api_key"],
                    model=model or "gpt-3.5-turbo",
                    temperature=0.1
                )
            elif provider == "gemini" and GEMINI_AVAILABLE:
                if not api_keys.get("google_api_key"):
                    raise ValueError("Google API ključ ni na voljo")
                llm = ChatGoogleGenerativeAI(
                    google_api_key=api_keys["google_api_key"],
                    model=model or "gemini-pro",
                    temperature=0.1
                )
            elif provider == "anthropic" and ANTHROPIC_AVAILABLE:
                if not api_keys.get("anthropic_api_key"):
                    raise ValueError("Anthropic API ključ ni na voljo")
                llm = ChatAnthropic(
                    anthropic_api_key=api_keys["anthropic_api_key"],
                    model=model or "claude-3-sonnet-20240229",
                    temperature=0.1
                )
            else:
                raise ValueError(f"Nepodprt ponudnik: {provider}")
            
            # Generiraj odgovor
            response = llm.invoke(prompt)
            
            # Pripravi vire
            sources = []
            for i, doc in enumerate(docs):
                sources.append({
                    "index": i + 1,
                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "metadata": doc.metadata
                })
            
            return {
                "answer": response.content,
                "sources": sources,
                "provider": provider,
                "model": model
            }
            
        except Exception as e:
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
        model = data.get('model', 'gpt-3.5-turbo')
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
        
        # OpenAI
        if api_keys.get("openai_api_key"):
            providers.append("openai")
        
        # Google Gemini
        if GEMINI_AVAILABLE and api_keys.get("google_api_key"):
            providers.append("gemini")
        
        # Anthropic Claude
        if ANTHROPIC_AVAILABLE and api_keys.get("anthropic_api_key"):
            providers.append("anthropic")
        
        provider_models = {
            "openai": ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"],
            "gemini": ["gemini-pro", "gemini-pro-vision"],
            "anthropic": ["claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
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
        # Preveri API ključe
        try:
            api_keys = rag_system._load_api_keys()
            has_openai = bool(api_keys.get("openai_api_key"))
            has_pinecone = bool(api_keys.get("pinecone_api_key") and api_keys.get("pinecone_environment"))
        except:
            has_openai = False
            has_pinecone = False
        
        return jsonify({
            "success": True,
            "api_keys": {
                "openai": has_openai,
                "pinecone": has_pinecone
            },
            "ready": has_openai and has_pinecone
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

