# api/routes.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from typing import List, Optional
from pydantic import BaseModel
from services.course_service import CourseService
from services.professor_service import ProfessorService
from services.name_service import NameService
from services.nlp_service import NLPService
from db.collections import Collections
import os

app = FastAPI(title="University Information System API")

app.mount("/static", StaticFiles(directory="project/site"), name="static")

@app.get("/")
async def root():
    return FileResponse("project/site/index.html")

@app.get("/production")
async def production():
    return FileResponse("project/site/index-production.html")

# Initialize services
collections = Collections()
nlp_service = NLPService()
name_service = NameService(collections, nlp_service)
course_service = CourseService(collections)
professor_service = ProfessorService(collections, name_service)

# Set up service references (to avoid circular dependencies)
professor_service.set_course_service(course_service)
course_service.set_professor_service(professor_service)

# Models
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

# Routes
@app.get("/courses/search", response_model=List[CourseResponse])
async def search_courses(query: str, limit: int = Query(5, ge=1, le=20)):
    """Search courses by content"""
    results = course_service.search_courses(query, limit)
    if not results or not results["ids"][0]:
        return []
        
    courses = []
    for i in range(len(results["ids"][0])):
        courses.append(CourseResponse(
            course_code=results["ids"][0][i],
            title=results["metadatas"][0][i].get("title", "Unknown"),
            year=results["metadatas"][0][i].get("year", 0),
            semester=results["metadatas"][0][i].get("semester", 0),
            ects=results["metadatas"][0][i].get("ects"),
            document=results["documents"][0][i]
        ))
    return courses

@app.get("/courses/filter")
async def filter_courses(
    year: Optional[int] = None,
    semester: Optional[int] = None,
    limit: int = Query(10, ge=1, le=100)
):
    """Filter courses by year and semester"""
    filters = {}
    if year is not None:
        filters["year"] = year
    if semester is not None:
        filters["semester"] = semester

    if (year is not None or semester is not None):
        limit = 27

    results = course_service.filter_courses(filters, limit)
    if not results or not results["ids"][0]:
        return []
        
    courses = []
    for i in range(len(results["ids"][0])):
        courses.append(CourseResponse(
            course_code=results["ids"][0][i],
            title=results["metadatas"][0][i].get("title", "Unknown"),
            year=results["metadatas"][0][i].get("year", 0),
            semester=results["metadatas"][0][i].get("semester", 0),
            ects=results["metadatas"][0][i].get("ects"),
            document=results["documents"][0][i]
        ))
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
        document=course["document"]
    )

@app.get("/professors/{name}/courses", response_model=ProfessorResponse)
async def get_professor_courses(name: str):
    """Get courses taught by a professor"""
    courses = professor_service.get_courses_by_professor(name)
    if not courses:
        raise HTTPException(status_code=404, detail="Professor not found or has no courses")
        
    canonical_name = name_service.find_canonical_name(name) or name
    
    course_list = []
    for course in courses:
        course_list.append(CourseResponse(
            course_code=course["course_code"],
            title=course["metadata"].get("title", "Unknown"),
            year=course["metadata"].get("year", 0),
            semester=course["metadata"].get("semester", 0),
            ects=course["metadata"].get("ects"),
            document=course["document"]
        ))
        
    return ProfessorResponse(
        name=canonical_name,
        courses=course_list
    )

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

def format_course_results(results):
    """Format course search results into a consistent structure"""
    courses = []
    for i in range(len(results["ids"][0])):
        courses.append({
            "course_code": results["ids"][0][i],
            "title": results["metadatas"][0][i].get("title", "Unknown"),
            "year": results["metadatas"][0][i].get("year", 0),
            "semester": results["metadatas"][0][i].get("semester", 0),
            "ects": results["metadatas"][0][i].get("ects"),
            "document": results["documents"][0][i]
        })
    return courses

def format_professor_courses(courses):
    """Format professor courses into a consistent structure"""
    course_list = []
    for course in courses:
        course_list.append({
            "course_code": course["course_code"],
            "title": course["metadata"].get("title", "Unknown"),
            "year": course["metadata"].get("year", 0),
            "semester": course["metadata"].get("semester", 0),
            "ects": course["metadata"].get("ects"),
            "document": course["document"]
        })
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

@app.post("/search/unified")
async def unified_search(request: QueryRequest):
    """Unified search endpoint that handles different query types"""
    query = request.query.strip()
    
    # 1. Analyze query intent
    query_intent = nlp_service.analyze_query_intent(query)
    
    # 2. For professor-subject matches, extract and process
    if query_intent == "professor_courses":
        professor_name = nlp_service.extract_professor_name(query)
        if professor_name:
            try:
                courses = professor_service.get_courses_by_professor(professor_name)
                if courses:
                    canonical_name = name_service.find_canonical_name(professor_name) or professor_name
                    course_list = format_professor_courses(courses)
                    
                    return {
                        "query_type": "professor_courses",
                        "data": {
                            "professor_name": canonical_name,
                            "courses": course_list
                        },
                        "natural_response": generate_professor_courses_response(canonical_name, course_list)
                    }
            except Exception:
                pass
    
    # 3. Default to standard course search
    results = course_service.search_courses(query, 10)
    if not results or not results["ids"][0]:
        return {"query_type": "unknown", "data": None, "message": "No results found"}
        
    courses = format_course_results(results)
    return {
        "query_type": "course_search",
        "data": courses
    }