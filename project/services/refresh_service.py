import os
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class RefreshService:
    """Manages database refresh operations"""
    
    def __init__(self, course_service=None, news_service=None, professor_service=None, name_service=None):
        self.course_service = course_service
        self.news_service = news_service
        self.professor_service = professor_service
        self.name_service = name_service
    
    def find_latest_data_directory(self, base_path, pattern=r'(\d{4}-\d{2}-\d{2})_scraped_on'):
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
                        date = datetime.strptime(date_str, '%Y-%m-%d')
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
    
    def refresh_courses(self, base_path="course_data", skip_professors=False, reset=True):
        """Refresh courses collection with latest scraped data"""
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
        return self.course_service.batch_import_courses(latest_dir, skip_professors)
    
    def refresh_news(self, base_path="news_data", reset=True):
        """Refresh news collection with latest scraped data"""
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
        return self.news_service.batch_import_news(latest_dir)
    
    def refresh_professors(self, consolidate=True):
        """Rebuild professor data from courses"""
        if not self.professor_service:
            logger.error("Professor service not available")
            return 0
        
        logger.info("Rebuilding professor data")
        count = self.professor_service.rebuild_professor_data()
        
        if consolidate and count > 0 and self.name_service:
            logger.info("Consolidating professor names")
            self.professor_service.consolidate_professor_names(interactive=False)
        
        return count
    
    def refresh_all(self, course_path="course_data", news_path="news_data", reset=True):
        """Refresh all collections with latest data"""
        course_count = self.refresh_courses(course_path, skip_professors=False, reset=reset)
        news_count = self.refresh_news(news_path, reset=reset)
        prof_count = self.refresh_professors(consolidate=True)
        
        return {
            "courses": course_count,
            "news": news_count,
            "professors": prof_count
        }