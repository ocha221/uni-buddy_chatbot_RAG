class News:
    """News data model"""
    
    def __init__(self, data=None):
        if data is None:
            data = {}
            
        self.id = data.get("id", "")
        self.url = data.get("url", "")
        self.title = data.get("title", "")
        self.date_published = data.get("date_published", "")
        self.content = data.get("content", "")
        self.links = data.get("links", [])
        self.files = data.get("files", [])
        self.news_type = data.get("news_type", "general")  # internship, thesis, etc.
        self.parsed_on = data.get("parsed_on", "")
        
    def to_document(self):
        """Convert news to document format for ChromaDB"""
        content = f"Title: {self.title}\n"
        content += f"Date: {self.date_published}\n"
        content += f"Content: {self.content}\n"
        
        if self.links:
            content += "Links:\n"
            for link in self.links:
                content += f"- {link.get('text', '')}: {link.get('url', '')}\n"
        
        return content
    
    def to_metadata(self):
        """Convert news to metadata for ChromaDB"""
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "date_published": self.date_published,
            "news_type": self.news_type,
            "parsed_on": self.parsed_on,
            "document_type": "news",
        }
    
    @classmethod
    def from_json(cls, json_data):
        """Create a News object from JSON data"""
        return cls(json_data)