import os
import json
from typing import List, Dict, Any
from flask import Blueprint, request, jsonify
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from pinecone import Pinecone

rag_bp = Blueprint('rag', __name__)

# Path to API keys
KEYS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'api_keys.json')

class RAGSystem:
    """
    RAG (Retrieval-Augmented Generation) sistem za poizvedbe
    """
    
    def __init__(self, api_keys_file: str = None):
        """Inicializacija RAG sistema"""
        if api_keys_file is None:
            api_keys_file = KEYS_FILE
        
        self.api_keys_file = api_keys_file
        self.api_keys = self._load_api_keys()
        self._setup_components()
    
    def _load_api_keys(self) -> Dict[str, str]:
        """Naloži API ključe iz okoljskih spremenljivk ali JSON datoteke"""
        # Najprej poskusi okoljske spremenljivke (za Railway deployment)
        env_keys = {
            "openai_api_key": os.environ.get("OPENAI_API_KEY"),
            "pinecone_api_key": os.environ.get("PINECONE_API_KEY"),
            "pinecone_environment": os.environ.get("PINECONE_ENVIRONMENT")
        }
        
        # Če so vsi ključi v okoljskih spremenljivkah, jih uporabi
        if all(env_keys.values()):
            print("Uporabljam API ključe iz okoljskih spremenljivk")
            return env_keys
        
        # Sicer preberi iz datoteke (za lokalni razvoj)
        try:
            with open(self.api_keys_file, 'r') as f:
                print("Uporabljam API ključe iz datoteke")
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"API ključi niso najdeni v {self.api_keys_file} ali okoljskih spremenljivkah")
    
    def _setup_components(self):
        """Nastavi komponente za RAG"""
        # Nastavi okoljske spremenljivke
        os.environ["OPENAI_API_KEY"] = self.api_keys["openai_api_key"]
        os.environ["PINECONE_API_KEY"] = self.api_keys["pinecone_api_key"]
        
        # OpenAI Embeddings
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=self.api_keys["openai_api_key"]
        )
        
        # OpenAI Chat model
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0.7,
            openai_api_key=self.api_keys["openai_api_key"]
        )
        
        # Pinecone inicializacija
        self.pc = Pinecone(api_key=self.api_keys["pinecone_api_key"])
        self.index_name = "klemenklon"
        
        # Pinecone Vector Store
        self.vector_store = PineconeVectorStore(
            index_name=self.index_name,
            embedding=self.embeddings
        )
        
        # Retriever
        self.retriever = self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 5}  # Vrni 5 najbolj podobnih dokumentov
        )
        
        # Custom prompt template
        self.prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""Uporabi naslednji kontekst za odgovor na vprašanje. Če odgovora ne najdeš v kontekstu, povej, da ne veš odgovora.

Kontekst:
{context}

Vprašanje: {question}

Odgovor:"""
        )
        
        # RetrievalQA chain
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.retriever,
            chain_type_kwargs={"prompt": self.prompt_template},
            return_source_documents=True
        )
    
    def query(self, question: str) -> Dict[str, Any]:
        """
        Izvedi RAG poizvedbo
        
        Args:
            question: Vprašanje uporabnika
            
        Returns:
            Slovar z odgovorom in metapodatki
        """
        try:
            print(f"Izvajam RAG poizvedbo: {question}")
            
            # Izvedi poizvedbo
            result = self.qa_chain.invoke({"query": question})
            
            # Pripravi odgovor
            answer = result["result"]
            source_docs = result["source_documents"]
            
            # Pripravi metapodatke virov
            sources = []
            for i, doc in enumerate(source_docs):
                sources.append({
                    "chunk_id": i + 1,
                    "content": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                    "metadata": doc.metadata
                })
            
            return {
                "success": True,
                "question": question,
                "answer": answer,
                "sources": sources,
                "num_sources": len(sources)
            }
            
        except Exception as e:
            error_msg = f"Napaka pri RAG poizvedbi: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "question": question
            }

@rag_bp.route('/query', methods=['POST'])
def rag_query():
    """RAG poizvedba endpoint"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({'error': 'Vprašanje je obvezno'}), 400
        
        # Inicializiraj RAG sistem
        rag_system = RAGSystem()
        
        # Izvedi poizvedbo
        result = rag_system.query(question)
        
        return jsonify(result), 200 if result.get('success') else 500
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@rag_bp.route('/health', methods=['GET'])
def rag_health():
    """Preveri zdravje RAG sistema"""
    try:
        # Preveri, ali so API ključi na voljo
        if not os.path.exists(KEYS_FILE):
            return jsonify({
                'status': 'error',
                'message': 'API ključi niso nastavljeni'
            }), 400
        
        with open(KEYS_FILE, 'r') as f:
            keys = json.load(f)
        
        required_keys = ['openai_api_key', 'pinecone_api_key', 'pinecone_environment']
        missing_keys = [key for key in required_keys if not keys.get(key)]
        
        if missing_keys:
            return jsonify({
                'status': 'error',
                'message': f'Manjkajo API ključi: {", ".join(missing_keys)}'
            }), 400
        
        return jsonify({
            'status': 'ok',
            'message': 'RAG sistem je pripravljen',
            'index_name': 'klemenklon'
        }), 200
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

