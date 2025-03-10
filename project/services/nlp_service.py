# services/nlp_service.py
import logging
from models.intent_mappings import IntentType, NEWS_INTENT_MAPPING
from langchain.schema import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
import numpy as np
from config.settings import GROQ_API_KEY, GROQ_MODEL

from services.course_service import CourseService
from db.collections import Collections

logger = logging.getLogger(__name__)
collections = Collections()
course_service = CourseService(collections)

PROMPT_MAP = {
    IntentType.PROFESSOR_COURSES: """
You are a helpful university assistant providing information about professor courses.

Context information:
- Professor Name: {professor_name}
- Courses: {courses}

IMPORTANT INSTRUCTIONS:
1. Format your response as a concise, scannable list of courses
2. Begin with "Professor {professor_name} teaches the following courses:"
3. Group courses by year and semester in chronological order
4. For each course include: Course code, Title, ECTS
5. Use bullet points and proper spacing for readability
6. If the professor teaches many courses (>5), highlight diverse subject areas
7. End with the total number of courses taught

DO NOT include general explanations or unnecessary text.
""",

    IntentType.NEWS_GENERAL: """
You are a helpful university assistant providing news updates.

Context:
- News Type: General university news
- News Items: {news_items}
- User Query: "{query}"

IMPORTANT INSTRUCTIONS:
1. PRIORITIZE finding specific information related to the user's query
2. Extract and highlight ACTIONABLE INFORMATION such as:
   - URLs and links relevant to the query
   - Application forms or registration links
   - Deadlines, dates, and locations
   - Contact information and procedures
3. Format your response using bullet points for key information
4. Structure your response as:
   - Brief introduction stating what you found
   - Specific actionable information (links, dates, procedures)
   - Brief context if needed
5. If you find specific links/forms matching the query, highlight them at the beginning
6. Use bold formatting for critical information (dates, links, deadlines)

DO NOT provide general summaries without extracting the specific information requested.
""",

    IntentType.NEWS_INTERNSHIP: """
You are a helpful university assistant providing information about internship opportunities.

Context:
- Announcement Type: Internship opportunities
- Announcements: {news_items}
- User Query: "{query}"

IMPORTANT INSTRUCTIONS:
1. PRIORITIZE extracting:
   - Application links and forms
   - Deadlines
   - Eligibility requirements
   - Company/organization details
   - Contact information
2. Format your response in these clear sections:
   - Available opportunities (with direct links to applications)
   - Key deadlines (sorted by closest first)
   - Application requirements
3. Use bullet points and bold formatting for key information
4. If a specific internship was requested, highlight that information FIRST
5. Include EXACT application URLs, not just general descriptions

Focus on actionable, practical information. Do NOT provide general summaries.
""",

    IntentType.NEWS_THESIS: """
You are a helpful university assistant providing information about thesis opportunities.

Context:
- Announcement Type: Thesis opportunities
- Announcements: {news_items}
- User Query: "{query}"

IMPORTANT INSTRUCTIONS:
1. PRIORITIZE extracting:
   - Specific thesis topics available
   - Supervisor contact information
   - Application procedures and deadlines
   - Eligibility requirements
   - Research areas
2. Format your response in these clear sections:
   - Available thesis topics (grouped by subject area)
   - Application deadlines and procedures
   - Contact information for supervisors
3. Use bullet points and bold formatting for key information
4. If a specific thesis topic was requested, highlight that information FIRST
5. Include EXACT application procedures and contact methods

Focus on specific, practical information. Do NOT provide general summaries.
""",

    IntentType.NEWS_STUDENT: """
You are a helpful university assistant providing student-related announcements.

Context:
- Announcement Type: Student-related news
- Announcements: {news_items}
- User Query: "{query}"

IMPORTANT INSTRUCTIONS:
1. PRIORITIZE extracting:
   - Registration deadlines
   - Form submission links
   - Required documents
   - Important dates for student procedures
   - Contact information for student services
2. Format your response in these clear sections:
   - Urgent deadlines (if any)
   - Specific information matching user's query
   - Links to forms or applications
3. Use bullet points and bold formatting for key information
4. For forms or applications, include EXACT links and submission instructions
5. List information in order of deadline proximity

Focus on actionable, time-sensitive information. Do NOT provide general summaries.
""",

    IntentType.NEWS_DISTINCTIONS: """
You are a helpful university assistant providing information about university distinctions and awards.

Context:
- Announcement Type: Distinctions and awards
- Announcements: {news_items}
- User Query: "{query}"

IMPORTANT INSTRUCTIONS:
1. PRIORITIZE extracting:
   - Names of award recipients and their achievements
   - Details about the distinctions/awards
   - Dates and locations of award ceremonies
   - Application information for upcoming awards
2. Format your response in these clear sections:
   - Specific information matching user's query
   - Recent distinctions (with recipient names and achievements)
   - Upcoming award opportunities (if any)
3. Use bullet points and bold formatting for key information
4. If asking about specific awards or people, highlight that information FIRST

Be concise but provide specific details about achievements.
""",

    IntentType.NEWS_EVENTS: """
You are a helpful university assistant providing information about upcoming university events.

Context:
- Announcement Type: University events
- Announcements: {news_items}
- User Query: "{query}"

IMPORTANT INSTRUCTIONS:
1. PRIORITIZE extracting:
   - Event dates, times, and locations
   - Registration links and deadlines
   - Speaker/presenter information
   - Target audience and prerequisites (if any)
   - Participation requirements
2. Format your response in these clear sections:
   - Upcoming events (chronologically ordered)
   - Registration information and links
   - Event details (speakers, format, etc.)
3. Use bullet points and bold formatting for key information
4. If asking about a specific event, highlight that information FIRST
5. Include EXACT registration links and procedures

Focus on practical information needed to participate in events.
""",

    IntentType.NEWS_VACANCIES: """
You are a helpful university assistant providing information about job vacancies.

Context:
- Announcement Type: Job vacancies
- Announcements: {news_items}
- User Query: "{query}"

IMPORTANT INSTRUCTIONS:
1. PRIORITIZE extracting:
   - Position titles and departments
   - Application deadlines
   - Required qualifications
   - Application procedures and links
   - Contract terms and duration
2. Format your response in these clear sections:
   - Available positions (with application deadlines)
   - Application requirements and procedures
   - Contact information
3. Use bullet points and bold formatting for key information
4. If asking about a specific position, highlight that information FIRST
5. Include EXACT application procedures and submission instructions

Focus on information needed to apply for positions.
""",

    IntentType.COURSE_SEARCH: """
You are a helpful university assistant providing information about university courses.

Context:
- Search Query: "{query}"
- Courses Found: {courses}

IMPORTANT INSTRUCTIONS:
1. PRIORITIZE extracting:
   - Course titles and codes matching the query
   - Course content directly relevant to the query
   - Prerequisites and requirements
   - When the course is offered (year/semester)
   - Instructors and ECTS
2. Format your response in these clear sections:
   - Most relevant courses to the query
   - Key topics and content matching the query
   - Course requirements and schedule information
3. Use bullet points and bold formatting for key information
4. If asking about specific course content, highlight that information FIRST
5. Include practical information like prerequisites, workload, and assessment methods

Focus on specific information matching the query, not general course descriptions.
""",

    IntentType.COURSE_FILTERING: """
You are a helpful university assistant providing filtered course information.

Context:
- Filter Criteria: "{query}"
- Courses Found: {courses}

IMPORTANT INSTRUCTIONS:
1. PRIORITIZE organizing courses by the filter criteria (year, semester, subject, etc.)
2. Format your response in these clear sections:
   - Summary of matches (e.g., "Found 5 courses in Semester 3")
   - Categorized listings based on filter criteria
   - Brief details for each course (code, title, ECTS)
3. Use bullet points and bold formatting for key information
4. Include a tabular format if presenting multiple courses
5. Highlight any patterns or notable information about the filtered results

Provide a well-organized overview of courses matching the filter criteria.
"""
}


class NLPService:
    """Handles NLP and AI operations"""
    
    def __init__(self):
        try:
            self.llm = ChatGroq(
                model=GROQ_MODEL, 
                temperature=0.1, 
                groq_api_key=GROQ_API_KEY
            )
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
                HumanMessage(content=f"Extract the professor name from this query: {query}")
            ]

            logger.info(f"Sending professor name extraction request for: '{query}'")
            response = self.llm.invoke(messages)
            extracted_name = response.content.strip()

            if extracted_name.lower() == "none":
                logger.info(f"No professor name found in query: '{query}'")
                return None

            logger.info(f"Extracted professor name: '{extracted_name}' from query: '{query}'")
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
                HumanMessage(content=f"Classify this query: {query}")
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
                "banned_query": IntentType.BANNED_QUERY
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

    Also extract:
    - Date range if specified (e.g., "this week", "last month")
    - Specific keywords or topics mentioned

    Return ONLY the category name, nothing else.
    """
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Classify this news query: {query}")
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


    def get_embeddings(self, texts):
        """Generate embeddings for a list of texts"""
        import chromadb.utils.embedding_functions as embedding_functions
        from config.settings import JINA_API_KEY, JINA_MODEL
        
        logger.info(f"Generating embeddings for {len(texts)} texts")
        
        try:
            # Create the embedding function
            embedding_function = embedding_functions.JinaEmbeddingFunction(
                api_key=JINA_API_KEY,
                model_name=JINA_MODEL
            )
            
            # Generate embeddings
            embeddings = embedding_function(texts)
            
            logger.info(f"Successfully generated {len(embeddings)} embeddings")
            return embeddings
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise e
    
    def process_unified_query(self, query, query_intent, news_service=None, professor_service=None, 
                          course_service=None, name_service=None):
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
                    courses = professor_service.get_courses_by_professor(professor_name)
                    if courses:
                        canonical_name = name_service.find_canonical_name(professor_name) or professor_name
                        course_list = self._format_courses_for_data(courses)
                        
                        context_data = {
                            "professor_name": canonical_name,
                            "courses": course_list,
                        }
                        
                        natural_response = self.generate_response(query_intent, context_data, query)
                        
                        return context_data, natural_response, query_intent
                    else:
                        return None, f"No courses found for professor {professor_name}.", "no_results"
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
                    results = news_service.search_news(query, query_intent=query_intent, limit=10)
                    
                    has_results = bool(results)
                    has_documents = bool(results.get("documents")) if has_results else False
                    has_content = bool(results.get("documents") and results["documents"][0]) if has_documents else False
                    logger.info(f"Has results: {has_results}, Has documents: {has_documents}, Has content: {has_content}")
                    if has_results and has_documents and has_content:
                        news_items = []
                        for i in range(len(results["documents"][0])):
                            news_items.append({
                                "content": results["documents"][0][i],
                                "metadata": results["metadatas"][0][i] if "metadatas" in results else {},
                                "distance": results["distances"][0][i] if "distances" in results else 1.0
                            })
                        
                        filtered_news_items = self.filter_relevant_content(news_items, max_items=5, intent = query_intent)

                        context_data = {"news_items": filtered_news_items}
                        natural_response = self.generate_response(query_intent, context_data, query)
                        
                        return {"news_items": filtered_news_items}, natural_response, query_intent
                    
                    category = NEWS_INTENT_MAPPING[query_intent].replace("type_", "").replace("_", " ")
                    return None, f"No {category} announcements found matching your query.", "no_results"
                except Exception as e:
                    logger.error(f"Error in news search: {str(e)}")
                    return None, "An error occurred while searching for news.", "error"
        
        if query_intent in [IntentType.COURSE_FILTERING, IntentType.COURSE_SEARCH]:
            if course_service:
                results = course_service.search_courses(query, 10)
                if results and results["ids"][0]:
                    courses = self._format_courses_for_data(results)
                    
                    # Filter courses to most relevant ones
                    filtered_courses = self.filter_relevant_content(courses, max_items=5)
                    
                    natural_response = self.generate_response(query_intent, filtered_courses, query)
                    
                    return filtered_courses, natural_response, query_intent
                
                return None, "No courses found matching your query.", "no_results"
        
        if query_intent == IntentType.COURSE_SEARCH:
            if course_service:
                results = course_service.search_courses(query, 10)
                if results and results["ids"][0]:
                    courses = self._format_courses_for_data(results)
                
                  #  filtered_courses = self.filter_relevant_content(courses, max_items=5, intent=query_intent)
                    

                    context_data = {"courses": courses}
                    natural_response = self.generate_response(query_intent, context_data, query)
                    
                    return context_data, natural_response, query_intent
                
                return None, "No results found for your query.", "no_results"

    def _format_courses_for_data(self, courses_or_results):
        """Format course data consistently for response"""
        formatted_courses = []
        
     
        if isinstance(courses_or_results, dict) and "ids" in courses_or_results:
            results = courses_or_results
            for i in range(len(results["ids"][0])):
                formatted_courses.append({
                    "course_code": results["ids"][0][i],
                    "title": results["metadatas"][0][i].get("title", "Unknown"),
                    "year": results["metadatas"][0][i].get("year", 0),
                    "semester": results["metadatas"][0][i].get("semester", 0),
                    "ects": results["metadatas"][0][i].get("ects"),
                    "document": results["documents"][0][i],
                    "distance": results["distances"][0][i] if "distances" in results else 1.0
                })
       
        elif isinstance(courses_or_results, list):
            for course in courses_or_results:
                formatted_courses.append({
                    "course_code": course["course_code"],
                    "title": course["metadata"].get("title", "Unknown"),
                    "year": course["metadata"].get("year", 0),
                    "semester": course["metadata"].get("semester", 0),
                    "ects": course["metadata"].get("ects"),
                    "document": course["document"],
                    "distance": 1.0  
                })
        
        return formatted_courses
   
   
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
            return self._generate_fallback_response(intent, context_data)
            
        if intent in NEWS_INTENT_MAPPING and "news_items" in context_data:
            context_data["news_items"] = self.filter_relevant_content(
                context_data["news_items"], 
                max_items=3  
            )
        elif intent in [IntentType.COURSE_SEARCH, IntentType.COURSE_FILTERING] and "courses" in context_data:
            context_data["courses"] = self.filter_relevant_content(
                context_data["courses"],
                intent=intent,
                max_items=5
            )

        try:
            if intent not in PROMPT_MAP:
                logger.warning(f"No prompt defined for intent {intent}, using generic prompt")
                prompt = "You are a helpful university assistant. Summarize the following information: {context}"
            else:
                prompt = PROMPT_MAP[intent]

            formatted_prompt = self._format_prompt_with_context(prompt, intent, context_data, query)
            
            messages = [
                SystemMessage(content=formatted_prompt),
                HumanMessage(content="Generate a helpful response based on this information.")
            ]
            
            logger.info(f"Sending response generation request for intent: {intent}")
            response = self.llm.invoke(messages)
            
            logger.info("context data: length: " + str(len(context_data)))
            logger.info(f"Generated response for intent {intent}")
            return response.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return self._generate_fallback_response(intent, context_data)
    
    def _format_prompt_with_context(self, prompt, intent, context_data, query=None):
        """Format prompt with context data and clearly identify the user's query"""
        try:
            format_data = {}
            
            original_query_section = ""
            if query:
                original_query_section = f"\n\nOriginal user query: \"{query}\""
                format_data["query"] = query
                
            if intent == IntentType.PROFESSOR_COURSES:
                format_data["professor_name"] = context_data.get("professor_name", "Unknown")
                format_data["courses"] = self._format_courses_for_prompt(context_data.get("courses", []))
                
            elif intent in NEWS_INTENT_MAPPING:
                format_data["news_items"] = self._format_news_for_prompt(context_data.get("news_items", []))
                
            elif intent == IntentType.COURSE_SEARCH or intent == IntentType.COURSE_FILTERING:
                format_data["courses"] = self._format_courses_for_prompt(context_data)
            
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
            if course.get('ects'):
                formatted_text += f"  - ECTS: {course.get('ects')}\n"
            if course.get('document'):
                doc_preview = course.get('document', '')[:500]
                if len(course.get('document', '')) > 500:
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
            formatted_text += f"  - Title: {item.get('metadata', {}).get('title', 'Untitled')}\n"
            if 'date_published' in item.get('metadata', {}):
                formatted_text += f"  - Date: {item['metadata']['date_published']}\n"
            
            #full content
            formatted_text += f"  - Content: {item.get('content', '')}\n"
            
            #λιν
            if 'links' in item.get('metadata', {}):
                formatted_text += "  - Links:\n"
                for link in item['metadata']['links']:
                    formatted_text += f"    - {link.get('text', '')}: {link.get('url', '')}\n"
            formatted_text += "\n"
            
        return formatted_text
    
    def apply_reranker(self, query, content_items, max_items=3):
        
        ##todo 
        logger.info("not yet")
        return self.filter_relevant_content(content_items, max_items)

    def filter_relevant_content(self, content_items, max_items=3, intent = None, threshold=0.5):
        if not content_items:
            return []
        
        if intent == IntentType.NEWS_GENERAL:
            
            return sorted(
                content_items, 
                key=lambda x: -x.get("metadata", {}).get("date_epoch", 0)  #*sort by newest 
            )[:max_items]

        if intent == IntentType.COURSE_SEARCH:
            return sorted(
                content_items, 
                key=lambda x: -x.get("metadata", {}).get("year", 0)  
            )[:max_items]
        
        try:
            sorted_items = sorted(content_items, key=lambda x: x.get("distance", 1.0))
            
            filtered_items = [item for item in sorted_items if item.get("distance", 1.0) <= threshold]
            
            return filtered_items[:max_items]
                
        except Exception as e:
            logger.error(f"Error filtering content: {str(e)}")
            return content_items[:max_items]



    #! fallback otan dn exei llm 
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

        #* Group courses by year and semester
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
            IntentType.NEWS_GENERAL: "news announcements"
        }
        
        title = intent_titles.get(intent, "announcements")
        response = f"Here are the latest {title}:\n\n"
        
        for i, item in enumerate(news_items[:5], 1):
            response += f"{i}. {item['metadata'].get('title', 'Announcement')}"
            if 'date_published' in item['metadata']:
                response += f" ({item['metadata']['date_published']})"
            response += "\n"
            content = item['content']
            if len(content) > 150:
                content = content[:150] + "..."
            response += f"{content}\n\n"
        
        return response