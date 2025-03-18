import logging
import uuid
from datetime import datetime, timedelta
from models.intent_mappings import IntentType, NEWS_INTENT_MAPPING

logger = logging.getLogger(__name__)


# ?TODO todo dtood todo todo
class ChatSession:
    """Represents a single chat conversation session"""

    def __init__(self, session_id=None):
        self.session_id = session_id or str(uuid.uuid4())
        self.messages = []
        self.context = {
            "active_professor": None,
            "active_courses": None,
            "active_news_category": None,
            "awaiting_clarification": False,
            "clarification_type": None,
            "original_query": None,
            "last_intent": None,
        }
        self.created_at = datetime.now()
        self.last_activity = datetime.now()

    def add_message(self, role, content, metadata=None):
        """Add a message to the conversation history"""
        message = {
            "role": role,  # ? "user" or "assistant"
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }

        if metadata:
            message["metadata"] = metadata

        self.messages.append(message)
        self.last_activity = datetime.now()
        return message

    def get_recent_messages(self, count=5):
        """Get the most recent messages"""
        return self.messages[-count:] if len(self.messages) > 0 else []

    def get_context(self, key=None):
        """Get context value or entire context dictionary"""
        if key:
            return self.context.get(key)
        return self.context

    def update_context(self, key, value):
        """Update the conversation context"""
        self.context[key] = value
        return self.context


class ChatService:
    """Manages chat sessions and multi-turn conversations"""

    def __init__(self, nlp_service):
        self.sessions = {}  # ? session_id -> ChatSession
        self.nlp_service = nlp_service
        self.session_expiry_minutes = 30

    def get_session(self, session_id):
        """Get an existing session or None if not found"""
        session = self.sessions.get(session_id)

        # ? Check for expired session
        if session and (datetime.now() - session.last_activity).total_seconds() > (
            self.session_expiry_minutes * 60
        ):
            logger.info(f"Session {session_id} has expired")
            del self.sessions[session_id]
            return None

        return session

    def create_session(self):
        """Create a new chat session"""
        session = ChatSession()
        self.sessions[session.session_id] = session
        logger.info(f"Created new chat session: {session.session_id}")
        return session

    def process_message(self, session_id, message, **services):
        """
        Process a user message in the context of a session

        Args:
            session_id: Chat session ID or None for new session
            message: User's message text
            **services: Service dependencies (news_service, professor_service, etc.)

        Returns:
            dict with session_id, message, query_type, data
        """
        # ? Get or create session
        session = self.get_session(session_id)
        if not session:
            session = self.create_session()
            session_id = session.session_id

        # ? Add user message to history
        session.add_message("user", message)

        # ? Handle clarification response if we're awaiting one
        if session.get_context("awaiting_clarification"):
            response_data, response_message, query_type = self._handle_clarification(
                session, message, **services
            )
        else:
            # ? Check if this is a follow-up question related to previous context
            is_followup = self._is_followup_question(message, session)

            if is_followup:
                # ? Process with context from previous interaction
                response_data, response_message, query_type = self._process_followup(
                    session, message, **services
                )
            else:
                # ? Process as a new query with full unified_search functionality
                query_intent = self.nlp_service.analyze_query_intent(message)
                response_data, response_message, query_type = (
                    self.nlp_service.process_unified_query(
                        message, query_intent, **services
                    )
                )

                # ? Update session context based on the new query
                self._update_session_context(
                    session, query_type, response_data, query_intent
                )

        # ? Add assistant response to history
        session.add_message(
            "assistant",
            response_message,
            {"query_type": query_type, "data": response_data},
        )

        return {
            "session_id": session_id,
            "message": response_message,
            "query_type": query_type,
            "data": response_data,
        }

    def _handle_clarification(self, session, message, **services):
        """Handle response to a clarification request"""
        clarification_type = session.get_context("clarification_type")
        original_query = session.get_context("original_query")

        # Reset clarification state
        session.update_context("awaiting_clarification", False)
        session.update_context("clarification_type", None)

        message_lower = message.lower()
        affirmative = any(
            word in message_lower
            for word in ["yes", "yep", "yeah", "correct", "right", "that's it"]
        )

        if clarification_type == "professor_name":
            candidate_match = session.get_context("candidate_match")

            if affirmative:
                # User confirmed the professor name match
                professor_service = services.get("professor_service")
                name_service = services.get("name_service")

                if professor_service and name_service and candidate_match:
                    original_name = self.nlp_service.extract_professor_name(
                        original_query
                    )
                    if original_name and original_name != candidate_match:
                        name_service.add_name_variation(candidate_match, original_name)

                    courses = professor_service.get_courses_by_professor(
                        candidate_match
                    )

                    if courses:
                        session.update_context("active_professor", candidate_match)

                        course_list = []
                        for course in courses:
                            course_list.append(
                                {
                                    "course_code": course["course_code"],
                                    "title": course["metadata"].get("title", "Unknown"),
                                    "year": course["metadata"].get("year", 0),
                                    "semester": course["metadata"].get("semester", 0),
                                    "ects": course["metadata"].get("ects"),
                                    "document": course["document"],
                                }
                            )

                        context_data = {
                            "professor_name": candidate_match,
                            "courses": course_list,
                        }

                        session.update_context("active_courses", course_list)

                        response_message = self.nlp_service.generate_response(
                            IntentType.PROFESSOR_COURSES, context_data, original_query
                        )

                        return (
                            context_data,
                            response_message,
                            IntentType.PROFESSOR_COURSES,
                        )

                    return (
                        None,
                        f"I couldn't find any courses for Professor {candidate_match}.",
                        "no_results",
                    )
                else:

                    return (
                        None,
                        "Sorry, I couldn't process that request properly.",
                        "error",
                    )
            else:

                return (
                    None,
                    "Could you please provide the full name of the professor you're looking for?",
                    "clarification_request",
                )

        query_intent = self.nlp_service.analyze_query_intent(message)
        return self.nlp_service.process_unified_query(message, query_intent, **services)

    def _is_followup_question(self, message, session):
        """Determine if the message is a follow-up question based on session context"""
        message_lower = message.lower()

        # ? Get previous context
        active_professor = session.get_context("active_professor")
        active_courses = session.get_context("active_courses")
        last_intent = session.get_context("last_intent")

        # ? Check for follow-up indicators
        followup_phrases = [
            "what about",
            "how about",
            "tell me more",
            "and also",
            "what else",
            "can you elaborate",
            "show me",
            "what are",
        ]

        has_followup_phrase = any(
            phrase in message_lower for phrase in followup_phrases
        )

        # ? Check for pronouns and short queries that likely reference context
        has_pronoun = any(
            word in message_lower.split()
            for word in ["it", "they", "them", "those", "that", "this", "these"]
        )
        is_short_query = len(message.split()) <= 5

        # ? Check for specific follow-up patterns
        has_course_reference = (
            "course" in message_lower
            or "class" in message_lower
            or "subject" in message_lower
        )
        has_professor_reference = (
            "professor" in message_lower
            or "teacher" in message_lower
            or "instructor" in message_lower
        )

        # ? Look for references to previous context
        references_previous = False

        if active_professor and (
            active_professor.lower() in message_lower
            or has_professor_reference
            or (has_pronoun and last_intent == IntentType.PROFESSOR_COURSES)
        ):
            references_previous = True

        if active_courses and (
            has_course_reference
            or (
                has_pronoun
                and (
                    last_intent == IntentType.COURSE_SEARCH
                    or last_intent == IntentType.COURSE_FILTERING
                )
            )
        ):
            references_previous = True

        return (
            has_followup_phrase or has_pronoun or is_short_query
        ) and references_previous

    def _process_followup(self, session, message, **services):
        """Process a follow-up question using session context"""
        active_professor = session.get_context("active_professor")
        active_courses = session.get_context("active_courses")
        last_intent = session.get_context("last_intent")

        # ? Determine what the follow-up is about
        if active_professor and last_intent == IntentType.PROFESSOR_COURSES:
            # ? Follow-up about a professor's courses
            if "semester" in message.lower() or "year" in message.lower():
                # ? User is likely asking about courses in a specific semester/year
                time_info = self.nlp_service.extract_time_info_from_query(message)

                if time_info and active_courses:
                    year, semester, _ = time_info

                    # ? Filter the existing courses based on year/semester
                    filtered_courses = active_courses

                    if year is not None:
                        filtered_courses = [
                            c for c in filtered_courses if c.get("year") == year
                        ]

                    if semester is not None:
                        filtered_courses = [
                            c for c in filtered_courses if c.get("semester") == semester
                        ]

                    if filtered_courses:
                        context_data = {
                            "professor_name": active_professor,
                            "courses": filtered_courses,
                        }

                        time_desc = ""
                        if year is not None and semester is not None:
                            time_desc = f"Year {year}, Semester {semester}"
                        elif year is not None:
                            time_desc = f"Year {year}"
                        elif semester is not None:
                            time_desc = f"Semester {semester}"

                        response_message = self.nlp_service.generate_response(
                            IntentType.PROFESSOR_COURSES,
                            context_data,
                            f"What courses does {active_professor} teach in {time_desc}?",
                        )

                        return (
                            context_data,
                            response_message,
                            IntentType.PROFESSOR_COURSES,
                        )

                    return (
                        None,
                        f"Professor {active_professor} doesn't teach any courses in the specified time period.",
                        "no_results",
                    )

            # ? Might be asking for details about specific courses
            professor_service = services.get("professor_service")

            if professor_service:
                courses = professor_service.get_courses_by_professor(active_professor)

                if courses:
                    context_data = {
                        "professor_name": active_professor,
                        "courses": [c for c in courses],
                    }

                    # ? For follow-up queries, combine the original context with the new query
                    combined_query = f"For Professor {active_professor}: {message}"
                    response_message = self.nlp_service.generate_response(
                        IntentType.PROFESSOR_COURSES, context_data, combined_query
                    )

                    return context_data, response_message, IntentType.PROFESSOR_COURSES

        elif (
            last_intent in [IntentType.COURSE_SEARCH, IntentType.COURSE_FILTERING]
            and active_courses
        ):
            # ? Follow-up about courses previously searched
            course_service = services.get("course_service")

            if (
                "professor" in message.lower()
                or "instructor" in message.lower()
                or "who teaches" in message.lower()
            ):
                # ? User is asking about who teaches these courses
                if active_courses and len(active_courses) > 0:
                    course_codes = [
                        course.get("course_code")
                        for course in active_courses
                        if course.get("course_code")
                    ]

                    professor_info = {}
                    if course_service and hasattr(
                        course_service, "get_professors_by_courses"
                    ):
                        professor_info = course_service.get_professors_by_courses(
                            course_codes
                        )

                    context_data = {
                        "courses": active_courses,
                        "professors": professor_info,
                    }

                    # ? Generate custom response about professors
                    response_message = (
                        f"Here's information about who teaches these courses:\n\n"
                    )

                    for course in active_courses:
                        course_code = course.get("course_code")
                        title = course.get("title", "Unknown course")

                        professors = professor_info.get(course_code, [])
                        if professors:
                            response_message += f"• {title} ({course_code}) is taught by {', '.join(professors)}\n"
                        else:
                            response_message += f"• {title} ({course_code}) - instructor information not available\n"

                    return context_data, response_message, "course_instructors"

            # ? General follow-up about courses, might be asking for more details
            if active_courses and len(active_courses) > 0:
                # ? Try to determine if they're asking about a specific course
                for course in active_courses:
                    title_words = course.get("title", "").lower().split()
                    code = course.get("course_code", "").lower()

                    # ? Check if the message mentions this specific course
                    if code in message.lower() or any(
                        word in message.lower() for word in title_words if len(word) > 3
                    ):
                        # ? User is likely asking about this specific course
                        if course_service:
                            detailed_course = course_service.get_course(
                                course.get("course_code")
                            )

                            if detailed_course:
                                context_data = {"courses": [detailed_course]}

                                response_message = self.nlp_service.generate_response(
                                    IntentType.COURSE_SEARCH,
                                    context_data,
                                    f"Tell me more about {course.get('title')}",
                                )

                                return (
                                    context_data,
                                    response_message,
                                    IntentType.COURSE_SEARCH,
                                )

                # ? If no specific course was identified, treat as general follow-up
                context_data = {"courses": active_courses}

                response_message = self.nlp_service.generate_response(
                    last_intent, context_data, message  # ? Use the original message
                )

                return context_data, response_message, last_intent

        # ? If we couldn't process as a follow-up, fall back to regular processing
        query_intent = self.nlp_service.analyze_query_intent(message)
        return self.nlp_service.process_unified_query(message, query_intent, **services)

    def _update_session_context(
        self, session, query_type, response_data, query_intent=None
    ):
        """Update session context based on query results"""
        # ? Save the intent for future reference
        if query_intent:
            session.update_context("last_intent", query_intent)

        # ? Save professor information if this was a professor query
        if query_type == IntentType.PROFESSOR_COURSES and response_data:
            if "professor_name" in response_data:
                session.update_context(
                    "active_professor", response_data["professor_name"]
                )

            if "courses" in response_data:
                session.update_context("active_courses", response_data["courses"])

        # ? Save course information if this was a course query
        elif (
            query_type in [IntentType.COURSE_SEARCH, IntentType.COURSE_FILTERING]
            and response_data
        ):
            if "courses" in response_data:
                session.update_context("active_courses", response_data["courses"])

        # ? Save news category if this was a news query
        elif query_type in NEWS_INTENT_MAPPING.values() and response_data:
            news_category = query_type
            session.update_context("active_news_category", news_category)

            if "news_items" in response_data:
                session.update_context("active_news", response_data["news_items"])
