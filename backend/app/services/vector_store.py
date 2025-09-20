import chromadb
from chromadb.utils import embedding_functions
from ..core.config import settings
import time
import logging

class VectorStore:
    def __init__(self):
        self.client = None
        self.collection = None
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

    def _ensure_initialized(self):
        """Initializes the ChromaDB client and collection if not already done, with retries."""
        if self.collection is not None:
            return

        logging.info("ChromaDB client not initialized. Attempting to connect...")
        attempts = 0
        while attempts < 5:
            try:
                # self.client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
                self.client = chromadb.PersistentClient(path="./chroma_data")
                self.client.heartbeat() # Check if the client is responsive
                self.collection = self.client.get_or_create_collection(
                    name="resume_collection",
                    embedding_function=self.embedding_function,
                    metadata={"hnsw:space": "cosine"}
                )
                logging.info("Successfully connected to ChromaDB and got collection.")
                return
            except Exception as e:
                attempts += 1
                logging.warning(f"ChromaDB connection attempt {attempts} failed: {e}. Retrying in 5s...")
                time.sleep(5)
        
        logging.error("Failed to connect to ChromaDB after several retries. Vector store will be unavailable.")

    def add_document(self, doc_id: str, document_text: str, metadata: dict):
        """Adds a document and its metadata to the Chroma collection."""
        self._ensure_initialized()
        if self.collection is None:
            logging.error("Cannot add document: Chroma collection is not available.")
            return
            
        try:
            self.collection.add(
                documents=[document_text],
                metadatas=[metadata],
                ids=[doc_id]
            )
        except Exception as e:
            logging.error(f"Error adding document to ChromaDB: {e}", exc_info=True)

    def search_similar(self, query_text: str, n_results: int = 5):
        """Searches for similar documents in the collection."""
        self._ensure_initialized()
        if self.collection is None:
            logging.error("Cannot search: Chroma collection is not available.")
            return None

        try:
            return self.collection.query(query_texts=[query_text], n_results=n_results)
        except Exception as e:
            logging.error(f"Error searching in ChromaDB: {e}", exc_info=True)
            return None

# Global instance to be imported by other modules
vector_store = VectorStore()