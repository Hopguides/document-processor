import os
import json
from typing import List, Dict, Any
from flask import Blueprint, request, jsonify
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from pinecone import Pinecone

# Dodamo podporo za Google Gemini
try:
    from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Dodamo podporo za Anthropic Claude
try:
    from langchain_anthropic import ChatAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

rag_bp = Blueprint('rag', __name__)

# Path to API keys
KEYS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'api_keys.json')

class MultiLLMRAGSystem:
    """
    RAG (Retrieval-Augmented Generation) sistem z podporo za več LLM ponudnikov
    """
    
    def __init__(self, api_keys_file: str = None):
        """Inicializacija RAG sistema"""
        if api_keys_file is None:
            api_keys_file = KEYS_FILE
        
        self.api_keys_file = api_keys_file
        self.api_keys = self._load_api_keys()
        self.available_providers = self._get_available_providers()
        self._setup_components()
    
    def _load_api_keys(self) -> Dict[str, str]:
        """Naloži API ključe iz okoljskih spremenljivk ali JSON datoteke"""
        # Najprej poskusi okoljske spremenljivke (za Railway deployment)
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
        
        # Google Gemini
        if GEMINI_AVAILABLE and self.api_keys.get("google_api_key"):
            providers.append("gemini")
        
        # Anthropic Claude
        if ANTHROPIC_AVAILABLE and self.api_keys.get("anthropic_api_key"):
            providers.append("anthropic")
        
        return providers
    
    def _setup_components(self):
        """Nastavi komponente za RAG"""
        # Nastavi okoljske spremenljivke
        if self.api_keys.get("openai_api_key"):
            os.environ["OPENAI_API_KEY"] = self.api_keys["openai_api_key"]
        if self.api_keys.get("google_api_key"):
            os.environ["GOOGLE_API_KEY"] = self.api_keys["google_api_key"]
        if self.api_keys.get("anthropic_api_key"):
            os.environ["ANTHROPIC_API_KEY"] = self.api_keys["anthropic_api_key"]
        
        # Nastavi Pinecone
        pc = Pinecone(api_key=self.api_keys["pinecone_api_key"])
        
        # Nastavi embeddings (vedno OpenAI za konsistentnost)
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=self.api_keys["openai_api_key"]
        )
        
        # Nastavi vector store
        self.vector_store = PineconeVectorStore(
            index_name="klemenklon",
            embedding=self.embeddings,
            pinecone_api_key=self.api_keys["pinecone_api_key"]
        )
        
        # Nastavi retriever
        self.retriever = self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 5}
        )
    
    def _get_llm(self, provider: str = "openai", model: str = None):
        """Vrne LLM glede na ponudnika"""
        if provider == "openai":
            model = model or "gpt-3.5-turbo"
            return ChatOpenAI(
                model=model,
                temperature=0.1,
                api_key=self.api_keys["openai_api_key"]
            )
        elif provider == "gemini" and GEMINI_AVAILABLE:
            model = model or "gemini-pro"
            return ChatGoogleGenerativeAI(
                model=model,
                temperature=0.1,
                google_api_key=self.api_keys["google_api_key"]
            )
        elif provider == "anthropic" and ANTHROPIC_AVAILABLE:
            model = model or "claude-3-sonnet-20240229"
            return ChatAnthropic(
                model=model,
                temperature=0.1,
                anthropic_api_key=self.api_keys["anthropic_api_key"]
            )
        else:
            raise ValueError(f"Nepodprt ponudnik: {provider}")
    
    def query(self, question: str, provider: str = "openai", model: str = None) -> Dict[str, Any]:
        """Izvede RAG poizvedbo"""
        try:
            # Preveri, ali je ponudnik dostopen
            if provider not in self.available_providers:
                raise ValueError(f"Ponudnik {provider} ni dostopen. Dostopni ponudniki: {self.available_providers}")
            
            # Pridobi LLM
            llm = self._get_llm(provider, model)
            
            # Nastavi prompt template
            prompt_template = """
            Uporabi naslednje kontekstne informacije za odgovor na vprašanje. 
            Če ne najdeš odgovora v kontekstu, povej, da ne veš odgovora.
            
            Kontekst:
            {context}
            
            Vprašanje: {question}
            
            Odgovor:
            """
            
            prompt = PromptTemplate(
                template=prompt_template,
                input_variables=["context", "question"]
            )
            
            # Ustvari RetrievalQA chain
            qa_chain = RetrievalQA.from_chain_type(
                llm=llm,
                chain_type="stuff",
                retriever=self.retriever,
                chain_type_kwargs={"prompt": prompt},
                return_source_documents=True
            )
            
            # Izvedi poizvedbo
            result = qa_chain.invoke({"query": question})
            
            # Pripravi odgovor
            sources = []
            for doc in result.get("source_documents", []):
                sources.append({
                    "content": doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content,
                    "metadata": doc.metadata
                })
            
            return {
                "success": True,
                "answer": result["result"],
                "sources": sources,
                "num_sources": len(sources),
                "provider": provider,
                "model": model or "default"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "provider": provider
            }
    
    def health_check(self) -> Dict[str, Any]:
        """Preveri stanje sistema"""
        try:
            # Preveri Pinecone povezavo
            pc = Pinecone(api_key=self.api_keys["pinecone_api_key"])
            index = pc.Index("klemenklon")
            stats = index.describe_index_stats()
            
            return {
                "status": "ok",
                "message": f"RAG sistem je pripravljen. Dostopni ponudniki: {', '.join(self.available_providers)}",
                "available_providers": self.available_providers,
                "pinecone_vectors": stats.total_vector_count if hasattr(stats, 'total_vector_count') else "N/A"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Napaka pri preverjanju stanja: {str(e)}",
                "available_providers": self.available_providers
            }

# Globalna instanca RAG sistema
rag_system = None

def get_rag_system():
    """Vrne globalno instanco RAG sistema"""
    global rag_system
    if rag_system is None:
        try:
            rag_system = MultiLLMRAGSystem()
        except Exception as e:
            print(f"Napaka pri inicializaciji RAG sistema: {e}")
            return None
    return rag_system

@rag_bp.route('/health', methods=['GET'])
def health():
    """Preveri stanje RAG sistema"""
    system = get_rag_system()
    if system is None:
        return jsonify({
            "status": "error",
            "message": "API ključi niso nastavljeni"
        }), 500
    
    result = system.health_check()
    status_code = 200 if result["status"] == "ok" else 500
    return jsonify(result), status_code

@rag_bp.route('/providers', methods=['GET'])
def get_providers():
    """Vrne seznam dostopnih LLM ponudnikov"""
    system = get_rag_system()
    if system is None:
        return jsonify({
            "success": False,
            "error": "API ključi niso nastavljeni",
            "providers": []
        }), 500
    
    return jsonify({
        "success": True,
        "providers": system.available_providers,
        "provider_info": {
            "openai": {"models": ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]},
            "gemini": {"models": ["gemini-pro", "gemini-pro-vision"]},
            "anthropic": {"models": ["claude-3-sonnet-20240229", "claude-3-haiku-20240307"]}
        }
    })

@rag_bp.route('/query', methods=['POST'])
def query():
    """Izvede RAG poizvedbo"""
    system = get_rag_system()
    if system is None:
        return jsonify({
            "success": False,
            "error": "API ključi niso nastavljeni"
        }), 500
    
    data = request.get_json()
    question = data.get('question', '').strip()
    provider = data.get('provider', 'openai')
    model = data.get('model')
    
    if not question:
        return jsonify({
            "success": False,
            "error": "Vprašanje je obvezno"
        }), 400
    
    result = system.query(question, provider, model)
    status_code = 200 if result["success"] else 500
    return jsonify(result), status_code

