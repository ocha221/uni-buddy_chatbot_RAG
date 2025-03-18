import logging
import json
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field
from config.settings import SIMILARITY_THRESHOLD

logger = logging.getLogger(__name__)


class SearchCourses(BaseModel):
    """Search for courses by query text"""

    query: str = Field(..., description="The search query for finding courses")
    limit: int = Field(10, description="Maximum number of results to return")


class FilterCourses(BaseModel):
    """Filter courses by year, semester, or other criteria"""

    year: Optional[int] = Field(
        None, description="The academic year (e.g., 1, 2, 3, 4)"
    )
    semester: Optional[int] = Field(None, description="The semester (e.g., 1, 2)")
    limit: int = Field(10, description="Maximum number of results to return")


class SearchNews(BaseModel):
    """Search for university news and announcements"""

    query: str = Field(..., description="The search query for finding news")
    category: Optional[str] = Field(
        None,
        description="News category (internship, thesis, student, distinctions, events, vacancies, general)",
    )
    limit: int = Field(10, description="Maximum number of results to return")


class GetRecentNews(BaseModel):
    """Get recent university news by category"""

    category: str = Field(
        ...,
        description="News category (internship, thesis, student, distinctions, events, vacancies, general)",
    )
    limit: int = Field(5, description="Maximum number of results to return")


class GetProfessorCourses(BaseModel):
    """Get courses taught by a professor"""

    professor_name: str = Field(..., description="Name of the professor to search for")


def get_professor_courses(
    self, professor_service, name_service, professor_name: str
) -> Dict:
    """Get courses taught by a professor"""

    if not professor_name:

        return {"error": "Missing required services or invalid professor name"}

    if not professor_service:

        return {"error": "Missing required services or invalid professor name"}

    if not name_service:

        return {"error": "Missing required services or invalid professor name"}

    try:

        canonical_name, confidence = (
            self.name_service.find_canonical_name_with_confidence(professor_name)
        )

        confidence = float(confidence) if confidence is not None else 0.0

        if canonical_name and confidence < SIMILARITY_THRESHOLD:

            return {
                "clarification_needed": True,
                "candidate_match": canonical_name,
                "original_name": professor_name,
                "confidence": confidence,
            }

        if canonical_name:

            professor_name = canonical_name

        courses = self.professor_service.get_courses_by_professor(professor_name)

        if courses:

            course_list = []
            for course in courses:
                course_list.append(
                    {
                        "course_code": course.get("course_code"),
                        "title": course.get("metadata", {}).get("title", "Unknown"),
                        "year": course.get("metadata", {}).get("year", 0),
                        "semester": course.get("metadata", {}).get("semester", 0),
                        "ects": course.get("metadata", {}).get("ects"),
                    }
                )

            return {"professor_name": professor_name, "courses": course_list}
        else:

            return {
                "error": f"No courses found for professor {professor_name}.",
                "professor_name": professor_name,
                "courses": [],
            }

    except Exception as e:

        logger.error(f"Error in get_professor_courses: {str(e)}")
        return {"error": f"Error processing professor search: {str(e)}"}


def search_courses(course_service, query: str, limit: int = 10) -> Dict:
    """Search for courses matching the query text"""
    logger.info(f"Searching courses with query: '{query}', limit: {limit}")

    if not course_service:
        logger.error("Course service not available")
        return {"error": "Course service not available"}

    try:
        results = course_service.search_courses(query, limit)

        if results and results.get("ids") and results["ids"][0]:
            courses = format_courses_for_data(results)
            return {"success": True, "courses": courses}
        else:
            return {"success": False, "error": "No courses found matching your query."}
    except Exception as e:
        logger.error(f"Error searching courses: {str(e)}")
        return {
            "success": False,
            "error": f"An error occurred while searching courses: {str(e)}",
        }


def filter_courses(
    course_service,
    year: Optional[int] = None,
    semester: Optional[int] = None,
    limit: int = 10,
) -> Dict:
    """Filter courses by year, semester, or other criteria"""
    logger.info(
        f"Filtering courses with year: {year}, semester: {semester}, limit: {limit}"
    )

    if not course_service:
        logger.error("Course service not available")
        return {"error": "Course service not available"}

    try:
        filters = {}

        if year is not None:
            filters["year"] = year
        if semester is not None:
            filters["semester"] = semester

        if not filters:
            return {
                "success": False,
                "error": "No filter criteria provided. Please specify year or semester.",
            }

        if "semester" in filters and "year" in filters:
            filters = {
                "$and": [
                    {"semester": filters["semester"]},
                    {"year": filters["year"]},
                ]
            }

        results = course_service.filter_courses(filters, limit)

        if results and results.get("ids") and results["ids"][0]:
            courses = format_courses_for_data(results)
            return {"success": True, "courses": courses}
        else:
            return {
                "success": False,
                "error": "No courses found matching your criteria.",
            }
    except Exception as e:
        logger.error(f"Error filtering courses: {str(e)}")
        return {
            "success": False,
            "error": f"An error occurred while filtering courses: {str(e)}",
        }


def search_news(
    news_service, query: str, category: Optional[str] = None, limit: int = 10
) -> Dict:
    """Search for university news and announcements"""
    logger.info(
        f"Searching news with query: '{query}', category: {category}, limit: {limit}"
    )

    if not news_service:
        logger.error("News service not available")
        return {"error": "News service not available"}

    try:
        # Convert string category to appropriate format if provided
        query_intent = None
        if category:
            category_mapping = {
                "internship": "NEWS_INTERNSHIP",
                "thesis": "NEWS_THESIS",
                "student": "NEWS_STUDENT",
                "distinctions": "NEWS_DISTINCTIONS",
                "events": "NEWS_EVENTS",
                "vacancies": "NEWS_VACANCIES",
                "general": "NEWS_GENERAL",
            }

            if category.lower() in category_mapping:
                query_intent = category_mapping[category.lower()]

        results = news_service.search_news(
            query, query_intent=query_intent, limit=limit
        )

        has_results = bool(results)
        has_documents = bool(results.get("documents")) if has_results else False
        has_content = (
            bool(results.get("documents") and results["documents"][0])
            if has_documents
            else False
        )

        if has_results and has_documents and has_content:
            news_items = []
            for i in range(len(results["documents"][0])):
                news_items.append(
                    {
                        "content": results["documents"][0][i],
                        "metadata": (
                            results["metadatas"][0][i] if "metadatas" in results else {}
                        ),
                        "distance": (
                            results["distances"][0][i]
                            if "distances" in results
                            else 1.0
                        ),
                    }
                )

            # Sort by date if available
            news_items = sorted(
                news_items, key=lambda x: -x.get("metadata", {}).get("date_epoch", 0)
            )[:limit]

            return {"success": True, "news_items": news_items}
        else:
            return {
                "success": False,
                "error": f"No news items found matching your query.",
            }
    except Exception as e:
        logger.error(f"Error searching news: {str(e)}")
        return {
            "success": False,
            "error": f"An error occurred while searching news: {str(e)}",
        }


def get_recent_news(news_service, category: str, limit: int = 5) -> Dict:
    """Get recent university news by category"""
    logger.info(f"Getting recent news for category: '{category}', limit: {limit}")

    if not news_service:
        logger.error("News service not available")
        return {"error": "News service not available"}

    try:
        # Convert string category to appropriate format
        category_mapping = {
            "internship": "NEWS_INTERNSHIP",
            "thesis": "NEWS_THESIS",
            "student": "NEWS_STUDENT",
            "distinctions": "NEWS_DISTINCTIONS",
            "events": "NEWS_EVENTS",
            "vacancies": "NEWS_VACANCIES",
            "general": "NEWS_GENERAL",
        }

        if category.lower() not in category_mapping:
            return {
                "success": False,
                "error": f"Invalid news category. Available categories: {', '.join(category_mapping.keys())}",
            }

        query_intent = category_mapping[category.lower()]

        # For recent news, we use an empty query and rely on category filtering
        results = news_service.search_news("", query_intent=query_intent, limit=limit)

        has_results = bool(results)
        has_documents = bool(results.get("documents")) if has_results else False
        has_content = (
            bool(results.get("documents") and results["documents"][0])
            if has_documents
            else False
        )

        if has_results and has_documents and has_content:
            news_items = []
            for i in range(len(results["documents"][0])):
                news_items.append(
                    {
                        "content": results["documents"][0][i],
                        "metadata": (
                            results["metadatas"][0][i] if "metadatas" in results else {}
                        ),
                        "distance": (
                            results["distances"][0][i]
                            if "distances" in results
                            else 1.0
                        ),
                    }
                )

            # Sort by date if available
            news_items = sorted(
                news_items, key=lambda x: -x.get("metadata", {}).get("date_epoch", 0)
            )[:limit]

            return {"success": True, "news_items": news_items}
        else:
            return {
                "success": False,
                "error": f"No recent news found for category: {category}",
            }
    except Exception as e:
        logger.error(f"Error getting recent news: {str(e)}")
        return {
            "success": False,
            "error": f"An error occurred while retrieving recent news: {str(e)}",
        }


def format_courses_for_data(results):
    """Format course results into a standardized format"""
    courses = []
    for i in range(len(results["ids"][0])):
        course_info = {
            "course_id": results["ids"][0][i],
            "course_code": results.get("metadatas", [[]])[0][i].get(
                "course_code", "Unknown"
            ),
            "title": results.get("metadatas", [[]])[0][i].get("title", "Unknown"),
            "year": results.get("metadatas", [[]])[0][i].get("year", 0),
            "semester": results.get("metadatas", [[]])[0][i].get("semester", 0),
            "ects": results.get("metadatas", [[]])[0][i].get("ects", 0),
            "professor": results.get("metadatas", [[]])[0][i].get(
                "professor", "Unknown"
            ),
            "content": (
                results.get("documents", [[]])[0][i] if "documents" in results else ""
            ),
        }
        courses.append(course_info)
    return courses
