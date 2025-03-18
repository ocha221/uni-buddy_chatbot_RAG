import logging
from models.prompt_map import PROMPT_MAP
from models.intent_mappings import IntentType, NEWS_INTENT_MAPPING
from langchain.schema import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """Formats responses for different query types"""

    def __init__(self, llm=None):
        self.llm = llm

    def format_professor_courses(self, professor_name, courses):
        """Format professor courses response"""
        if not courses:
            return f"I couldn't find any courses taught by Professor {professor_name}."

        courses_by_year_sem = {}
        for course in courses:
            key = (course.get("year", 0), course.get("semester", 0))
            if key not in courses_by_year_sem:
                courses_by_year_sem[key] = []
            courses_by_year_sem[key].append(course)

        response = f"Professor {professor_name} teaches {len(courses)} courses:\n\n"

        for (year, semester), year_courses in sorted(courses_by_year_sem.items()):
            if year > 0 and semester > 0:
                response += f"Year {year}, Semester {semester}:\n"

            for course in year_courses:
                response += f"• {course['title']} ({course['course_code']})"
                if course.get("ects"):
                    response += f", {course['ects']} ECTS"
                response += "\n"
            response += "\n"

        return response

    def _format_courses_for_data(self, courses_or_results):
        """Format course data consistently for response"""
        formatted_courses = []

        if isinstance(courses_or_results, dict) and "ids" in courses_or_results:
            results = courses_or_results
            for i in range(len(results["ids"][0])):
                formatted_courses.append(
                    {
                        "course_code": results["ids"][0][i],
                        "title": results["metadatas"][0][i].get("title", "Unknown"),
                        "year": results["metadatas"][0][i].get("year", 0),
                        "semester": results["metadatas"][0][i].get("semester", 0),
                        "ects": results["metadatas"][0][i].get("ects"),
                        "document": results["documents"][0][i],
                        "distance": (
                            results["distances"][0][i]
                            if "distances" in results
                            else 1.0
                        ),
                    }
                )

        elif isinstance(courses_or_results, list):
            for course in courses_or_results:
                formatted_courses.append(
                    {
                        "course_code": course["course_code"],
                        "title": course["metadata"].get("title", "Unknown"),
                        "year": course["metadata"].get("year", 0),
                        "semester": course["metadata"].get("semester", 0),
                        "ects": course["metadata"].get("ects"),
                        "document": course["document"],
                        "distance": 1.0,
                    }
                )

        return formatted_courses

    def _format_prompt_with_context(self, prompt, intent, context_data, query=None):
        """Format prompt with context data and clearly identify the user's query"""
        try:
            format_data = {}

            original_query_section = ""
            if query:
                original_query_section = f'\n\nOriginal user query: "{query}"'
                format_data["query"] = query

            if intent == IntentType.PROFESSOR_COURSES:
                format_data["professor_name"] = context_data.get(
                    "professor_name", "Unknown"
                )
                format_data["courses"] = self._format_courses_for_prompt(
                    context_data.get("courses", [])
                )

            elif intent in NEWS_INTENT_MAPPING:
                format_data["news_items"] = self._format_news_for_prompt(
                    context_data.get("news_items", [])
                )

            elif (
                intent == IntentType.COURSE_SEARCH
                or intent == IntentType.COURSE_FILTERING
            ):
                format_data["courses"] = self._format_courses_for_prompt(
                    context_data.get("courses", [])
                )

            formatted_prompt = prompt.format(**format_data)

            formatted_prompt += original_query_section

            return formatted_prompt

        except Exception as e:
            logger.error(f"Error formatting prompt: {str(e)}")
            return prompt

    def _format_courses_for_prompt(self, courses):
        """Format course data for inclusion in prompts"""
        if not courses:
            return "No courses found."

        formatted_text = ""
        for i, course in enumerate(courses, 1):
            formatted_text += f"Course {i}:\n"
            formatted_text += f"  - Code: {course.get('course_code', 'Unknown')}\n"
            formatted_text += f"  - Title: {course.get('title', 'Unknown')}\n"
            formatted_text += f"  - Year: {course.get('year', 'Unknown')}\n"
            formatted_text += f"  - Semester: {course.get('semester', 'Unknown')}\n"
            if course.get("ects"):
                formatted_text += f"  - ECTS: {course.get('ects')}\n"
            if course.get("document"):
                doc_preview = course.get("document", "")[:500]
                if len(course.get("document", "")) > 500:
                    doc_preview += "..."
                formatted_text += f"  - Description: {doc_preview}\n"
            formatted_text += "\n"

        return formatted_text

    def _format_news_for_prompt(self, news_items):
        """Format news data for inclusion in prompts"""
        if not news_items:
            return "No news items found."

        formatted_text = ""
        for i, item in enumerate(news_items, 1):
            formatted_text += f"News Item {i}:\n"
            formatted_text += (
                f"  - Title: {item.get('metadata', {}).get('title', 'Untitled')}\n"
            )
            if "date_published" in item.get("metadata", {}):
                formatted_text += f"  - Date: {item['metadata']['date_published']}\n"

            # full content
            formatted_text += f"  - Content: {item.get('content', '')}\n"

            # λιν
            if "links" in item.get("metadata", {}):
                formatted_text += "  - Links:\n"
                for link in item["metadata"]["links"]:
                    formatted_text += (
                        f"    - {link.get('text', '')}: {link.get('url', '')}\n"
                    )
            formatted_text += "\n"

        return formatted_text

    def _generate_fallback_response(self, intent, context_data):
        """Generate a fallback response when LLM is unavailable"""
        if intent == IntentType.PROFESSOR_COURSES:
            return self._generate_professor_courses_fallback(context_data)
        elif intent in NEWS_INTENT_MAPPING:
            return self._generate_news_fallback(intent, context_data)
        else:
            return "Here is the information I found. (Note: Enhanced formatting is currently unavailable.)"

    def _generate_professor_courses_fallback(self, context_data):
        """Generate a fallback response for professor courses"""
        professor_name = context_data.get("professor_name", "Unknown")
        courses = context_data.get("courses", [])

        if not courses:
            return f"I couldn't find any courses taught by Professor {professor_name}."

        # * Group courses by year and semester
        courses_by_year_sem = {}
        for course in courses:
            key = (course.get("year", 0), course.get("semester", 0))
            if key not in courses_by_year_sem:
                courses_by_year_sem[key] = []
            courses_by_year_sem[key].append(course)

        response = f"Professor {professor_name} teaches {len(courses)} courses:\n\n"

        for (year, semester), year_courses in sorted(courses_by_year_sem.items()):
            if year > 0 and semester > 0:
                response += f"Year {year}, Semester {semester}:\n"

            for course in year_courses:
                response += f"• {course['title']} ({course['course_code']})"
                if course.get("ects"):
                    response += f", {course['ects']} ECTS"
                response += "\n"
            response += "\n"

        return response

    def _generate_news_fallback(self, intent, context_data):
        """Generate a fallback response for news items"""
        news_items = context_data.get("news_items", [])

        if not news_items:
            return "I couldn't find any relevant news announcements."

        intent_titles = {
            IntentType.NEWS_INTERNSHIP: "internship announcements",
            IntentType.NEWS_THESIS: "thesis opportunities",
            IntentType.NEWS_STUDENT: "student-related announcements",
            IntentType.NEWS_DISTINCTIONS: "distinction and award announcements",
            IntentType.NEWS_EVENTS: "upcoming events",
            IntentType.NEWS_VACANCIES: "vacancy announcements",
            IntentType.NEWS_GENERAL: "news announcements",
        }

        title = intent_titles.get(intent, "announcements")
        response = f"Here are the latest {title}:\n\n"

        for i, item in enumerate(news_items[:5], 1):
            response += f"{i}. {item['metadata'].get('title', 'Announcement')}"
            if "date_published" in item["metadata"]:
                response += f" ({item['metadata']['date_published']})"
            response += "\n"
            content = item["content"]
            if len(content) > 150:
                content = content[:150] + "..."
            response += f"{content}\n\n"

        return response
