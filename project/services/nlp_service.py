# services/nlp_service.py
import logging
from models.intent_mappings import IntentType, NEWS_INTENT_MAPPING
from langchain.schema import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
import numpy as np
from config.settings import GROQ_API_KEY, GROQ_MODEL, SIMILARITY_THRESHOLD

from services.course_service import CourseService
from services.response_formatter import ResponseFormatter
from db.collections import Collections
from models.prompt_map import PROMPT_MAP

logger = logging.getLogger(__name__)
collections = Collections()
course_service = CourseService(collections)


class NLPService:
    """Handles NLP and AI operations"""

    def __init__(self):
        try:
            self.llm = ChatGroq(
                model=GROQ_MODEL, temperature=0.1, groq_api_key=GROQ_API_KEY
            )
            self.formatter = ResponseFormatter()
            logger.info(f"Initialized Groq LLM with model: {GROQ_MODEL}")
        except Exception as e:
            logger.error(f"Failed to initialize Groq LLM: {str(e)}")
            self.llm = None
            
    def extract_professor_name(self, query):
        """Extract professor name from query using LLM"""
        if not self.llm:
            logger.warning("LLM not initialized, falling back to simple extraction")
            return None

        if not query or len(query.strip()) < 3:
            return None

        try:
            system_prompt = """
You are a professor name extractor for a university information system.

## Task Description
Extract ONLY the full professor name from queries, which may contain Greek terms like "mathimata" (meaning "courses").

## Rules
1. Return ONLY the full professor name as a simple text string
2. Return "None" if no professor name is detected
3. Do not include titles (Dr., Prof., etc.) in the output
4. Recognize names regardless of their position in the query
5. Identify full names (first and last name together) as professor names
6. Single names (just first or just last name) should be identified as professor names if they appear to be names rather than other terms

## Format
- Return only the name without any explanation or formatting
- Maintain the original capitalization of the name
- Remove any non-name elements from the output

## Examples
Input: "mathimata Ioannis Georgios"
Output: "Ioannis Georgios"

Input: "Ioannis Georgios mathimata"
Output: "Ioannis Georgios"

Input: "Georgios"
Output: "Georgios"

Input: "mathimata 2023"
Output: "None"

Input: "πότε έχει ώρες γραφείου ο Papadopoulos"
Output: "Papadopoulos"
"""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(
                    content=f"Extract the professor name from this query: {query}"
                ),
            ]

            logger.info(f"Sending professor name extraction request for: '{query}'")
            response = self.llm.invoke(messages)
            extracted_name = response.content.strip()

            if extracted_name.lower() == "none":
                logger.info(f"No professor name found in query: '{query}'")
                return None

            logger.info(
                f"Extracted professor name: '{extracted_name}' from query: '{query}'"
            )
            return extracted_name

        except Exception as e:
            logger.error(f"Error extracting professor name: {str(e)}")
            return None

    def calculate_similarity(self, v1, v2):
        """Calculate cosine similarity between two vectors"""
        try:
            dot_product = np.dot(v1, v2)
            norm_v1 = np.linalg.norm(v1)
            norm_v2 = np.linalg.norm(v2)
            return dot_product / (norm_v1 * norm_v2)
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {str(e)}")
            return 0.0

    def analyze_query_intent(self, query):
        """
        First-stage
        """
        try:
            system_prompt = """
    You are analyzing user queries for a university information system.
    Classify the query into exactly ONE of these categories:

    - "professor_courses": Questions about what courses a professor teaches
    - "course_search": Searching for specific course content or topics
    - "course_filtering": Filtering courses by year, semester, etc.
    - "news": ANY questions about university news, announcements, events, internships, etc.
    - "general_info": General questions about the university
    - "unknown": Unrecognized or irrelevant queries
    - "banned_query": NSFW, hateful, or otherwise inappropriate queries

    Examples:
    - "What courses does Professor Smith teach?" → "professor_courses"
    - "Tell me about programming courses" → "course_search" 
    - "Which courses are in the 3rd semester?" → "course_filtering"
    - "Mathimata 3o etos" → "course_filtering"
    - "Are there any internship announcements?" → "news"
    - "Latest thesis opportunities" → "news"
    - "Student announcements this week" → "news"
    - "Recent university awards" → "news"
    - "Upcoming university events" → "news"
    - "What's new at the university?" → "news"

    Return ONLY the category name, nothing else.
    """
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Classify this query: {query}"),
            ]

            response = self.llm.invoke(messages)
            intent = response.content.strip().lower()

            intent_mapping = {
                "professor_courses": IntentType.PROFESSOR_COURSES,
                "professor course": IntentType.PROFESSOR_COURSES,
                "professor": IntentType.PROFESSOR_COURSES,
                "course_search": IntentType.COURSE_SEARCH,
                "course search": IntentType.COURSE_SEARCH,
                "course_filtering": IntentType.COURSE_FILTERING,
                "course filter": IntentType.COURSE_FILTERING,
                "news": IntentType.NEWS_GENERAL,
                "general_info": IntentType.GENERAL_INFO,
                "general": IntentType.GENERAL_INFO,
                "unknown": IntentType.UNKNOWN,
                "banned_query": IntentType.BANNED_QUERY,
            }

            if intent in intent_mapping:
                if intent == "banned_query":
                    logger.warning(f"Banned query detected: {query}")
                return intent_mapping[intent]

            for key, value in intent_mapping.items():
                if key in intent:
                    return value

            return IntentType.UNKNOWN

        except Exception as e:
            logger.error(f"Error analyzing query intent: {str(e)}")
            return IntentType.UNKNOWN

    def analyze_news_intent(self, query):
        """
        stage 2 an to query einai gia nea
        """
        try:
            system_prompt = """
    You are analyzing user queries specifically about university news announcements.
    Classify the query into exactly ONE of these news categories:

    - "news_internship": Questions about internship or practical training announcements
    - "news_ptixiaki": Questions about thesis or dissertation announcements 
    - "news_student": Questions about student-related news and announcements
    - "news_distinctions": Questions about distinctions, awards, or recognitions
    - "news_events": Questions about university events, activities, or seminars
    - "news_vacancies": Questions about job openings or position vacancies
    - "news_general": General news inquiries not fitting into other news categories


    Return ONLY the category name, nothing else.
    """
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Classify this news query: {query}"),
            ]

            response = self.llm.invoke(messages)
            intent = response.content.strip().lower()

            intent_mapping = {
                "news_internship": IntentType.NEWS_INTERNSHIP,
                "internship": IntentType.NEWS_INTERNSHIP,
                "news_ptixiaki": IntentType.NEWS_THESIS,
                "thesis": IntentType.NEWS_THESIS,
                "ptixiaki": IntentType.NEWS_THESIS,
                "news_student": IntentType.NEWS_STUDENT,
                "student news": IntentType.NEWS_STUDENT,
                "news_distinctions": IntentType.NEWS_DISTINCTIONS,
                "distinctions": IntentType.NEWS_DISTINCTIONS,
                "awards": IntentType.NEWS_DISTINCTIONS,
                "news_events": IntentType.NEWS_EVENTS,
                "events": IntentType.NEWS_EVENTS,
                "news_vacancies": IntentType.NEWS_VACANCIES,
                "vacancies": IntentType.NEWS_VACANCIES,
                "news_general": IntentType.NEWS_GENERAL,
            }

            if intent in intent_mapping:
                return intent_mapping[intent]

            for key, value in intent_mapping.items():
                if key in intent:
                    return value

            return IntentType.NEWS_GENERAL

        except Exception as e:
            logger.error(f"Error analyzing news intent: {str(e)}")
            return IntentType.NEWS_GENERAL

    def extract_time_info_from_query(self, query):
        """
        extract info about semester/year
        second stage if query is COURSE_FILTERING
        tbd"""
        try:
            system_prompt = """
You are a university assistant analyzing user queries.
Your task is to extract specific time-related information from the query.
Classify the query via the following rubric:
-"course_year" : The user is asking about courses in a specific year (e.g., "3rd year", "2nd year").
-"course_semester" : The user is asking about courses in a specific semester (e.g., "1st semester", "2nd semester").
-"course_year_semester" : The user is asking about courses in a specific year and semester (e.g., "3rd year, 2nd semester").

Examples:
-"mathimata 3o etos" → [3,None,None]
-"mathimata 2o eksamino" → [None,2,None]
-"poia mathimata exei to 3o etos" → [3,None,None]
-"ποια μαθηματα θα παρακολουθησω το 2ο εξάμηνο" → [None,2,None]
return ONLY the classification as a list of three elements: [year, semester, year_semester].
        """
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Extract time info from this query: {query}"),
            ]

            response = self.llm.invoke(messages)
            extracted_info = response.content.strip()
            parsed_info = eval(extracted_info)

            if len(parsed_info) != 3:
                logger.error(
                    f"Invalid format for extracted time info: {extracted_info}"
                )
                return None

            return parsed_info
        except Exception as e:
            logger.error(f"Error extracting time info from query: {str(e)}")
            return None
        pass

    def get_embeddings(self, texts):
        """Generate embeddings for a list of texts"""
        import chromadb.utils.embedding_functions as embedding_functions
        from config.settings import JINA_API_KEY, JINA_MODEL

        logger.info(f"Generating embeddings for {len(texts)} texts")

        try:
            # Create the embedding function
            embedding_function = embedding_functions.JinaEmbeddingFunction(
                api_key=JINA_API_KEY, model_name=JINA_MODEL
            )

            # Generate embeddings
            embeddings = embedding_function(texts)

            logger.info(f"Successfully generated {len(embeddings)} embeddings")
            return embeddings
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise e

    def process_unified_query(
        self,
        query,
        query_intent,
        news_service=None,
        professor_service=None,
        course_service=None,
        name_service=None,
    ):
        """
        Process a user query:
        - Get relevant data based on intent
        - Filter to most relevant items
        - Generate natural language response

        (filtered_data, natural_response, query_type)
        """

        if query_intent == IntentType.BANNED_QUERY:
            return None, "Query is not allowed.", "banned_query"

        if query_intent == IntentType.UNKNOWN:
            return None, "Sorry! Can you please rephrase your question?", "unknown"

        if query_intent == IntentType.PROFESSOR_COURSES:
            professor_name = self.extract_professor_name(query)
            if professor_name and professor_service:
                try:
                    
                    if hasattr(name_service, "find_canonical_name_with_confidence"):
                        canonical_name, confidence = name_service.find_canonical_name_with_confidence(professor_name)

                        confidence = float(confidence) if confidence is not None else 0.0
                        if canonical_name and confidence < SIMILARITY_THRESHOLD:
                            metadata = {
                                "clarification_needed": True,
                                "candidate_match": canonical_name,
                                "confidence": confidence
                            } #TODO with chat_Service
                            return metadata, f"I found a professor named '{canonical_name}' that seems similar to '{professor_name}'. Is that who you meant?", "clarification_request"
                        
                        if canonical_name:
                            professor_name = canonical_name
                    else:
                        #* fallback
                        canonical_name = name_service.find_canonical_name(professor_name) or professor_name
                        professor_name = canonical_name
                    
                    courses = professor_service.get_courses_by_professor(professor_name)
                    if courses:
                        course_list = self.formatter._format_courses_for_data(courses)

                        context_data = {
                            "professor_name": professor_name,
                            "courses": course_list,
                        }

                        natural_response = self.generate_response(
                            query_intent, context_data, query
                        )

                        return context_data, natural_response, query_intent
                    else:
                        return (
                            None,
                            f"No courses found for professor {professor_name}.",
                            "no_results",
                        )
                except Exception as e:
                    logger.error(f"Error processing professor query: {str(e)}")
                    return None, "An error occurred processing your query.", "error"
       
       
        if query_intent == IntentType.NEWS_GENERAL:
            specific_news_intent = self.analyze_news_intent(query)
            logger.info(f"Second-stage classification: {specific_news_intent}")
            query_intent = specific_news_intent

        if query_intent in NEWS_INTENT_MAPPING:
            if news_service:
                try:
                    results = news_service.search_news(
                        query, query_intent=query_intent, limit=10
                    )

                    has_results = bool(results)
                    has_documents = (
                        bool(results.get("documents")) if has_results else False
                    )
                    has_content = (
                        bool(results.get("documents") and results["documents"][0])
                        if has_documents
                        else False
                    )
                    logger.info(
                        f"Has results: {has_results}, Has documents: {has_documents}, Has content: {has_content}"
                    )
                    if has_results and has_documents and has_content:
                        news_items = []
                        for i in range(len(results["documents"][0])):
                            news_items.append(
                                {
                                    "content": results["documents"][0][i],
                                    "metadata": (
                                        results["metadatas"][0][i]
                                        if "metadatas" in results
                                        else {}
                                    ),
                                    "distance": (
                                        results["distances"][0][i]
                                        if "distances" in results
                                        else 1.0
                                    ),
                                }
                            )

                        filtered_news_items = self.filter_relevant_content(
                            news_items, max_items=5, intent=query_intent
                        )

                        context_data = {"news_items": filtered_news_items}
                        natural_response = self.generate_response(
                            query_intent, context_data, query
                        )

                        return (
                            {"news_items": filtered_news_items},
                            natural_response,
                            query_intent,
                        )

                    category = (
                        NEWS_INTENT_MAPPING[query_intent]
                        .replace("type_", "")
                        .replace("_", " ")
                    )
                    return (
                        None,
                        f"No {category} announcements found matching your query.",
                        "no_results",
                    )
                except Exception as e:
                    logger.error(f"Error in news search: {str(e)}")
                    return None, "An error occurred while searching for news.", "error"

        if query_intent == IntentType.COURSE_FILTERING:
            filters = {}
            limit = 10

            infogram = self.extract_time_info_from_query(query)
            if infogram:
                logger.info(f"Extracted time info: {infogram}")
                year, semester, _ = infogram

                if year is not None:
                    filters["year"] = year
                if semester is not None:
                    filters["semester"] = semester

                if year is not None or semester is not None:
                    limit = 27

                if "semester" in filters and "year" in filters:
                    filters = {
                        "$and": [
                            {"semester": filters["semester"]},
                            {"year": filters["year"]},
                        ]
                    }

                try:
                    results = course_service.filter_courses(filters, limit)

                    if results and results.get("ids") and results["ids"][0]:
                        courses = self.formatter._format_courses_for_data(results)

                        context_data = {"courses": courses}
                        natural_response = self.generate_response(
                            query_intent, context_data, query
                        )

                        return context_data, natural_response, query_intent
                    else:
                        return (
                            None,
                            "No courses found matching your criteria.",
                            "no_results",
                        )

                except Exception as e:
                    logger.error(f"Error filtering courses: {str(e)}")
                    return None, "An error occurred while filtering courses.", "error"

            # * no time info
            if course_service:
                try:
                    results = course_service.search_courses(query, 10)
                    if results and results.get("ids") and results["ids"][0]:
                        courses = self.formatter._format_courses_for_data(results)

                        context_data = {"courses": courses}
                        natural_response = self.generate_response(
                            query_intent, context_data, query
                        )

                        return context_data, natural_response, query_intent

                    return None, "No courses found matching your query.", "no_results"
                except Exception as e:
                    logger.error(f"Error searching courses: {str(e)}")
                    return None, "An error occurred while searching courses.", "error"
            else:
                return None, "Course service not available.", "error"

        if query_intent == IntentType.COURSE_SEARCH:
            if course_service:
                results = course_service.search_courses(query, 10)
                if results and results["ids"][0]:
                    courses = self.formatter._format_courses_for_data(results)

                    #  filtered_courses = self.filter_relevant_content(courses, max_items=5, intent=query_intent)

                    context_data = {"courses": courses}
                    natural_response = self.generate_response(
                        query_intent, context_data, query
                    )

                    return context_data, natural_response, query_intent

                return None, "No results found for your query.", "no_results"
    
    def generate_response(self, intent, context_data, query=None):
        """
        Generate a natural language response using the LLM based on intent and data

        Args:
            intent: IntentType enum value
            context_data: Dict containing data relevant to the intent
            query: Original user query (optional)

        Returns:
            Formatted natural language response
        """
        if not self.llm:
            logger.warning("LLM not initialized, falling back to template responses")
            return self.formatter._generate_fallback_response(intent, context_data)

        if intent in NEWS_INTENT_MAPPING and "news_items" in context_data:
            context_data["news_items"] = self.filter_relevant_content(
                context_data["news_items"], max_items=3
            )
        elif intent in [IntentType.COURSE_SEARCH] and "courses" in context_data:
            context_data["courses"] = self.filter_relevant_content(
                context_data["courses"], intent=intent, max_items=5
            )

        try:
            if intent not in PROMPT_MAP:
                logger.warning(
                    f"No prompt defined for intent {intent}, using generic prompt"
                )
                prompt = "You are a helpful university assistant. Summarize the following information: {context}"
            else:
                prompt = PROMPT_MAP[intent]

            formatted_prompt = self.formatter._format_prompt_with_context(
                prompt, intent, context_data, query
            )

            messages = [
                SystemMessage(content=formatted_prompt),
                HumanMessage(
                    content="Generate a helpful response based on this information."
                ),
            ]

            logger.info(f"Sending response generation request for intent: {intent}")
            response = self.llm.invoke(messages)

            logger.info("context data: length: " + str(len(context_data)))
            logger.info(f"Generated response for intent {intent}")
            return response.content.strip()

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return self.formatter._generate_fallback_response(intent, context_data)

    def apply_reranker(self, query, content_items, max_items=3):

        ##todo
        logger.info("not yet")
        return self.filter_relevant_content(content_items, max_items)

    def filter_relevant_content(
        self, content_items, max_items=3, intent=None, threshold=0.5
    ):
        if not content_items:
            return []

        if intent == IntentType.NEWS_GENERAL:
            return sorted(
                content_items,
                key=lambda x: -x.get("metadata", {}).get(
                    "date_epoch", 0
                ),  # *sort by newest
            )[:max_items]

        if intent == IntentType.COURSE_SEARCH:
            return sorted(
                content_items, key=lambda x: -x.get("metadata", {}).get("year", 0)
            )[:max_items]

        try:
            sorted_items = sorted(content_items, key=lambda x: x.get("distance", 1.0))

            filtered_items = [
                item for item in sorted_items if item.get("distance", 1.0) <= threshold
            ]

            return filtered_items[:max_items]

        except Exception as e:
            logger.error(f"Error filtering content: {str(e)}")
            return content_items[:max_items]

    #! fallback otan dn exei llm
