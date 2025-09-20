import chromadb
from chromadb.utils import embedding_functions
from ..core.config import settings

class VectorStore:
    def __init__(self):
        self.client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self.collection = self.client.get_or_create_collection(
            name="resume_collection",
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"}
        )

    def add_document(self, doc_id: str, document_text: str, metadata: dict):
        """Adds a document and its metadata to the Chroma collection."""
        try:
            self.collection.add(
                documents=[document_text],
                metadatas=[metadata],
                ids=[doc_id]
            )
        except Exception as e:
            print(f"Error adding document to ChromaDB: {e}")

    def search_similar(self, query_text: str, n_results: int = 5):
        """Searches for similar documents in the collection."""
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            return results
        except Exception as e:
            print(f"Error searching in ChromaDB: {e}")
            return None

vector_store = VectorStore()