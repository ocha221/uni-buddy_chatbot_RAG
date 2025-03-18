class IntentType:
    """Intent type constants for query classification"""

    PROFESSOR_COURSES = "professor_courses"
    COURSE_SEARCH = "course_search"
    COURSE_FILTERING = "course_filtering"
    NEWS_INTERNSHIP = "news_internship"
    NEWS_THESIS = "news_ptixiaki"
    NEWS_STUDENT = "news_student"
    NEWS_DISTINCTIONS = "news_distinctions"
    NEWS_EVENTS = "news_events"
    NEWS_VACANCIES = "news_vacancies"
    NEWS_GENERAL = "news_general"
    GENERAL_INFO = "general_info"
    UNKNOWN = "unknown"
    BANNED_QUERY = "banned_query"  # TODO


NEWS_INTENT_MAPPING = {
    IntentType.NEWS_INTERNSHIP: "type_internship_related",
    IntentType.NEWS_STUDENT: "type_student_related",
    IntentType.NEWS_DISTINCTIONS: "type_distinctions_awards",
    IntentType.NEWS_EVENTS: "type_events_activities",
    IntentType.NEWS_VACANCIES: "type_vacancies",
    IntentType.NEWS_GENERAL: "type_general",
}
