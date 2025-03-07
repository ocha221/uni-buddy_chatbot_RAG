import json
import os
import logging
import time
import uuid
from models.news import News
from db.collections import Collections
from config.settings import EMBEDDING_DELAY

logger = logging.getLogger(__name__)

class NewsService:
    """Manages news operations"""
    
    def __init__(self, collections=None):
        self.collections = collections or Collections()
        self.news_collection = self.collections.get_news_collection()
    
    def add_news(self, news):
        """Add a news item to the database"""
        try:
            if not news.id:
                news.id = str(uuid.uuid4())
                
            document = news.to_document()
            metadata = news.to_metadata()
            
            self.news_collection.add(
                documents=[document],
                ids=[news.id],
                metadatas=[metadata]
            )
            
            time.sleep(EMBEDDING_DELAY)
            logger.info(f"Added news {news.id} to database")
            return True
        except Exception as e:
            logger.error(f"Error adding news {news.id}: {str(e)}")
            return False
    
    def determine_news_type(self, directory_path):
        """Determine news type based on directory path"""
        path_parts = directory_path.lower().split(os.sep)
        if "internship" in path_parts or "internship_data" in path_parts:
            return "internship"
        elif "ptyxiaki" in path_parts:
            return "ptixiaki"
        else: #TODO add more stuff
            return "general"
    
    def batch_import_news(self, directory):
        """Import multiple news items from a directory"""
        news_files = []
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".json"):
                    file_path = os.path.join(root, file)
                    news_type = self.determine_news_type(root)
                    news_files.append((file_path, news_type))
        
        if not news_files:
            logger.warning(f"No news files found in {directory}")
            return 0
            
        logger.info(f"Found {len(news_files)} news files to import")
        
        success_count = 0
        for file_path, news_type in news_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                data["news_type"] = news_type
                news = News.from_json(data)
                
                if self.add_news(news):
                    success_count += 1
            except Exception as e:
                logger.error(f"Error processing {file_path}: {str(e)}")
        
        logger.info(f"Successfully imported {success_count} out of {len(news_files)} news items")
        return success_count