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
            name="demo_tests",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.jina_embeddings,
        )
    
    def get_professor_collection(self):
        """Get or create the professor collection"""
        return self.client.get_or_create_collection(
            name="professor_courses", 
            metadata={"hnsw:space": "cosine"}
        )
    
    def get_professor_names_collection(self):
        """Get or create the professor name mappings collection"""
        return self.client.get_or_create_collection(
            name="professor_name_mappings",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.jina_embeddings,
        )
        
    def reset_collections(self, reset_courses=True, reset_professors=True, reset_name_mappings=True):
        """Reset specified collections"""
        if reset_courses:
            self.client.delete_collection("demo_tests")
            self.get_course_collection()
            
        if reset_professors:
            self.client.delete_collection("professor_courses")
            self.get_professor_collection()
            
        if reset_name_mappings:
            self.client.delete_collection("professor_name_mappings")
            self.get_professor_names_collection()