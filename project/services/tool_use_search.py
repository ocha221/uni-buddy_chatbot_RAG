import logging
import json
import os
from typing import Dict, List, Any, Optional, Union
import datetime

from langchain_core.messages import ToolMessage, HumanMessage, SystemMessage
from langchain.chat_models import init_chat_model
from config.settings import GROQ_API_KEY, GROQ_MODEL, SIMILARITY_THRESHOLD
from services.response_formatter import ResponseFormatter

# Import the tool utilities
from models.llm_tools import (
    GetProfessorCourses,
    SearchCourses,
    FilterCourses,
    SearchNews,
    GetRecentNews,
    get_professor_courses,
    search_courses,
    filter_courses,
    search_news,
    get_recent_news
)

logger = logging.getLogger(__name__)
tool_logger = logging.getLogger("tool_logs")
tool_logger.setLevel(logging.DEBUG)

# Setup logging directories
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(log_dir, exist_ok=True)

if not tool_logger.handlers:
    file_handler = logging.FileHandler(os.path.join(log_dir, "tool_logs.log"))
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    tool_logger.addHandler(file_handler)

# Add a new debug logger specifically for tool outputs
debug_logger = logging.getLogger("debug_logs")
debug_logger.setLevel(logging.DEBUG)
debug_file_handler = logging.FileHandler(os.path.join(log_dir, "debug_outputs.log"))
debug_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
debug_file_handler.setFormatter(debug_formatter)
debug_logger.addHandler(debug_file_handler)

class ToolBasedChatService:
    """Simplified service that handles conversations with LLM using tool calls"""
    
    def __init__(self, nlp_service=None, professor_service=None, course_service=None, news_service=None, name_service=None):
        tool_logger.info("Initializing SimpleToolBasedChatService")
        self.nlp_service = nlp_service
        self.professor_service = professor_service
        self.course_service = course_service
        self.news_service = news_service
        self.name_service = name_service
        
        # Enhanced system prompt with instructions for all tools
        self.system_prompt = """
You are a university assistant that helps students and faculty find information.

IMPORTANT GUIDELINES:
1. When a user asks about professors or courses taught by professors, use GetProfessorCourses
2. When a user searches for specific courses by topic or content, use SearchCourses
3. When a user asks for courses by year or semester, use FilterCourses
4. When a user asks about university news, use SearchNews or GetRecentNews
5. Always call the appropriate tool before giving an answer

For professor queries:
- If you receive a response with "clarification_needed": true, ask the user if they meant the name in "candidate_match"
- If they confirm, use GetProfessorCourses with the EXACT name from clarification_needed 

For news queries:
- Use SearchNews when the user has specific topics they want to find news about
- Use GetRecentNews when the user just wants the latest news in a category
- Available news categories: internship, thesis, student, distinctions, events, vacancies, general

For course queries:
- Use FilterCourses when the user mentions specific years or semesters
- Use SearchCourses when the user is looking for courses by topic or content

When you receive tool responses with a "formatted_response" or "formatted_courses" or "formatted_news" field, use that formatted content in your response to the user. This content has been professionally formatted for readability and relevance.
Do not change anything in the formatted content.
"""
        
        # Configure available tools
        self.tools = [
            GetProfessorCourses, 
            SearchCourses,
            FilterCourses,
            SearchNews,
            GetRecentNews
        ]
        
        # Simple conversation history for each thread
        self.conversations = {}
        
        # Debug directory for tool outputs
        self.debug_dir = os.path.join(log_dir, "tool_outputs")
        os.makedirs(self.debug_dir, exist_ok=True)
        
        try:
            os.environ["GROQ_API_KEY"] = GROQ_API_KEY
            self.llm = init_chat_model(GROQ_MODEL, model_provider="groq")
            self.llm_with_tools = self.llm.bind_tools(self.tools)
            tool_logger.info(f"Successfully initialized LLM with {len(self.tools)} available tools")
        except Exception as e:
            tool_logger.error(f"Failed to initialize LLM: {str(e)}", exc_info=True)
            self.llm = None
            self.llm_with_tools = None
    
    def _save_debug_output(self, tool_name, args, result):
        """Save tool input and output to debug files"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{tool_name}.json"
        filepath = os.path.join(self.debug_dir, filename)
        
        debug_data = {
            "timestamp": timestamp,
            "tool_name": tool_name,
            "input_args": args,
            "output_result": result
        }
        
        with open(filepath, 'w') as f:
            json.dump(debug_data, f, indent=2)
        
        # Also log to debug log file
        debug_logger.info(f"Tool execution: {tool_name}")
        debug_logger.info(f"Input args: {json.dumps(args)}")
        debug_logger.info(f"Output result: {json.dumps(result)}")
        debug_logger.info("-" * 80)  # Divider for readability
        
        # Estimate token size
        result_str = json.dumps(result)
        estimated_tokens = len(result_str.split()) * 1.3  # Rough approximation
        debug_logger.info(f"Estimated token size of result: ~{int(estimated_tokens)}")
        
        return filepath
    
    def _execute_tool(self, tool_call):
        """Execute a tool based on tool call information"""
        tool_name = tool_call["name"].lower()
        args = tool_call["args"]
        
        tool_logger.info(f"Executing tool: {tool_name} with args: {args}")
        
        # Create formatter instance
        formatter = ResponseFormatter()
        
        result = None
        if tool_name == "getprofessorcourses":
            result = get_professor_courses(
                self,
                self.professor_service, 
                self.name_service, 
                args.get("professor_name", "")
            )
            
            # Format the professor courses result using ResponseFormatter
            if isinstance(result, dict) and "professor_name" in result and "courses" in result:
                formatted_response = formatter.format_professor_courses(
                    result["professor_name"], 
                    result["courses"]
                )
                # Add the formatted response to the result
                result["formatted_response"] = formatted_response
                
        elif tool_name == "SearchCourses":
            result = search_courses(
                self.course_service, 
                args.get("query", ""), 
                args.get("limit", 10)
            )
            # Format the search courses result
            if isinstance(result, dict) and "courses" in result:
                formatted_courses = formatter._format_courses_for_prompt(result["courses"])
                result["formatted_courses"] = formatted_courses
                
        elif tool_name == "filtercourses":
            result = filter_courses(
                self.course_service, 
                args.get("year"), 
                args.get("semester"), 
                args.get("limit", 10)
            )
            
            # Format the filter courses result
            if isinstance(result, dict) and "courses" in result:
                formatted_courses = formatter._format_courses_for_prompt(result["courses"])
                result["formatted_courses"] = formatted_courses
                
        elif tool_name == "searchnews":
            result = search_news(
                self.news_service, 
                args.get("query", ""), 
                args.get("category"), 
                args.get("limit", 10)
            )
            
            # Format the news result
            if isinstance(result, dict) and "news_items" in result:
                # Determine the news intent type based on category
                from models.intent_mappings import IntentType
                category = args.get("category", "general").lower()
                news_intent_mapping = {
                    "internship": IntentType.NEWS_INTERNSHIP,
                    "thesis": IntentType.NEWS_THESIS,
                    "student": IntentType.NEWS_STUDENT,
                    "distinctions": IntentType.NEWS_DISTINCTIONS,
                    "events": IntentType.NEWS_EVENTS,
                    "vacancies": IntentType.NEWS_VACANCIES,
                    "general": IntentType.NEWS_GENERAL
                }
                intent = news_intent_mapping.get(category, IntentType.NEWS_GENERAL)
                formatted_news = formatter._generate_news_fallback(intent, result)
                result["formatted_response"] = formatted_news
                
        elif tool_name == "getrecentnews":
            result = get_recent_news(
                self.news_service, 
                args.get("category", "general"), 
                args.get("limit", 5)
            )
            
            # Format the recent news result
            if isinstance(result, dict) and "news_items" in result:
                from models.intent_mappings import IntentType
                category = args.get("category", "general").lower()
                news_intent_mapping = {
                    "internship": IntentType.NEWS_INTERNSHIP,
                    "thesis": IntentType.NEWS_THESIS,
                    "student": IntentType.NEWS_STUDENT,
                    "distinctions": IntentType.NEWS_DISTINCTIONS,
                    "events": IntentType.NEWS_EVENTS,
                    "vacancies": IntentType.NEWS_VACANCIES,
                    "general": IntentType.NEWS_GENERAL
                }
                intent = news_intent_mapping.get(category, IntentType.NEWS_GENERAL)
                formatted_news = formatter._generate_news_fallback(intent, result)
                result["formatted_response"] = formatted_news
                
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
        
        # Save to debug file and log
        debug_file = self._save_debug_output(tool_name, args, result)
        tool_logger.info(f"Tool output saved to: {debug_file}")
        
        return result
    
    def _estimate_messages_token_count(self, messages):
        """Provide a rough estimate of token count for debugging"""
        # This is a very rough approximation
        total_chars = sum(len(str(msg.content)) for msg in messages)
        # Roughly 4 characters per token on average
        estimated_tokens = total_chars / 4
        return int(estimated_tokens)
    
    def process_message(self, message: str, thread_id: str = "default") -> Dict:
        """Process a user message and handle any tool calls"""
        if not self.llm_with_tools:
            return {"message": "LLM not initialized"}
        
        formatter = ResponseFormatter()
        # Initialize or get conversation history
        if thread_id not in self.conversations:
            self.conversations[thread_id] = [SystemMessage(content=self.system_prompt)]
        
        messages = self.conversations[thread_id]
        
        # Add user message
        messages.append(HumanMessage(content=message))
        
        # Log estimated token count before processing
        token_estimate = self._estimate_messages_token_count(messages)
        tool_logger.info(f"Estimated token count before processing: ~{token_estimate}")
        debug_logger.info(f"Starting conversation processing with estimated ~{token_estimate} tokens")
        
        try:
            # Get initial response from LLM
            tool_logger.info("Sending messages to LLM for initial response")
            ai_msg = self.llm_with_tools.invoke(messages)
            messages.append(ai_msg)
            
            # Debug info about the response
            debug_logger.info(f"LLM Response: {ai_msg.content[:200]}...")
            
            # Handle tool calls if present
            if hasattr(ai_msg, 'tool_calls') and ai_msg.tool_calls:
                num_tool_calls = len(ai_msg.tool_calls)
                tool_logger.info(f"Message has {num_tool_calls} tool calls")
                debug_logger.info(f"Processing {num_tool_calls} tool calls")
                
                # Process each tool call
                for i, tool_call in enumerate(ai_msg.tool_calls):
                    tool_logger.info(f"Processing tool call {i+1}/{num_tool_calls}: {tool_call['name']}")
                    
                    # Execute the tool
                    tool_result = self._execute_tool(tool_call)
                    
                    # Truncate large results for token management
                    truncated_result = self._maybe_truncate_result(tool_result)
                    if truncated_result != tool_result:
                        debug_logger.warning("Tool result was truncated to reduce token count")
                    
                    
                    # Add tool message to conversation
                    tool_msg = ToolMessage(
                        content=json.dumps(truncated_result),
                        name=tool_call["name"],
                        tool_call_id=tool_call.get("id", "")
                    )
                    messages.append(tool_msg)
                    
                    # Log token estimate after each tool call
                    token_estimate = self._estimate_messages_token_count(messages)
                    debug_logger.info(f"Token estimate after tool call {i+1}: ~{token_estimate}")
                    
                    # If we're approaching the limit, break
                    if token_estimate > 5000:  # Set a safe threshold below Groq's 6000 limit
                        debug_logger.warning(f"Token count estimate (~{token_estimate}) approaching limit, breaking processing")
                        break
                
                # Get final response with tool results
                tool_logger.info("Sending messages to LLM for final response")
                debug_logger.info(f"Final token estimate before response: ~{token_estimate}")
                
                # If we're very close to the limit, trim conversation history
                if token_estimate > 5000:
                    debug_logger.warning("Token count too high, trimming conversation")
                    # Keep system message, last user message, and most recent tool results
                    system_msg = messages[0]
                    user_msg = messages[-3]  # The user message before the tool response
                    tool_msg = messages[-1]  # Most recent tool message
                    
                    # Reset messages
                    messages = [system_msg, user_msg, tool_msg]
                    token_estimate = self._estimate_messages_token_count(messages)
                    debug_logger.info(f"Trimmed conversation to ~{token_estimate} tokens")
                
                final_msg = self.llm_with_tools.invoke(messages)
                messages.append(final_msg)
                return {"message": final_msg.content}
            else:
                # No tool calls, return the initial response
                return {"message": ai_msg.content}
                
        except Exception as e:
            tool_logger.error(f"Error processing message: {str(e)}", exc_info=True)
            debug_logger.error(f"Error details: {str(e)}", exc_info=True)
            return {"message": f"Error processing message: {str(e)}"}
    
    def _maybe_truncate_result(self, result):
        """Truncate large tool results to prevent token limit issues"""
        # Convert to string to check size
        result_str = json.dumps(result)
        
        # If result is small, return as is
        if len(result_str) < 2000:
            return result
        
        # For course or news lists, truncate the items
        if isinstance(result, dict):
            if "courses" in result and isinstance(result["courses"], list) and len(result["courses"]) > 3:
                debug_logger.info(f"Truncating course list from {len(result['courses'])} to 3 items")
                result["courses"] = result["courses"][:3]
                result["_truncated"] = True
                
            if "news_items" in result and isinstance(result["news_items"], list) and len(result["news_items"]) > 3:
                debug_logger.info(f"Truncating news list from {len(result['news_items'])} to 3 items")
                result["news_items"] = result["news_items"][:3]
                result["_truncated"] = True
                
            # Truncate long content fields in items
            if "courses" in result and isinstance(result["courses"], list):
                for course in result["courses"]:
                    if "content" in course and isinstance(course["content"], str) and len(course["content"]) > 500:
                        course["content"] = course["content"][:500] + "... [content truncated]"
                        
            if "news_items" in result and isinstance(result["news_items"], list):
                for item in result["news_items"]:
                    if "content" in item and isinstance(item["content"], str) and len(item["content"]) > 500:
                        item["content"] = item["content"][:500] + "... [content truncated]"
        
        return result