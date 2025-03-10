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

    def search_news(self, query, query_intent=None, limit=5, max_days_old=None):
        """
        Args:
            query: Text search query
            query_intent: Single intent or list of intents
            limit: Maximum number of results
            max_days_old: Only return news from the last N days
        """
        try:
            if query_intent == IntentType.BANNED_QUERY:
                return None

            where_clause = None  # * aftomato skip otan einai general

            if query_intent != IntentType.NEWS_GENERAL:
                intents = (
                    [query_intent] if isinstance(query_intent, str) else query_intent
                )

                if intents and any(i in NEWS_INTENT_MAPPING for i in intents):
                    where_conditions = []
                    for intent in intents:
                        if intent in NEWS_INTENT_MAPPING:
                            field = NEWS_INTENT_MAPPING[intent]
                            where_conditions.append({field: True})

                    if len(where_conditions) > 1:
                        where_clause = {"$or": where_conditions}
                    elif len(where_conditions) == 1:
                        where_clause = where_conditions[0]

            if max_days_old:
                import time

                cutoff_epoch = int(time.time()) - (max_days_old * 86400)

                date_filter = {"date_epoch": {"$gte": cutoff_epoch}}

                if where_clause:
                    where_clause = {"$and": [where_clause, date_filter]}
                else:
                    where_clause = date_filter

            results = self.news_collection.query(
                query_texts=[query], n_results=limit, where=where_clause
            )

            if results and "documents" in results and results["documents"][0]:
                news_items = []
                for i in range(len(results["documents"][0])):
                    news_items.append(
                        {
                            "document": results["documents"][0][i],
                            "metadata": (
                                results["metadatas"][0][i]
                                if "metadatas" in results
                                else {}
                            ),
                            "id": results["ids"][0][i],
                            "distance": (
                                results["distances"][0][i]
                                if "distances" in results
                                else 1.0
                            ),
                        }
                    )
                # todo todo todo
                # ? (similarity_score * 0.7) + (recency_bonus * 0.3)
                # ? to recency logika thelei parapanw
                import time

                current_time = int(time.time())

                for item in news_items:
                    similarity = 1 - min(item["distance"], 1.0)
                    date_epoch = item["metadata"].get("date_epoch", 0)
                    days_old = (current_time - date_epoch) / 86400
                    recency = max(0, 1 - (days_old / 30))
                    item["combined_score"] = (similarity * 0.7) + (recency * 0.3)

                news_items.sort(key=lambda x: x["combined_score"], reverse=True)

                new_results = {
                    "ids": [[item["id"] for item in news_items[:limit]]],
                    "documents": [[item["document"] for item in news_items[:limit]]],
                    "metadatas": [[item["metadata"] for item in news_items[:limit]]],
                    "distances": [[item["distance"] for item in news_items[:limit]]],
                }

                return new_results

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

    def debug_search(self, query, query_intent=None, limit=10):
        """Debug news search issues"""
        try:
            # Log the search parameters
            intent_type = (
                NEWS_INTENT_MAPPING.get(query_intent) if query_intent else None
            )
            logger.info(
                f"Debug news search: query='{query}', intent_type={intent_type}, limit={limit}"
            )

            # Get the collection
            collection = self.news_collection.get()
            logger.info(
                f"News collection stats: {len(collection.get('ids', []))} total items"
            )

            # If there's a specific intent type, log how many items have that type
            if intent_type:
                matching_items = 0
                for metadata in collection.get("metadatas", []):
                    if metadata.get("type") == intent_type:
                        matching_items += 1
                logger.info(f"News items with type '{intent_type}': {matching_items}")

            # Perform the actual search
            results = self.search_news(query, query_intent, limit)

            # Log the results
            has_results = bool(results)
            has_documents = bool(results.get("documents")) if has_results else False
            has_content = (
                bool(results.get("documents") and results["documents"][0])
                if has_documents
                else False
            )

            logger.info(
                f"Search results: has_results={has_results}, has_documents={has_documents}, has_content={has_content}"
            )

            if has_content:
                logger.info(f"Found {len(results['documents'][0])} matching news items")

            return {
                "search_params": {
                    "query": query,
                    "intent_type": intent_type,
                    "limit": limit,
                },
                "collection_stats": {
                    "total_items": len(collection.get("ids", [])),
                    "matching_type": matching_items if intent_type else None,
                },
                "results_stats": {
                    "has_results": has_results,
                    "has_documents": has_documents,
                    "has_content": has_content,
                    "found_items": len(results["documents"][0]) if has_content else 0,
                },
            }
        except Exception as e:
            logger.error(f"Error in debug_search: {str(e)}")
            return {"error": str(e)}
