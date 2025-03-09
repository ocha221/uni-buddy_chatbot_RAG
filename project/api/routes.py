# api/routes.py
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from typing import List, Optional
from pydantic import BaseModel
import uvicorn
import logging
from logging.handlers import RotatingFileHandler
import threading
import schedule
import time
import os

from services.course_service import CourseService
from services.professor_service import ProfessorService
from services.name_service import NameService
from services.nlp_service import NLPService
from services.news_service import NewsService
from models.intent_mappings import IntentType, NEWS_INTENT_MAPPING
from db.collections import Collections

from services.refresh_service import RefreshService

log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "api_service.log")

file_handler = RotatingFileHandler(log_file, maxBytes=10485760, backupCount=5)
file_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
file_handler.setFormatter(file_formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger = logging.getLogger(__name__)

app = FastAPI(title="University Information System API")

# * scheduler
scheduler_thread = None
scheduler_running = False
refresh_interval = 12


def get_collections():
    return Collections()


def get_name_service(collections=Depends(get_collections)):
    nlp_service = NLPService()
    return NameService(collections=collections, nlp_service=nlp_service)


def get_news_service(collections=Depends(get_collections)):
    return NewsService(collections=collections)


def get_course_service(collections=Depends(get_collections)):
    return CourseService(collections=collections)


def get_professor_service(
    collections=Depends(get_collections), name_service=Depends(get_name_service)
):
    professor_service = ProfessorService(
        collections=collections, name_service=name_service
    )
    return professor_service


def get_nlp_service():
    return NLPService()


def get_refresh_service(
    course_service=Depends(get_course_service),
    professor_service=Depends(get_professor_service),
    name_service=Depends(get_name_service),
    news_service=Depends(get_news_service),
):
    return RefreshService(
        course_service=course_service,
        news_service=news_service,
        professor_service=professor_service,
        name_service=name_service,
    )


collections = Collections()
nlp_service = NLPService()
name_service = NameService(collections, nlp_service)
course_service = CourseService(collections)
professor_service = ProfessorService(collections, name_service)
news_service = NewsService(collections)

# * services
professor_service.set_course_service(course_service)
course_service.set_professor_service(professor_service)


def run_scheduler():
    """Run the scheduler loop"""
    global scheduler_running
    while scheduler_running:
        schedule.run_pending()
        time.sleep(60)


def start_scheduler(interval=12):
    """Start the scheduler thread"""
    global scheduler_thread, scheduler_running, refresh_interval

    if scheduler_thread and scheduler_thread.is_alive():
        logger.info("Scheduler already running, updating schedule instead")
        schedule.clear()
        refresh_service = RefreshService(
            course_service=course_service,
            news_service=news_service,
            professor_service=professor_service,
            name_service=name_service,
        )
        schedule.every(interval).hours.do(refresh_service.refresh_all)
        logger.info(f"Updated refresh schedule: every {interval} hours")
        return True

    refresh_interval = interval
    schedule.clear()

    if interval > 0:
        refresh_service = RefreshService(
            course_service=course_service,
            news_service=news_service,
            professor_service=professor_service,
            name_service=name_service,
        )
        schedule.every(interval).hours.do(refresh_service.refresh_all)
        logger.info(f"Configured refresh schedule: every {interval} hours")

        scheduler_running = True
        scheduler_thread = threading.Thread(target=run_scheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()
        logger.info("Refresh scheduler started")
    else:
        logger.info("Automatic refresh disabled (interval set to 0)")

    return True


def stop_scheduler():
    """Stop the scheduler thread"""
    global scheduler_running
    scheduler_running = False
    schedule.clear()
    logger.info("Refresh scheduler stopped")


app.mount("/static", StaticFiles(directory="project/site/"), name="static")


@app.on_event(
    "startup"
)  # TODO lifespan handler alla to vlepoume afto leitourggei mia xara
async def startup_event():
    logger.info("API server starting up")
    start_scheduler(refresh_interval)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("API server shutting down")
    stop_scheduler()


class RefreshResponse(BaseModel):
    success: bool
    message: str
    courses: int = 0
    news: int = 0
    professors: int = 0


class CourseResponse(BaseModel):
    course_code: str
    title: str
    year: int
    semester: int
    ects: Optional[int] = None
    document: str


class ProfessorResponse(BaseModel):
    name: str
    courses: List[CourseResponse]


class QueryRequest(BaseModel):
    query: str


@app.post("/api/refresh/courses", response_model=RefreshResponse)
async def refresh_courses(background_tasks: BackgroundTasks):
    """Refresh courses collection with latest data"""

    def do_refresh():
        try:
            global_refresh_service = RefreshService(
                course_service=course_service,
                news_service=news_service,
                professor_service=professor_service,
                name_service=name_service,
            )
            count = global_refresh_service.refresh_courses(reset=True)
            logger.info(f"Background refresh completed: {count} courses updated")
        except Exception as e:
            logger.error(f"Background refresh error: {str(e)}")

    background_tasks.add_task(do_refresh)
    return RefreshResponse(
        success=True,
        message="Course refresh started in background",
    )


@app.post("/api/refresh/news", response_model=RefreshResponse)
async def refresh_news(background_tasks: BackgroundTasks):
    """Refresh news collection with latest data"""

    def do_refresh():
        try:
            global_refresh_service = RefreshService(
                course_service=course_service,
                news_service=news_service,
                professor_service=professor_service,
                name_service=name_service,
            )
            count = global_refresh_service.refresh_news(reset=True)
            logger.info(f"Background refresh completed: {count} news items updated")
        except Exception as e:
            logger.error(f"Background refresh error: {str(e)}")

    background_tasks.add_task(do_refresh)
    return RefreshResponse(
        success=True,
        message="News refresh started in background",
    )


@app.post("/api/refresh/professors", response_model=RefreshResponse)
async def refresh_professors(background_tasks: BackgroundTasks):
    """Rebuild professor data from courses"""

    def do_refresh():
        try:
            global_refresh_service = RefreshService(
                course_service=course_service,
                news_service=news_service,
                professor_service=professor_service,
                name_service=name_service,
            )
            count = global_refresh_service.refresh_professors(consolidate=True)
            logger.info(f"Background refresh completed: {count} professors updated")
        except Exception as e:
            logger.error(f"Background refresh error: {str(e)}")

    background_tasks.add_task(do_refresh)
    return RefreshResponse(
        success=True,
        message="Professor refresh started in background",
    )


@app.post("/api/refresh/all", response_model=RefreshResponse)
async def refresh_all(background_tasks: BackgroundTasks):
    """Refresh all collections with latest data"""

    def do_refresh():
        try:
            global_refresh_service = RefreshService(
                course_service=course_service,
                news_service=news_service,
                professor_service=professor_service,
                name_service=name_service,
            )
            results = global_refresh_service.refresh_all(reset=True)
            logger.info(f"Background full refresh completed: {results}")
        except Exception as e:
            logger.error(f"Background full refresh error: {str(e)}")

    background_tasks.add_task(do_refresh)
    return RefreshResponse(
        success=True,
        message="Full database refresh started in background",
    )


@app.post("/api/professors/consolidate", response_model=RefreshResponse)
async def consolidate_professors(background_tasks: BackgroundTasks):
    """Consolidate professor names"""

    def do_consolidate():
        try:
            count = professor_service.consolidate_professor_names(interactive=False)
            logger.info(
                f"Background consolidation completed: {count} professor groups consolidated"
            )
        except Exception as e:
            logger.error(f"Background consolidation error: {str(e)}")

    background_tasks.add_task(do_consolidate)
    return RefreshResponse(
        success=True,
        message="Professor name consolidation started in background",
    )


@app.post("/api/schedule", response_model=RefreshResponse)
async def set_schedule(hours: int = 12):
    """Set the refresh schedule interval"""
    start_scheduler(hours)
    return RefreshResponse(
        success=True,
        message=f"Refresh schedule set to every {hours} hours",
    )


@app.get("/")
async def root():
    return FileResponse("project/site/index.html")


@app.get("/production")
async def production():
    return FileResponse("project/site/index-production.html")


@app.get("/admin")
async def admin():
    admin_file = "/Users/chai/modular_Rag/project/api/admin.html"
    return FileResponse(admin_file)


@app.get("/courses/search", response_model=List[CourseResponse])
async def search_courses(query: str, limit: int = Query(5, ge=1, le=20)):
    """Search courses by content"""
    results = course_service.search_courses(query, limit)
    if not results or not results["ids"][0]:
        return []

    courses = []
    for i in range(len(results["ids"][0])):
        courses.append(
            CourseResponse(
                course_code=results["ids"][0][i],
                title=results["metadatas"][0][i].get("title", "Unknown"),
                year=results["metadatas"][0][i].get("year", 0),
                semester=results["metadatas"][0][i].get("semester", 0),
                ects=results["metadatas"][0][i].get("ects"),
                document=results["documents"][0][i],
            )
        )
    return courses


@app.get("/courses/filter")
async def filter_courses(
    year: Optional[int] = None,
    semester: Optional[int] = None,
    limit: int = Query(10, ge=1, le=100),
):
    """Filter courses by year and semester"""
    filters = {}
    if year is not None:
        filters["year"] = year
    if semester is not None:
        filters["semester"] = semester

    if year is not None or semester is not None:
        limit = 27

    results = course_service.filter_courses(filters, limit)
    if not results or not results["ids"][0]:
        return []

    courses = []
    for i in range(len(results["ids"][0])):
        courses.append(
            CourseResponse(
                course_code=results["ids"][0][i],
                title=results["metadatas"][0][i].get("title", "Unknown"),
                year=results["metadatas"][0][i].get("year", 0),
                semester=results["metadatas"][0][i].get("semester", 0),
                ects=results["metadatas"][0][i].get("ects"),
                document=results["documents"][0][i],
            )
        )
    return courses


@app.get("/courses/{course_code}", response_model=CourseResponse)
async def get_course(course_code: str):
    """Get course by code"""
    course = course_service.get_course(course_code)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    return CourseResponse(
        course_code=course_code,
        title=course["metadata"].get("title", "Unknown"),
        year=course["metadata"].get("year", 0),
        semester=course["metadata"].get("semester", 0),
        ects=course["metadata"].get("ects"),
        document=course["document"],
    )


@app.get("/professors/{name}/courses", response_model=ProfessorResponse)
async def get_professor_courses(name: str):
    """Get courses taught by a professor"""
    courses = professor_service.get_courses_by_professor(name)
    if not courses:
        raise HTTPException(
            status_code=404, detail="Professor not found or has no courses"
        )

    canonical_name = name_service.find_canonical_name(name) or name

    course_list = []
    for course in courses:
        course_list.append(
            CourseResponse(
                course_code=course["course_code"],
                title=course["metadata"].get("title", "Unknown"),
                year=course["metadata"].get("year", 0),
                semester=course["metadata"].get("semester", 0),
                ects=course["metadata"].get("ects"),
                document=course["document"],
            )
        )

    return ProfessorResponse(name=canonical_name, courses=course_list)


@app.get("/professors", response_model=List[dict])
async def get_all_professors():
    """Get all professors"""
    all_professors = professor_service.professor_collection.get()
    professors = []
    for i, metadata in enumerate(all_professors["metadatas"]):
        if "professor_name" in metadata:
            professors.append({"name": metadata["professor_name"]})
    return professors


@app.post("/professors/add-variation")
async def add_professor_variation(canonical_name: str, variation: str):
    """Add a name variation for a professor"""
    success = name_service.add_name_variation(canonical_name, variation)
    return {"success": success}


@app.post("/professors/extract")
async def extract_professor_name(request: QueryRequest):
    """Extract professor name from query"""
    extracted_name = nlp_service.extract_professor_name(request.query)
    return {"query": request.query, "extracted_name": extracted_name}


@app.post("/search/unified")
async def unified_search(request: QueryRequest):
    """Unified search endpoint that handles different query types"""
    query = request.query.strip()
    query_intent = nlp_service.analyze_query_intent(query)
    logger.info(f"Query: '{query}' classified as '{query_intent}'")
    # TODO add like
    # TODO logging and stuff, print to file when banned q's or something. can also log like ip etc/device metadata
    # TODO eclass stuff if logged in? やばいいい
    if query_intent == IntentType.BANNED_QUERY:
        return {
            "query_type": "banned_query",
            "data": None,
            "message": "Query is not allowed.",
        }
    if query_intent == IntentType.UNKNOWN:
        return {
            "query_type": "unknown",
            "data": None,
            "message": "Sorry! Can you please rephrase your question?",
        }
    if query_intent == IntentType.PROFESSOR_COURSES:
        professor_name = nlp_service.extract_professor_name(query)
        if professor_name:
            try:
                courses = professor_service.get_courses_by_professor(professor_name)
                if courses:
                    canonical_name = (
                        name_service.find_canonical_name(professor_name)
                        or professor_name
                    )
                    course_list = format_professor_courses(courses)

                    return {
                        "query_type": query_intent,
                        "data": {
                            "professor_name": canonical_name,
                            "courses": course_list,
                        },
                        "natural_response": generate_professor_courses_response(
                            canonical_name, course_list
                        ),
                    }
            except Exception as e:
                logger.error(f"Error processing professor query: {str(e)}")

    if query_intent in NEWS_INTENT_MAPPING:
        results = news_service.search_news(query, query_intent=query_intent, limit=10)
        if results and results.get("documents") and results["documents"][0]:
            news_items = []
            for i in range(len(results["documents"][0])):
                news_items.append(
                    {
                        "content": results["documents"][0][i],
                        "metadata": (
                            results["metadatas"][0][i]
                            if "metadatas" in results and results["metadatas"][0]
                            else {}
                        ),
                    }
                )

            return {
                "query_type": query_intent,
                "data": {"news_items": news_items},
                "natural_response": generate_news_response(query_intent, news_items),
            }

    if query_intent == IntentType.COURSE_FILTERING:
        # TODO llm that pulls like year/semester data :)
        results = course_service.search_courses(query, 10)
        if results and results["ids"][0]:
            courses = format_course_results(results)
            return {"query_type": query_intent, "data": courses}

    results = course_service.search_courses(query, 10)
    if not results or not results["ids"][0]:
        return {
            "query_type": "no_results",
            "data": None,
            "message": "No results found for your query.",
        }

    courses = format_course_results(results)
    return {"query_type": IntentType.COURSE_SEARCH, "data": courses}


def format_course_results(results):  #?
    """Format course search results into a consistent structure"""
    courses = []
    for i in range(len(results["ids"][0])):
        courses.append(
            {
                "course_code": results["ids"][0][i],
                "title": results["metadatas"][0][i].get("title", "Unknown"),
                "year": results["metadatas"][0][i].get("year", 0),
                "semester": results["metadatas"][0][i].get("semester", 0),
                "ects": results["metadatas"][0][i].get("ects"),
                "document": results["documents"][0][i],
            }
        )
    return courses


def format_professor_courses(courses):
    """Format professor courses into a consistent structure"""
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
    return course_list


def generate_professor_courses_response(professor_name, courses):
    """Generate a natural language response about professor courses"""
    if not courses:
        return f"I couldn't find any courses taught by Professor {professor_name}."

    # Group courses by year and semester
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


def generate_news_response(intent, news_items):
    """Generate a natural language response for news queries"""
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

@app.get("/api/printnews")
async def print_all_news():
    """Print all news entries in the collection"""
    count = news_service.print_all_news()
    if count == 0:
        return {"message": "No news entries found"}
    return {"message": f"Printed {count} news entries"}


def start_server(host="0.0.0.0", port=8000, interval=12):
    """Start the API server with refresh scheduling"""
    global refresh_interval
    refresh_interval = interval
    logger.info(
        f"Starting API server on {host}:{port} with refresh interval of {interval} hours"
    )
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()



#TODO move all the response stuff to nlp_service / ta antoistixa genika