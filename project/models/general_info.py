class GeneralInfo:
    """General information data model"""

    def __init__(self, data=None):
        if data is None:
            data = {}

        self.id = data.get("id", "")
        self.url = data.get("url", "")
        self.title = data.get("title", "")
        self.content_sections = data.get("content_sections", [])
        self.links = data.get("links", [])
        self.files = data.get("files", [])
        self.page_type = data.get("page_type", [])
        self.parsed_on = data.get("parsed_on", "")

    def to_document(self):
        """Convert general info to document format for ChromaDB"""
        content = f"Title: {self.title}\n"

        for section in self.content_sections:
            content += f"Section: {section.get('section_id', '')}\n"
            content += f"{section.get('content', '')}\n\n"

        if self.links:
            content += "Links:\n"
            for link in self.links:
                content += f"- {link.get('text', '')}: {link.get('url', '')}\n"

        if self.page_type:
            content += f"Page Type: {', '.join(self.page_type)}\n"

        return content

    def to_metadata(self):
        """Convert general info to metadata for ChromaDB"""
        metadata = {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "parsed_on": self.parsed_on,
            "document_type": "general_info",
        }

        for page_type in self.page_type:
            metadata[f"type_{page_type}"] = True

        return metadata

    @classmethod
    def from_json(cls, json_data):
        """Create a GeneralInfo object from JSON data"""
        return cls(json_data)
