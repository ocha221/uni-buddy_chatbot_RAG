# models/course.py
class Course:
    """Course data model"""

    def __init__(self, data=None):
        if data is None:
            data = {}

        self.course_code = data.get("course_code", "")
        self.title = data.get("title", "")
        self.year = data.get("year", 0)
        self.semester = data.get("semester", 0)
        self.hours = data.get("hours", 0)
        self.ects = data.get("ects", 0)
        self.instructors = data.get("instructors", [])
        self.learning_outcomes = data.get("learning_outcomes", "")
        self.course_content = data.get("course_content", "")

    def to_document(self):
        """Convert course to document format for ChromaDB"""
        content = f"Title: {self.title}\n"
        content += f"Course Code: {self.course_code}\n"
        content += f"Year: {self.year}, Semester: {self.semester}\n"
        content += f"Hours: {self.hours}, ECTS: {self.ects}\n"
        instructors_text = (
            ", ".join(self.instructors)
            if isinstance(self.instructors, list)
            else self.instructors
        )
        content += f"Instructors: {instructors_text}\n"
        content += f"Learning Outcomes: {self.learning_outcomes}\n"
        content += f"Course Content: {self.course_content}\n"

        return content

    def to_metadata(self):
        """Convert course to metadata for ChromaDB"""
        return {
            "course_code": self.course_code,
            "title": self.title,
            "year": int(self.year),
            "semester": int(self.semester),
            "ects": self.ects,
            "document_type": "course",
        }

    @classmethod
    def from_json(cls, json_data):
        """Create a Course object from JSON data"""
        return cls(json_data)
