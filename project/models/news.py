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
        self.news_types = data.get("news_types", [])
        self.date_epoch = data.get("date_epoch", 0)
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

        if self.news_types:
            type_mapping = {
                "student-related": "Φοιτητικά",
                "distinctions-awards": "Διακρίσεις",
                "internship-related": "Πρακτική Άσκηση",
                "events-activities": "Εκδηλώσεις-Δραστηριότητες",
                "vacancies": "Προκήρυξη Θέσεων",
            }
            greek_types = [type_mapping.get(t, t) for t in self.news_types]
            content += f"Categories: {', '.join(greek_types)}\n"

        return content

    def to_metadata(self):
        """Convert news to metadata for ChromaDB"""
        metadata = {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "date_published": self.date_published,
            "date_epoch": self.date_epoch,
            "parsed_on": self.parsed_on,
            "document_type": "news",
        }

        all_types = [
            "student-related",
            "distinctions-awards",
            "internship-related",
            "events-activities",
            "vacancies",
        ]

        for news_type in all_types:
            metadata[f"type_{news_type.replace('-', '_')}"] = (
                news_type in self.news_types
            )

        return metadata

    @classmethod
    def from_json(cls, json_data):
        """Create a News object from JSON data"""
        return cls(json_data)
