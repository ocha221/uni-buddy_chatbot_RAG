from db.client import get_client
from db.embeddings import get_jina_embeddings


class Collections:
    """Manages ChromaDB collections"""

    def __init__(self):
        self.client = get_client()
        self.jina_embeddings = get_jina_embeddings()

    def get_course_collection(self):
        """Get or create the course collection"""
        return self.client.get_or_create_collection(
            name="courses",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.jina_embeddings,
        )

    def get_professor_collection(self):
        """Get or create the professor collection"""
        return self.client.get_or_create_collection(
            name="professor_courses", metadata={"hnsw:space": "cosine"}
        )

    def get_professor_names_collection(self):
        """Get or create the professor name mappings collection"""
        return self.client.get_or_create_collection(
            name="professor_name_mappings",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.jina_embeddings,
        )

    def get_news_collection(self):
        """Get or create the news collection"""
        return self.client.get_or_create_collection(
            name="news",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.jina_embeddings,
        )

    def reset_collections(
        self,
        reset_courses=True,
        reset_professors=True,
        reset_name_mappings=True,
        reset_news=True,
    ):
        """Reset specified collections by clearing their data (not deleting collections)"""
        if reset_courses:
            course_collection = self.get_course_collection()
            all_ids = course_collection.get()["ids"]
            if all_ids:
                course_collection.delete(ids=all_ids)

        if reset_professors:
            professor_collection = self.get_professor_collection()
            all_ids = professor_collection.get()["ids"]
            if all_ids:
                professor_collection.delete(ids=all_ids)

        if reset_name_mappings:
            name_collection = self.get_professor_names_collection()
            all_ids = name_collection.get()["ids"]
            if all_ids:
                name_collection.delete(ids=all_ids)

        if reset_news:
            news_collection = self.get_news_collection()
            all_ids = news_collection.get()["ids"]
            if all_ids:
                news_collection.delete(ids=all_ids)
