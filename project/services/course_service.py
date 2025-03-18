# services/course_service.py
import json
import os
import logging
import time
from models.course import Course
from db.collections import Collections
from config.settings import EMBEDDING_DELAY

logger = logging.getLogger(__name__)

class CourseService:
    """Manages course operations"""
    
    def __init__(self, collections=None, professor_service=None):
        self.collections = collections or Collections()
        self.professor_service = professor_service  
        self.course_collection = self.collections.get_course_collection()
    
    def set_professor_service(self, professor_service):
        """Set the professor service (to avoid circular imports)"""
        self.professor_service = professor_service
    
    def load_course(self, file_path):
        """Load course data from JSON file"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Course.from_json(data)
        except Exception as e:
            logger.error(f"Error loading course from {file_path}: {str(e)}")
            return None
    
    def add_course(self, course, skip_professors=False):
        """Add a course to the database"""
        try:
            document = course.to_document()
            metadata = course.to_metadata()
            
            self.course_collection.add(
                documents=[document],
                ids=[course.course_code],
                metadatas=[metadata]
            )
            
            time.sleep(EMBEDDING_DELAY)
            
            logger.info(f"Added course {course.course_code} to database")
            
            # Process instructors if professor service is available
            if self.professor_service and course.instructors and not skip_professors:
                instructors = self._process_instructors(course.instructors)
                for instructor in instructors:
                    self.professor_service.add_professor(instructor, course.course_code, course.title)
            
            return True
        except Exception as e:
            logger.error(f"Error adding course {course.course_code}: {str(e)}")
            return False
    
    def _process_instructors(self, instructors):
        """Process instructor data to consistent format"""
        if not isinstance(instructors, list):
            if isinstance(instructors, str):
                instructors = [name.strip() for name in instructors.split(",")]
            else:
                instructors = []
        return instructors
    
    def get_course(self, course_code):
        """Get a course by course code"""
        try:
            result = self.course_collection.get(ids=[course_code])
            if result["ids"]:
                return {
                    "course_code": course_code,
                    "metadata": result["metadatas"][0] if result["metadatas"] else None,
                    "document": result["documents"][0] if result["documents"] else None
                }
            return None
        except Exception as e:
            logger.error(f"Error getting course {course_code}: {str(e)}")
            return None
    
    def search_courses(self, query, limit=5):
        """Search courses by content"""
        try:
            results = self.course_collection.query(query_texts=[query], n_results=limit)
            return results
        except Exception as e:
            logger.error(f"Error searching courses with query '{query}': {str(e)}")
            return None
    
    def filter_courses(self, filters, limit=10):
        """Filter courses by metadata fields"""
        try:
            results = self.course_collection.query(
                query_texts=[""], 
                where=filters,
                n_results=limit
            )
            return results
        except Exception as e:
            logger.error(f"Error filtering courses: {str(e)}")
            return None
    
    def find_course_files(self, directory):
        """Find course JSON files in a directory"""
        course_files = []
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".json"):
                    course_files.append(os.path.join(root, file))
        return course_files
    
    def batch_import_courses(self, directory, skip_professors=False):
        """Import multiple courses from a directory"""
        course_files = self.find_course_files(directory)
        
        if not course_files:
            logger.warning(f"No course files found in {directory}")
            return 0
            
        logger.info(f"Found {len(course_files)} course files to import")
        
        success_count = 0
        for file_path in course_files:
            course = self.load_course(file_path)
            if not course:
                continue
                
            if skip_professors:
                document = course.to_document()
                metadata = course.to_metadata()
                
                self.course_collection.add(
                    documents=[document],
                    ids=[course.course_code],
                    metadatas=[metadata]
                )
                
                time.sleep(EMBEDDING_DELAY)
                
                logger.info(f"Added course {course.course_code} to database (skipped professor data)")
                success_count += 1
            else:
                if self.add_course(course):
                    success_count += 1
        
        logger.info(f"Successfully imported {success_count} out of {len(course_files)} courses")
        return success_count