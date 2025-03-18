import chromadb.utils.embedding_functions as embedding_functions
from config.settings import JINA_API_KEY, JINA_MODEL


def get_jina_embeddings():
    """Return Jina embedding function"""
    return embedding_functions.JinaEmbeddingFunction(
        api_key=JINA_API_KEY,
        model_name=JINA_MODEL,
    )
