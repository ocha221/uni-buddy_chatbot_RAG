# models/professor.py
class Professor:
    """Professor data model"""
    
    def __init__(self, name, courses=None):
        self.name = name
        self.courses = courses or []
        
    def to_document(self):
        """Convert professor to document format for ChromaDB"""
        content = f"Professor: {self.name}\n"
        for course in self.courses:
            content += f"Teaches course: {course['code']} - {course['title']}\n"
        return content
    
    def to_metadata(self):
        """Convert professor to metadata for ChromaDB"""
        course_codes = ",".join([course["code"] for course in self.courses])
        return {
            "professor_name": self.name,
            "document_type": "professor",
            "course_codes": course_codes
        }
        
    def add_course(self, code, title):
        """Add a course taught by this professor"""
        # Check if course already exists
        for course in self.courses:
            if course["code"] == code:
                return
                
        self.courses.append({"code": code, "title": title})