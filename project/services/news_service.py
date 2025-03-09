import json
import os
import logging
import time
import uuid
from models.news import News
from models.intent_mappings import IntentType, NEWS_INTENT_MAPPING
from db.collections import Collections
from config.settings import EMBEDDING_DELAY
from typing import Optional

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
                documents=[document], ids=[news.id], metadatas=[metadata]
            )

            time.sleep(EMBEDDING_DELAY)
            logger.info(f"Added news {news.id} to database")
            return True
        except Exception as e:
            logger.error(f"Error adding news {news.id}: {str(e)}")
            return False

    def determine_news_types(self, json_data):
        if "news_types" in json_data and json_data["news_types"]:
            return json_data["news_types"]
        else:
            return "type_general"

    def batch_import_news(self, directory):
        """Import everything from a directory"""
        news_files = []
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".json"):
                    file_path = os.path.join(root, file)
                    news_files.append(file_path)

        if not news_files:
            logger.warning(f"No news files found in {directory}")
            return 0

        logger.info(f"Found {len(news_files)} news files to import")

        success_count = 0
        for file_path in news_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                data["news_types"] = self.determine_news_types(data)
                news = News.from_json(data)

                if self.add_news(news):
                    success_count += 1
            except Exception as e:
                logger.error(f"Error processing {file_path}: {str(e)}")

        logger.info(
            f"Successfully imported {success_count} out of {len(news_files)} news items"
        )
        return success_count

    def search_news(self, query, query_intent=None, limit=5):
        """Search for news based on query and intent"""
        try:
            if query_intent == IntentType.BANNED_QUERY:
                return None #TODO message something idk
            
            where_clause = {}
            if query_intent in NEWS_INTENT_MAPPING:
                metadata_field = NEWS_INTENT_MAPPING[query_intent]
                where_clause[metadata_field] = True
                
                results = self.news_collection.query(
                    query_texts=[query],
                    n_results=limit,
                    where=where_clause if where_clause else None,
                )
                return results
            if query_intent in [IntentType.NEWS_GENERAL, IntentType.UNKNOWN]:
                results = self.news_collection.query(
                    query_texts=[query],
                    n_results=limit
                )
                return results
            results = self.news_collection.query(
                query_texts=[query],
                n_results=limit
            )
            return results
                
        except Exception as e:
            logger.error(f"Error searching news with query '{query}': {str(e)}")
            return None

    def print_all_news(self):
        """self explanatory lol"""
        try:
            all_news = self.news_collection.get()

            if not all_news or len(all_news.get("ids", [])) == 0:
                logger.info("No news entries found in the collection")
                return 0

            count = len(all_news["ids"])
            logger.info(f"Found {count} news entries in the collection")

            for i in range(count):
                news_id = all_news["ids"][i]
                metadata = all_news["metadatas"][i]
                document = all_news["documents"][i]

                print(f"\n--- News Entry {i+1}/{count} ---")
                print(f"ID: {news_id}")
                print("Metadata:")
                for key, value in metadata.items():
                    print(f"  {key}: {value}")
                # print("Document Content:")
                # print(document)
                print("-" * 50)

            return count
        except Exception as e:
            logger.error(f"Error retrieving all news entries: {str(e)}")
            return 0
