# services/name_service.py
import os
import pickle
import logging
from config.settings import PROFESSOR_MAPPING_PATH, SIMILARITY_THRESHOLD
from db.collections import Collections

logger = logging.getLogger(__name__)

class NameService:
    """Manages professor name variations and matching"""
    
    def __init__(self, collections=None, nlp_service=None):
        self.collections = collections or Collections()
        self.nlp_service = nlp_service
        self.professor_collection = self.collections.get_professor_collection()
        self.professor_names_collection = self.collections.get_professor_names_collection()
        self.name_cache = {}
        self.load_name_cache()
        
    def load_name_cache(self):
        """Load professor name mappings from pickle file"""
        if os.path.exists(PROFESSOR_MAPPING_PATH):
            try:
                with open(PROFESSOR_MAPPING_PATH, "rb") as f:
                    self.name_cache = pickle.load(f)
                logger.info(f"Loaded {len(self.name_cache)} professor name mappings from cache")
            except Exception as e:
                logger.error(f"Error loading professor name cache: {e}")
                self.name_cache = {}
        
    def save_name_cache(self):
        """Save professor name mappings to pickle file"""
        try:
            with open(PROFESSOR_MAPPING_PATH, "wb") as f:
                pickle.dump(self.name_cache, f)
            logger.info(f"Saved {len(self.name_cache)} professor name mappings to cache")
        except Exception as e:
            logger.error(f"Error saving professor name cache: {e}")
    
    def add_name_variation(self, canonical_name, variation):
        """Add a name variation for a canonical professor name"""
        if not variation or not canonical_name:
            return False

        try:
            # Normalize names
            canonical_name = canonical_name.strip()
            variation = variation.strip()

            # Update cache
            self.name_cache[variation.lower()] = canonical_name

            variation_id = f"name_var_{variation.replace(' ', '_').lower()}"
            canonical_id = f"name_can_{canonical_name.replace(' ', '_').lower()}"

            logger.info(f"Processing variation '{variation}' for '{canonical_name}'")

            # Check if variation already exists
            try:
                existing = self.professor_names_collection.get(ids=[variation_id])
                if len(existing["ids"]) > 0:
                    if existing["metadatas"][0].get("canonical_name") != canonical_name:
                        logger.info(f"Updating variation '{variation}' to '{canonical_name}'")
                        self.professor_names_collection.update(
                            ids=[variation_id],
                            documents=[variation],
                            metadatas=[{"canonical_name": canonical_name, "is_variation": True}]
                        )
                    return True
            except Exception as e:
                logger.error(f"Error checking variation '{variation}': {str(e)}")

            # Add variation
            self.professor_names_collection.add(
                ids=[variation_id],
                documents=[variation],
                metadatas=[{"canonical_name": canonical_name, "is_variation": True}]
            )

            # Check if canonical name exists
            try:
                existing = self.professor_names_collection.get(ids=[canonical_id])
                has_canonical = len(existing["ids"]) > 0
            except Exception as e:
                logger.error(f"Error checking canonical '{canonical_name}': {str(e)}")
                has_canonical = False

            # Add canonical name if needed
            if not has_canonical:
                try:
                    self.professor_names_collection.add(
                        ids=[canonical_id],
                        documents=[canonical_name],
                        metadatas=[{"canonical_name": canonical_name, "is_canonical": True}]
                    )
                except Exception as e:
                    logger.error(f"Error adding canonical '{canonical_name}': {str(e)}")

            logger.info(f"Successfully added variation '{variation}' for '{canonical_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error adding professor name variation: {str(e)}")
            return False
    
    def find_canonical_name(self, query_name):
        """Find the canonical name for a given professor name variation"""
        if not query_name:
            return None

        query_name = query_name.strip()

        # Check cache first
        if query_name.lower() in self.name_cache:
            return self.name_cache[query_name.lower()]

        logger.info(f"{query_name} not found in cache, searching collection...")

        # Check for exact match in professors collection
        try:
            all_professors = self.professor_collection.get()
            for i, prof in enumerate(all_professors["metadatas"]):
                if "professor_name" in prof and query_name.lower() == prof["professor_name"].lower():
                    self.name_cache[query_name.lower()] = prof["professor_name"]
                    return prof["professor_name"]
        except Exception as e:
            logger.error(f"Error checking exact match: {str(e)}")

        # Try embedding-based search
        try:
            results = self.professor_names_collection.query(query_texts=[query_name], n_results=1)
            if results["ids"] and len(results["ids"][0]) > 0:
                canonical_name = results["metadatas"][0][0].get("canonical_name")
                if canonical_name:
                    # Update cache
                    self.name_cache[query_name.lower()] = canonical_name
                    return canonical_name
        except Exception as e:
            logger.error(f"Error in embedding search: {str(e)}")

        return None