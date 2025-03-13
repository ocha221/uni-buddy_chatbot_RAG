import os
import logging
import re
from datetime import datetime
import time
import json

logger = logging.getLogger(__name__)

class RefreshService:
    """Manages database refresh operations"""
    
    def __init__(self, course_service=None, news_service=None, professor_service=None, name_service=None):
        self.course_service = course_service
        self.news_service = news_service
        self.professor_service = professor_service
        self.name_service = name_service
    
    def find_latest_data_directory(self, base_path, pattern=r'(\d{2}_\d{2}_\d{4})_scraped_on'):
        """Find the most recent data directory based on date in folder name"""
        if not os.path.exists(base_path):
            
            logger.warning(f"Base path does not exist: {base_path}")
            return None
        latest_dir = None
        latest_date = None
        
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            if os.path.isdir(item_path):
                match = re.search(pattern, item)
                if match:
                    date_str = match.group(1)
                    try:
                        date = datetime.strptime(date_str, '%d_%m_%Y')
                        if latest_date is None or date > latest_date:
                            latest_date = date
                            latest_dir = item_path
                    except ValueError:
                        logger.warning(f"Could not parse date from directory: {item}")
        
        if latest_dir:
            logger.info(f"Found latest data directory: {latest_dir} (from {latest_date})")
        else:
            logger.warning(f"No matching data directories found in {base_path}")
            
        return latest_dir
    
       

    def retry_operation(self, operation_func, items, max_retries=3, delay=5):
        """
        Retry failed imports/etc
        """

        successful_items = []
        failed_items = []
        
        for item in items:
            try:
                if operation_func(item):
                    successful_items.append(item)
                else:
                    failed_items.append(item)
            except Exception as e:
                logger.error(f"Error processing item: {str(e)}")
                failed_items.append(item)
        
       #* retry whatev failed
        retry_count = 0
        current_delay = delay
        
        while failed_items and retry_count < max_retries:
            retry_count += 1
            logger.info(f"Retry attempt {retry_count}/{max_retries} for {len(failed_items)} failed items")
            time.sleep(current_delay)
            current_delay *= 2  #*exponential
            
            #*another retry
            still_failed = []      
            for item in failed_items:
                try:
                    logger.info(f"Retrying item: {getattr(item, 'course_code', getattr(item, 'id', str(item)))}")
                    if operation_func(item):
                        successful_items.append(item)
                    else:
                        still_failed.append(item)
                except Exception as e:
                    logger.error(f"Error during retry: {str(e)}")
                    still_failed.append(item)
            
            failed_items = still_failed
        
        if failed_items:
            logger.warning(f"After {max_retries} retries, {len(failed_items)} items still failed")
            
        return successful_items, failed_items
    
    def refresh_courses(self, base_path="course_data", skip_professors=False, reset=True, max_retries=3):
        """Refresh courses collection with latest data"""
        latest_dir = self.find_latest_data_directory(base_path)
        if not latest_dir:
            logger.error(f"No course data directory found in {base_path}")
            return 0
        
        if not self.course_service:
            logger.error("Course service not available")
            return 0
        
        if reset:
            logger.info("Resetting course collection before import")
            self.course_service.collections.reset_collections(
                reset_courses=True, 
                reset_professors=False, 
                reset_name_mappings=False
            )
        
        logger.info(f"Refreshing courses from {latest_dir}")
        course_files = self.course_service.find_course_files(latest_dir)
        
        if not course_files:
            logger.warning(f"No course files found in {latest_dir}")
            return 0
            
        logger.info(f"Found {len(course_files)} course files to import")
        
        courses = []
        for file_path in course_files:
            course = self.course_service.load_course(file_path)
            if course:
                courses.append(course)
        
        def add_course_operation(course):
            if skip_professors:
                document = course.to_document()
                metadata = course.to_metadata()
                
                self.course_service.course_collection.add(
                    documents=[document],
                    ids=[course.course_code],
                    metadatas=[metadata]
                )
                
                time.sleep(self.course_service.EMBEDDING_DELAY)
                
                logger.info(f"Added course {course.course_code} to database (skipped professor data)")
                return True
            else:
                return self.course_service.add_course(course)
        successful, failed = self.retry_operation(add_course_operation, courses, max_retries=max_retries)
        
        if failed:
            logger.warning(f"Failed to import {len(failed)} courses: {[getattr(c, 'course_code', 'Unknown') for c in failed]}")
        
        logger.info(f"Successfully imported {len(successful)} out of {len(courses)} courses")
        return len(successful)
    
    def refresh_news(self, base_path="news_data", reset=True, max_retries=3):
        """Refresh news collection with latest data"""
        latest_dir = self.find_latest_data_directory(base_path)
        if not latest_dir:
            logger.error(f"No news data directory found in {base_path}")
            return 0
        
        if not self.news_service:
            logger.error("News service not available")
            return 0
        
        if reset:
            logger.info("Resetting news collection before import")
            self.news_service.collections.client.delete_collection("news")
            self.news_service.news_collection = self.news_service.collections.get_news_collection()
        
        logger.info(f"Refreshing news from {latest_dir}")
        
        
        news_files = []
        for root, _, files in os.walk(latest_dir):
            for file in files:
                if file.endswith(".json"):
                    file_path = os.path.join(root, file)
                    news_files.append(file_path)
        
        if not news_files:
            logger.warning(f"No news files found in {latest_dir}")
            return 0
        
        logger.info(f"Found {len(news_files)} news files to import")
        
        news_items = []
        for file_path in news_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                data["news_types"] = self.news_service.determine_news_types(data)
                news = self.news_service.News.from_json(data)
                news_items.append(news)
            except Exception as e:
                logger.error(f"Error processing {file_path}: {str(e)}")
        
        def add_news_operation(news_item):
            return self.news_service.add_news(news_item)
        
        successful, failed = self.retry_operation(add_news_operation, news_items, max_retries=max_retries)
        
        if failed:
            logger.warning(f"Failed to import {len(failed)} news items: {[getattr(n, 'id', 'Unknown') for n in failed]}")
        
        logger.info(f"Successfully imported {len(successful)} out of {len(news_items)} news items")
        return len(successful)
    
   
    def refresh_all(self, course_path="course_data", news_path="news_data", reset=True, max_retries=3):
        """Refresh all collections with latest data"""
        course_count = self.refresh_courses(course_path, skip_professors=True, reset=reset, max_retries=max_retries)
        news_count = self.refresh_news(news_path, reset=reset, max_retries=max_retries)
        prof_count = self.refresh_professors(consolidate=True)
        
        return {
            "courses": course_count,
            "news": news_count,
            "professors": prof_count
        }