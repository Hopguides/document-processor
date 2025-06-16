import os
import json
from typing import List, Dict, Optional, Tuple
from flask import Blueprint, request, jsonify
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_openai import ChatOpenAI
from langchain.schema import Document
from .gemini_key_manager import GeminiKeyManager

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

class MultiLLMRAGSystem:
    def __init__(self):
        self.api_keys_file = os.path.join(os.path.dirname(__file__), '..', 'api_keys.json')
        self.api_keys = self._load_api_keys()
        self.gemini_key_manager = GeminiKeyManager()
        self._setup_components()
    
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
    
    def _get_available_providers(self) -> List[str]:
        """Vrne seznam dostopnih LLM ponudnikov"""
        providers = []
        
        # OpenAI
        if self.api_keys.get("openai_api_key"):
            providers.append("openai")
        
        # Google Gemini - preveri ali imamo ključe v bazi ali okoljskih spremenljivkah
        if GEMINI_AVAILABLE and (self.api_keys.get("google_api_key") or self._has_gemini_keys()):
            providers.append("gemini")
        
        # Anthropic Claude
        if ANTHROPIC_AVAILABLE and self.api_keys.get("anthropic_api_key"):
            providers.append("anthropic")
        
        return providers
    
    def _has_gemini_keys(self) -> bool:
        """Preveri ali imamo dostopne Gemini ključe v bazi"""
        try:
            key = self.gemini_key_manager.get_next_available_key()
            return key is not None
        except:
            return False
    
    def _get_gemini_api_key(self) -> Optional[Tuple[str, int]]:
        """Pridobi naslednji dostopni Gemini API ključ z ID-jem"""
        # Najprej poskusi iz okoljskih spremenljivk
        env_key = self.api_keys.get("google_api_key")
        if env_key:
            return env_key, None  # None ID za okoljski ključ
        
        # Nato poskusi iz baze ključev
        try:
            key_data = self.gemini_key_manager.get_next_available_key()
            if key_data:
                return key_data['api_key'], key_data['id']
        except Exception as e:
            print(f"Napaka pri pridobivanju Gemini ključa: {e}")
        
        return None, None
    
    def _setup_components(self):
        """Nastavi komponente za RAG"""
        # Nastavi okoljske spremenljivke
        if self.api_keys.get("openai_api_key"):
            os.environ["OPENAI_API_KEY"] = self.api_keys["openai_api_key"]
        if self.api_keys.get("anthropic_api_key"):
            os.environ["ANTHROPIC_API_KEY"] = self.api_keys["anthropic_api_key"]
        
        # Za Gemini ne nastavljamo okoljske spremenljivke, ker uporabljamo rotacijo ključev
        
        # Nastavi Pinecone
        if self.api_keys.get("pinecone_api_key"):
            os.environ["PINECONE_API_KEY"] = self.api_keys["pinecone_api_key"]
        
        # Nastavi embeddings (vedno OpenAI za konsistentnost)
        self.embeddings = OpenAIEmbeddings()
        
        # Nastavi vector store
        self.vector_store = PineconeVectorStore(
            index_name="klemenklon",
            embedding=self.embeddings
        )
    
    def _get_llm(self, provider: str = "openai", model: str = None, gemini_key_id: int = None):
        """Vrne LLM glede na ponudnika z podporo za rotacijo Gemini ključev"""
        if provider == "openai":
            return ChatOpenAI(
                model=model or "gpt-3.5-turbo",
                temperature=0.1
            )
        elif provider == "gemini" and GEMINI_AVAILABLE:
            # Pridobi Gemini ključ
            api_key, key_id = self._get_gemini_api_key()
            if not api_key:
                raise ValueError("Ni dostopnih Gemini API ključev")
            
            # Nastavi začasno okoljsko spremenljivko za ta klic
            original_key = os.environ.get("GOOGLE_API_KEY")
            os.environ["GOOGLE_API_KEY"] = api_key
            
            try:
                llm = ChatGoogleGenerativeAI(
                    model=model or "gemini-pro",
                    temperature=0.1
                )
                # Shrani ID ključa za sledenje uporabe
                llm._gemini_key_id = key_id
                return llm
            finally:
                # Obnovi originalno okoljsko spremenljivko
                if original_key:
                    os.environ["GOOGLE_API_KEY"] = original_key
                elif "GOOGLE_API_KEY" in os.environ:
                    del os.environ["GOOGLE_API_KEY"]
                    
        elif provider == "anthropic" and ANTHROPIC_AVAILABLE:
            return ChatAnthropic(
                model=model or "claude-3-sonnet-20240229",
                temperature=0.1
            )
        else:
            raise ValueError(f"Nepodprt ponudnik: {provider}")
    
    def _update_gemini_key_usage(self, key_id: int, success: bool, error_type: str = None):
        """Posodobi statistike uporabe Gemini ključa"""
        if key_id is not None:  # Samo za ključe iz baze, ne za okoljske
            try:
                self.gemini_key_manager.update_key_usage(key_id, success, error_type)
            except Exception as e:
                print(f"Napaka pri posodabljanju statistik ključa {key_id}: {e}")
    
    def get_providers_and_models(self) -> Dict[str, List[str]]:
        """Vrne dostopne ponudnike in njihove modele"""
        providers = self._get_available_providers()
        
        models = {
            "openai": ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo-preview"],
            "gemini": ["gemini-pro", "gemini-pro-vision"],
            "anthropic": ["claude-3-sonnet-20240229", "claude-3-haiku-20240307"]
        }
        
        return {provider: models.get(provider, []) for provider in providers}
    
    def query(self, question: str, provider: str = "openai", model: str = None) -> Dict:
        """Izvede RAG poizvedbo z možnostjo izbire ponudnika"""
        try:
            # Poišči relevantne dokumente
            docs = self.vector_store.similarity_search(question, k=5)
            
            if not docs:
                return {
                    "success": False,
                    "error": "Ni najdenih relevantnih dokumentov"
                }
            
            # Pripravi kontekst
            context = "\n\n".join([doc.page_content for doc in docs])
            
            # Pripravi prompt
            prompt = f"""Na podlagi naslednjega konteksta odgovori na vprašanje v slovenščini.

Kontekst:
{context}

Vprašanje: {question}

Odgovor:"""
            
            # Pridobi LLM
            llm = self._get_llm(provider, model)
            gemini_key_id = getattr(llm, '_gemini_key_id', None)
            
            try:
                # Generiraj odgovor
                response = llm.invoke(prompt)
                answer = response.content if hasattr(response, 'content') else str(response)
                
                # Posodobi statistike za Gemini ključ
                if provider == "gemini" and gemini_key_id:
                    self._update_gemini_key_usage(gemini_key_id, success=True)
                
                # Pripravi vire
                sources = []
                for i, doc in enumerate(docs):
                    sources.append({
                        "index": i + 1,
                        "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                        "metadata": doc.metadata
                    })
                
                return {
                    "success": True,
                    "answer": answer,
                    "sources": sources,
                    "provider": provider,
                    "model": model or "default",
                    "gemini_key_id": gemini_key_id
                }
                
            except Exception as llm_error:
                # Obravnava napak LLM
                error_message = str(llm_error)
                
                # Posodobi statistike za Gemini ključ
                if provider == "gemini" and gemini_key_id:
                    if "rate limit" in error_message.lower() or "quota" in error_message.lower():
                        self._update_gemini_key_usage(gemini_key_id, success=False, error_type="rate_limit")
                    else:
                        self._update_gemini_key_usage(gemini_key_id, success=False, error_type="api_error")
                
                # Če je Gemini napaka in imamo več ključev, poskusi z naslednjim
                if provider == "gemini" and gemini_key_id and "rate limit" in error_message.lower():
                    try:
                        # Poskusi z naslednjim ključem
                        llm_retry = self._get_llm(provider, model)
                        retry_key_id = getattr(llm_retry, '_gemini_key_id', None)
                        
                        if retry_key_id != gemini_key_id:  # Drugačen ključ
                            response = llm_retry.invoke(prompt)
                            answer = response.content if hasattr(response, 'content') else str(response)
                            
                            self._update_gemini_key_usage(retry_key_id, success=True)
                            
                            sources = []
                            for i, doc in enumerate(docs):
                                sources.append({
                                    "index": i + 1,
                                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                                    "metadata": doc.metadata
                                })
                            
                            return {
                                "success": True,
                                "answer": answer,
                                "sources": sources,
                                "provider": provider,
                                "model": model or "default",
                                "gemini_key_id": retry_key_id,
                                "note": "Uporabljam rezervni ključ zaradi rate limita"
                            }
                    except:
                        pass  # Če retry ne uspe, vrni originalno napako
                
                raise llm_error
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

# Globalna instanca RAG sistema
rag_system = None

def get_rag_system():
    """Pridobi ali ustvari RAG sistem"""
    global rag_system
    if rag_system is None:
        try:
            rag_system = MultiLLMRAGSystem()
        except Exception as e:
            print(f"Napaka pri inicializaciji RAG sistema: {e}")
            return None
    return rag_system

@rag_bp.route('/providers', methods=['GET'])
def get_providers():
    """Vrne dostopne LLM ponudnike in modele"""
    try:
        system = get_rag_system()
        if not system:
            return jsonify({
                "success": False,
                "error": "RAG sistem ni inicializiran"
            }), 500
        
        providers_models = system.get_providers_and_models()
        
        return jsonify({
            "success": True,
            "providers": providers_models
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@rag_bp.route('/query', methods=['POST'])
def rag_query():
    """Izvede RAG poizvedbo"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        provider = data.get('provider', 'openai')
        model = data.get('model')
        
        if not question:
            return jsonify({
                "success": False,
                "error": "Vprašanje je obvezno"
            }), 400
        
        system = get_rag_system()
        if not system:
            return jsonify({
                "success": False,
                "error": "RAG sistem ni inicializiran"
            }), 500
        
        result = system.query(question, provider, model)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@rag_bp.route('/health', methods=['GET'])
def rag_health():
    """Preveri stanje RAG sistema"""
    try:
        system = get_rag_system()
        if not system:
            return jsonify({
                "success": False,
                "error": "RAG sistem ni inicializiran"
            }), 500
        
        providers = system._get_available_providers()
        
        # Preveri Gemini ključe
        gemini_stats = None
        if "gemini" in providers:
            try:
                gemini_stats = system.gemini_key_manager.get_statistics()
            except:
                pass
        
        return jsonify({
            "success": True,
            "status": "RAG sistem je operativen",
            "available_providers": providers,
            "gemini_keys_stats": gemini_stats
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

