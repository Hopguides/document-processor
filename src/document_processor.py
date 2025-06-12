import os
import json
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone

class DocumentProcessor:
    """
    Sistem za obdelavo dokumentov v vektorsko bazo
    Implementira logiko: Text Splitter -> OpenAI Embeddings -> Pinecone Insert
    """
    
    def __init__(self, api_keys_file: str = "api_keys.json"):
        """Inicializacija z nalaganjem API ključev"""
        self.api_keys_file = api_keys_file
        self.api_keys = self._load_api_keys()
        self._setup_components()
    
    def _load_api_keys(self) -> Dict[str, str]:
        """Naloži API ključe iz JSON datoteke"""
        try:
            with open(self.api_keys_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"API ključi niso najdeni v {self.api_keys_file}")
        except json.JSONDecodeError:
            raise ValueError(f"Napaka pri branju API ključev iz {self.api_keys_file}")
    
    def _setup_components(self):
        """Nastavi komponente za obdelavo"""
        # Nastavi okoljske spremenljivke
        os.environ["OPENAI_API_KEY"] = self.api_keys["openai_api_key"]
        os.environ["PINECONE_API_KEY"] = self.api_keys["pinecone_api_key"]
        
        # Text Splitter z nastavitvami iz zahtev
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", " ", ""]
        )
        
        # OpenAI Embeddings z modelom text-embedding-3-small
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=self.api_keys["openai_api_key"]
        )
        
        # Pinecone inicializacija
        self.pc = Pinecone(api_key=self.api_keys["pinecone_api_key"])
        self.index_name = "klemenklon"
        
        # Preveri, ali indeks obstaja
        try:
            self.index = self.pc.Index(self.index_name)
            print(f"Povezan z obstoječim Pinecone indeksom: {self.index_name}")
        except Exception as e:
            print(f"Napaka pri povezovanju z indeksom {self.index_name}: {e}")
            raise
    
    def process_document(self, content: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Glavna funkcija za obdelavo dokumenta
        
        Args:
            content: Besedilo dokumenta za obdelavo
            metadata: Dodatni metapodatki za dokument
            
        Returns:
            Slovar z rezultati obdelave
        """
        if metadata is None:
            metadata = {}
        
        try:
            print("Začenjam obdelavo dokumenta...")
            
            # 1. Text Splitter - razdelitev dokumenta na manjše kose
            print("1. Razdeljevanje besedila na manjše kose...")
            chunks = self.text_splitter.split_text(content)
            print(f"   Ustvarjenih {len(chunks)} kosov besedila")
            
            # 2. Pripravi metapodatke za vsak kos
            print("2. Pripravljam metapodatke...")
            documents = []
            for i, chunk in enumerate(chunks):
                doc_metadata = {
                    "chunk_id": i,
                    "chunk_size": len(chunk),
                    "total_chunks": len(chunks),
                    **metadata
                }
                documents.append({
                    "page_content": chunk,
                    "metadata": doc_metadata
                })
            
            # 3. OpenAI Embeddings - ustvarjanje vdelavkov
            print("3. Ustvarjam embeddings z OpenAI...")
            texts = [doc["page_content"] for doc in documents]
            metadatas = [doc["metadata"] for doc in documents]
            
            # 4. Pinecone Insert - vstavljanje v vektorsko bazo
            print("4. Vstavljam v Pinecone vektorsko bazo...")
            vector_store = PineconeVectorStore.from_texts(
                texts=texts,
                embedding=self.embeddings,
                metadatas=metadatas,
                index_name=self.index_name
            )
            
            print("✅ Obdelava dokumenta uspešno končana!")
            
            return {
                "success": True,
                "chunks_processed": len(chunks),
                "total_characters": len(content),
                "average_chunk_size": len(content) // len(chunks) if chunks else 0,
                "index_name": self.index_name,
                "message": f"Dokument je bil uspešno obdelan in shranjen v {len(chunks)} kosih."
            }
            
        except Exception as e:
            error_msg = f"Napaka pri obdelavi dokumenta: {str(e)}"
            print(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "chunks_processed": 0
            }
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Pridobi statistike Pinecone indeksa"""
        try:
            stats = self.index.describe_index_stats()
            return {
                "success": True,
                "stats": stats
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

def main():
    """Testna funkcija"""
    # Primer uporabe
    processor = DocumentProcessor()
    
    # Testni dokument
    test_content = """
    To je testni dokument za preverjanje delovanja sistema za obdelavo dokumentov.
    
    Sistem implementira naslednje korake:
    1. Razdelitev dokumenta na manjše kose (Text Splitter)
    2. Ustvarjanje vdelavkov z OpenAI (Embeddings)
    3. Vstavljanje v Pinecone vektorsko bazo
    
    Ta testni dokument vsebuje več odstavkov, da lahko preverimo,
    kako sistem razdeluje besedilo na manjše kose in jih obdeluje.
    
    Vsak kos bo imel svojo identifikacijo in metapodatke,
    ki bodo omogočali kasnejše iskanje in pridobivanje informacij.
    """
    
    # Obdelaj testni dokument
    result = processor.process_document(
        content=test_content,
        metadata={"source": "test_document", "type": "test"}
    )
    
    print("\nRezultat obdelave:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # Pridobi statistike indeksa
    stats = processor.get_index_stats()
    print("\nStatistike indeksa:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()

