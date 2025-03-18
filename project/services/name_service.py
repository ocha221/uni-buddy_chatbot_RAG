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
        self.professor_names_collection = (
            self.collections.get_professor_names_collection()
        )
        self.name_cache = {}
        self.embedding_cache = {}  # New cache for embeddings
        self.load_name_cache()
        self.load_embedding_cache()

    def load_embedding_cache(self):
        """Load professor name embeddings from pickle file"""
        embedding_path = PROFESSOR_MAPPING_PATH.replace(".pkl", "_embeddings.pkl")
        if os.path.exists(embedding_path):
            try:
                with open(embedding_path, "rb") as f:
                    self.embedding_cache = pickle.load(f)
                logger.info(
                    f"Loaded {len(self.embedding_cache)} professor name embeddings from cache"
                )
            except Exception as e:
                logger.error(f"Error loading professor name embeddings: {e}")
                self.embedding_cache = {}

    def load_name_cache(self):
        """Load professor name mappings from pickle file"""
        if os.path.exists(PROFESSOR_MAPPING_PATH):
            try:
                with open(PROFESSOR_MAPPING_PATH, "rb") as f:
                    self.name_cache = pickle.load(f)
                logger.info(
                    f"Loaded {len(self.name_cache)} professor name mappings from cache"
                )
            except Exception as e:
                logger.error(f"Error loading professor name cache: {e}")
                self.name_cache = {}

    def save_name_cache(self):
        """Save professor name mappings to pickle file"""
        try:
            with open(PROFESSOR_MAPPING_PATH, "wb") as f:
                pickle.dump(self.name_cache, f)
            logger.info(
                f"Saved {len(self.name_cache)} professor name mappings to cache"
            )
        except Exception as e:
            logger.error(f"Error saving professor name cache: {e}")

    def save_embedding_cache(self):
        """Save professor name embeddings to pickle file"""
        embedding_path = PROFESSOR_MAPPING_PATH.replace(".pkl", "_embeddings.pkl")
        try:
            with open(embedding_path, "wb") as f:
                pickle.dump(self.embedding_cache, f)
            logger.info(
                f"Saved {len(self.embedding_cache)} professor name embeddings to cache"
            )
        except Exception as e:
            logger.error(f"Error saving professor name embeddings: {e}")

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
                        logger.info(
                            f"Updating variation '{variation}' to '{canonical_name}'"
                        )
                        self.professor_names_collection.update(
                            ids=[variation_id],
                            documents=[variation],
                            metadatas=[
                                {"canonical_name": canonical_name, "is_variation": True}
                            ],
                        )
                    return True
            except Exception as e:
                logger.error(f"Error checking variation '{variation}': {str(e)}")

            # Add variation
            self.professor_names_collection.add(
                ids=[variation_id],
                documents=[variation],
                metadatas=[{"canonical_name": canonical_name, "is_variation": True}],
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
                        metadatas=[
                            {"canonical_name": canonical_name, "is_canonical": True}
                        ],
                    )
                except Exception as e:
                    logger.error(f"Error adding canonical '{canonical_name}': {str(e)}")

            logger.info(
                f"Successfully added variation '{variation}' for '{canonical_name}'"
            )
            return True

        except Exception as e:
            logger.error(f"Error adding professor name variation: {str(e)}")
            return False

    def find_canonical_name(self, query_name):
        """Find the canonical name for a given professor name variation using embedding similarity"""
        if not query_name:
            return None

        query_name = query_name.strip()

        if query_name.lower() in self.name_cache:
            return self.name_cache[query_name.lower()]

        logger.info(f"{query_name} not found in cache, using embedding similarity...")

        if not self.embedding_cache or not self.nlp_service:
            return None

        try:
            query_embedding = self.nlp_service.get_embeddings([query_name])[0]

            best_match = None
            best_similarity = -1

            for canonical_name, embedding in self.embedding_cache.items():
                similarity = self.nlp_service.calculate_similarity(
                    query_embedding, embedding
                )
                logger.info(
                    f" ===== \n Comparing '{query_name}' with '{canonical_name}': similarity {similarity:.4f} \n ===== "
                )  # TODO add to file
                if similarity > best_similarity and similarity > SIMILARITY_THRESHOLD:
                    best_similarity = similarity
                    best_match = canonical_name

            if best_match:
                self.name_cache[query_name.lower()] = best_match
                logger.info(
                    f"Found match for '{query_name}': '{best_match}' (similarity: {best_similarity:.4f})"
                )
                return best_match

        except Exception as e:
            logger.error(f"Error in embedding similarity search: {str(e)}")

        return None

    def find_canonical_name_with_confidence(self, query_name):
        """Find canonical name and return confidence level
        prob will replace find_canonical_name, this works in the context of multi-turn chat
        if we're unsure of a match, we can ask the user to be more specific!"""
        if not query_name:
            return None, 0.0

        query_name = query_name.strip()
        if query_name.lower() in self.name_cache:
            return self.name_cache[query_name.lower()], 1.0

        logger.info(f"{query_name} not found in cache, using embedding similarity...")

        if not self.embedding_cache or not self.nlp_service:
            return None, 0.0

        try:
            query_embedding = self.nlp_service.get_embeddings([query_name])[0]

            best_match = None
            best_similarity = -1

            for canonical_name, embedding in self.embedding_cache.items():
                similarity = self.nlp_service.calculate_similarity(
                    query_embedding, embedding
                )
                logger.info(
                    f"Comparing '{query_name}' with '{canonical_name}': similarity {similarity:.4f}"
                )

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = canonical_name

            if best_similarity > 0:
                return best_match, best_similarity

        except Exception as e:
            logger.error(f"Error in embedding similarity search: {str(e)}")

        return None, 0.0
