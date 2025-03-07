# services/nlp_service.py
import logging
from langchain.schema import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
import numpy as np
from config.settings import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

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
        Analyze the intent of a user query
        Returns one of: "course_search", "professor_courses", "course_filtering", "general_info"
        """
        try:
            system_prompt = """
    You are analyzing user queries for a university information system.
    Classify the query into exactly ONE of these categories:
    - "professor_courses": Questions about what courses a professor teaches
    - "course_search": Searching for specific course content or topics
    - "course_filtering": Filtering courses by year, semester, etc.
    - "general_info": General questions about the university
    - "news_internship": Questions about internship announcements
    - "news_ptixiaki": Questions about thesis announcements
    - "news_general": General news inquiries
    - "unknown": Unrecognized or irrelevant queries

    Return ONLY the category name, nothing else.
    """
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Classify this query: {query}")
            ]

            response = self.llm.invoke(messages)
            intent = response.content.strip().lower()
            
            # Normalize the response
            if "professor" in intent:
                return "professor_courses"
            elif "filter" in intent or "year" in intent or "semester" in intent:
                return "course_filtering"
            elif "course" in intent or "search" in intent:
                return "course_search"
            else:
                return "general_info"
                
        except Exception as e:
            logger.error(f"Error analyzing query intent: {str(e)}")
            return "course_search"  # Default fallback
   
        
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