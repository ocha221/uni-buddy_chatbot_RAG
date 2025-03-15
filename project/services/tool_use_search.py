
import logging
import json
import os
from typing import Dict, List, Any

from langchain_core.messages import ToolMessage, HumanMessage, SystemMessage
from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field
from config.settings import GROQ_API_KEY, GROQ_MODEL, SIMILARITY_THRESHOLD


logger = logging.getLogger(__name__)
tool_logger = logging.getLogger("tool_logs")
tool_logger.setLevel(logging.DEBUG)


if not tool_logger.handlers:
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
    os.makedirs(log_dir, exist_ok=True)
    file_handler = logging.FileHandler(os.path.join(log_dir, "tool_logs.log"))
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    tool_logger.addHandler(file_handler)


class GetProfessorCourses(BaseModel):
    """Get courses taught by a specific professor"""
    professor_name: str = Field(..., description="The name of the professor to search for")

class ConfirmProfessorName(BaseModel):
    """Confirm a suggested professor name and get their courses"""
    confirmed_name: str = Field(..., description="The confirmed name of the professor")

class ToolBasedChatService:
    """Handles conversations with Groq LLM using tool calls"""
    
    def __init__(self, nlp_service=None, professor_service=None, course_service=None, news_service=None, name_service=None):
        tool_logger.info("Initializing ToolBasedChatService")
        self.nlp_service = nlp_service
        self.professor_service = professor_service
        self.course_service = course_service
        self.news_service = news_service
        self.name_service = name_service
        
        tool_logger.debug(f"Services initialized - NLP: {nlp_service is not None}, "
                         f"Professor: {professor_service is not None}, "
                         f"Course: {course_service is not None}, "
                         f"News: {news_service is not None}, "
                         f"Name: {name_service is not None}")
        
        
        tool_logger.info("Configuring available tools")
        self.tools = [GetProfessorCourses, ConfirmProfessorName]
        
        try:
            tool_logger.info(f"Initializing Groq LLM with model: {GROQ_MODEL}")
            os.environ["GROQ_API_KEY"] = GROQ_API_KEY
            self.llm = init_chat_model(GROQ_MODEL, model_provider="groq")
            self.llm_with_tools = self.llm.bind_tools(self.tools)
            tool_logger.info(f"Successfully initialized Groq LLM with {len(self.tools)} available tools")
            logger.info(f"Initialized Groq LLM with model: {GROQ_MODEL} for tool calling")
        except Exception as e:
            tool_logger.error(f"Failed to initialize Groq LLM: {str(e)}", exc_info=True)
            logger.error(f"Failed to initialize Groq LLM for tool calling: {str(e)}")
            self.llm = None
            self.llm_with_tools = None
    
    def process_message(self, message: str, session_context: Dict = None) -> Dict:
        """Process a user message using LLM with tool calling"""
        tool_logger.info(f"Processing message: '{message[:50]}{'...' if len(message) > 50 else ''}'")
        
        if session_context:
            tool_logger.debug(f"Session context provided: {json.dumps(session_context)}")
        
        if not self.llm_with_tools:
            tool_logger.error("LLM not initialized, cannot process message")
            return {"message": "Sorry, I'm not able to process your request right now."}
        
        tool_logger.debug("Creating system prompt")
        system_prompt = """
You are a university assistant that helps students and faculty find information.

IMPORTANT: When a user mentions ANY professor name, even if they don't explicitly ask about courses:
1. Always extract the professor's name from the user's message
2. ALWAYS call the GetProfessorCourses tool with the professor's name as the professor_name parameter
3. If a clarification is needed, ask if they meant the suggested name
4. If they confirm, use the ConfirmProfessorName tool

Examples of when to extract names and call the tool:
- "What courses does Adam teach?"
- "The professor is Adam georgios"
- "hmm, the name is Adam georgios"
- "I'm looking for Adam"

Always pass the full name you extracted as the professor_name parameter.
"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=message)
        ]
        tool_logger.debug("Created message array with system prompt and user message")
        
        try:
            
            tool_logger.info("Sending request to LLM")
            response = self.llm_with_tools.invoke(messages)
            tool_logger.info("Received response from LLM")
            tool_logger.debug(f"LLM response content: '{response.content[:100]}{'...' if len(response.content) > 100 else ''}'")
            
            
            if hasattr(response, 'tool_calls') and response.tool_calls:
                tool_logger.info(f"LLM requested {len(response.tool_calls)} tool call(s)")
                
                
                messages.append(response)
                
                tool_results = {}
                
                for tool_call in response.tool_calls:
                    
                    function_name = tool_call["name"]
                    function_args = tool_call["args"]
                    tool_call_id = tool_call["id"]
                    
                    tool_logger.info(f"Processing tool call: {function_name}")
                    tool_logger.debug(f"Tool arguments: {json.dumps(function_args)}")
                    
                    result = None
                    
                    
                    if function_name == "GetProfessorCourses":
                        professor_name = function_args.get("professor_name")
                        tool_logger.info(f"Executing GetProfessorCourses for '{professor_name}'")
                        result = self._get_professor_courses(professor_name)
                    
                    
                    elif function_name == "ConfirmProfessorName":
                        confirmed_name = function_args.get("confirmed_name")
                        tool_logger.info(f"Executing ConfirmProfessorName for '{confirmed_name}'")
                        result = self._get_professor_courses(confirmed_name)
                    
                    if result:
                        tool_logger.debug(f"Tool result: {json.dumps(result)}")
                        tool_results[function_name] = result
                        
                        
                        messages.append(ToolMessage(
                            content=json.dumps(result),
                            tool_call_id=tool_call_id
                        ))
                
                
                tool_logger.info("Requesting final response from LLM after tool execution")
                final_response = self.llm.invoke(messages)
                tool_logger.info("Received final response")
                tool_logger.debug(f"Final response content: '{final_response.content[:100]}{'...' if len(final_response.content) > 100 else ''}'")
                
                return {
                    "message": final_response.content,
                    "data": tool_results
                }
            else:
                
                tool_logger.info("No tool calls requested, returning standard response")
                return {"message": response.content}
            
        except Exception as e:
            tool_logger.error(f"Error processing message with tools: {str(e)}", exc_info=True)
            logger.error(f"Error processing message with tools: {str(e)}")
            return {"message": "Sorry, I encountered an error while processing your request."}
    
    def _get_professor_courses(self, professor_name: str) -> Dict:
        """Get courses taught by a professor"""
        tool_logger.info(f"Getting courses for professor: '{professor_name}'")
        
        if not professor_name:
            tool_logger.warning("Empty professor name provided")
            return {"error": "Missing required services or invalid professor name"}
            
        if not self.professor_service:
            tool_logger.error("Professor service not available")
            return {"error": "Missing required services or invalid professor name"}
            
        if not self.name_service:
            tool_logger.error("Name service not available")
            return {"error": "Missing required services or invalid professor name"}
        
        try:
            tool_logger.debug(f"Finding canonical name for '{professor_name}'")
            canonical_name, confidence = self.name_service.find_canonical_name_with_confidence(professor_name)
            
            confidence = float(confidence) if confidence is not None else 0.0
            tool_logger.info(f"Canonical name result: '{canonical_name}' with confidence {confidence}")
            if canonical_name and confidence < SIMILARITY_THRESHOLD:
                tool_logger.info(f"Confidence {confidence} below threshold {SIMILARITY_THRESHOLD}, requesting clarification")
                return {
                    "clarification_needed": True,
                    "candidate_match": canonical_name,
                    "original_name": professor_name,
                    "confidence": confidence
                }
            if canonical_name:
                tool_logger.info(f"Using canonical name '{canonical_name}' instead of '{professor_name}'")
                professor_name = canonical_name
            
            
            tool_logger.info(f"Retrieving courses for professor '{professor_name}'")
            courses = self.professor_service.get_courses_by_professor(professor_name)
            
            if courses:
                tool_logger.info(f"Found {len(courses)} courses for professor '{professor_name}'")
                
                course_list = []
                for course in courses:
                    course_list.append({
                        "course_code": course.get("course_code"),
                        "title": course.get("metadata", {}).get("title", "Unknown"),
                        "year": course.get("metadata", {}).get("year", 0),
                        "semester": course.get("metadata", {}).get("semester", 0),
                        "ects": course.get("metadata", {}).get("ects"),
                    })
                
                tool_logger.debug(f"Formatted course list: {json.dumps(course_list)}")
                return {
                    "professor_name": professor_name,
                    "courses": course_list
                }
            else:
                tool_logger.info(f"No courses found for professor '{professor_name}'")
                return {
                    "error": f"No courses found for professor {professor_name}.",
                    "professor_name": professor_name,
                    "courses": []
                }
                
        except Exception as e:
            tool_logger.error(f"Error in get_professor_courses for '{professor_name}': {str(e)}", exc_info=True)
            logger.error(f"Error in get_professor_courses: {str(e)}")
            return {"error": f"Error processing professor search: {str(e)}"}