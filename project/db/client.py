import chromadb
from chromadb.config import Settings
from config.settings import DB_PATH

def get_client():
    """Initialize and return a ChromaDB client"""
    return chromadb.PersistentClient(
        DB_PATH, 
        settings=Settings(anonymized_telemetry=False)
    )