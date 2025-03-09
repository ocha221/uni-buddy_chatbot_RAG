import logging
from models.professor import Professor
from db.collections import Collections

logger = logging.getLogger(__name__)

class ProfessorService:
    """Manages professor operations"""
    
    def __init__(self, collections=None, name_service=None, course_service=None):
        self.collections = collections or Collections()
        self.name_service = name_service
        self.course_service = course_service  # Will be set after CourseService init
        self.professor_collection = self.collections.get_professor_collection()
    
    def set_course_service(self, course_service):
        """Set the course service (to avoid circular imports)"""
        self.course_service = course_service
    
    def add_professor(self, professor_name, course_code, course_title):
        """Add or update a professor in the database"""
        try:
            prof_id = f"professor_{professor_name.replace(' ', '_').lower()}"
            
            # Check if professor already exists
            try:
                existing_entry = self.professor_collection.get(ids=[prof_id])
                exists = len(existing_entry["ids"]) > 0
            except:
                exists = False
            
            professor = Professor(professor_name, [])
            
            if exists:
                # Update existing professor
                existing_doc = existing_entry["documents"][0]
                existing_metadata = existing_entry["metadatas"][0]
                
                courses = (
                    existing_metadata.get("course_codes", "").split(",")
                    if existing_metadata.get("course_codes")
                    else []
                )
                
                if course_code not in courses and course_code.strip():
                    courses.append(course_code)
                
                updated_metadata = existing_metadata.copy()
                updated_metadata["course_codes"] = ",".join(courses)
                
                updated_content = existing_doc
                if course_code not in updated_content:
                    updated_content += f"\nTeaches course: {course_code} - {course_title}"
                
                self.professor_collection.update(
                    ids=[prof_id],
                    documents=[updated_content],
                    metadatas=[updated_metadata]
                )
            else:
                # Add new professor
                professor.add_course(course_code, course_title)
                
                document = professor.to_document()
                metadata = professor.to_metadata()
                
                self.professor_collection.add(
                    documents=[document],
                    ids=[prof_id],
                    metadatas=[metadata]
                )
            
            # Add name variation if name service is available
            if self.name_service:
                self.name_service.add_name_variation(professor_name, professor_name)
            
            return True
        except Exception as e:
            logger.error(f"Error adding professor {professor_name}: {str(e)}")
            return False
    
    def get_courses_by_professor(self, professor_name):
        """Get all courses taught by a professor"""
        if not professor_name:
            return None
        
        # Try to find canonical name if name service is available
        canonical_name = None
        if self.name_service:
            canonical_name = self.name_service.find_canonical_name(professor_name)
        
        if canonical_name:
            professor_name = canonical_name
            logger.info(f"Using canonical professor name: {professor_name}")
        else:
            logger.info(f"No canonical name found for '{professor_name}', using as-is")
        
        prof_id = f"professor_{professor_name.replace(' ', '_').lower()}"
        try:
            print(f"trying exact match for {prof_id}")
            exact_match = self.professor_collection.get(ids=[prof_id])
            
            if exact_match and len(exact_match["ids"]) > 0:
               
                metadata = exact_match["metadatas"][0]
                course_codes = metadata.get("course_codes", "").split(",")
                course_codes = [code for code in course_codes if code.strip()]
                
                logger.info(f"Found {len(course_codes)} courses for professor {professor_name} via direct lookup")
                
                course_results = []
                if self.course_service and course_codes:
                    for course_code in course_codes:
                        course_data = self.course_service.get_course(course_code)
                        if course_data:
                            course_results.append(course_data)
                return course_results
        except Exception as e:
            logger.error(f"Error retrieving professor {professor_name}: {str(e)}\n continuing with full search")
        
        #! full db search
        logger.info(f"full db scan...")
        try:
            all_professors = self.professor_collection.get()
            
            matching_professors = []
            for i, prof in enumerate(all_professors["metadatas"]):
                if (
                    "professor_name" in prof
                    and professor_name.lower() in prof["professor_name"].lower()
                ):
                    matching_professors.append({
                        "id": all_professors["ids"][i],
                        "metadata": prof,
                        "document": all_professors["documents"][i] if all_professors["documents"] else None
                    })
            
            if not matching_professors:
                return None
        except Exception as e:
            logger.error(f"Error retrieving professors: {str(e)}")
            return None
        
        try:
            all_course_codes = set()
            for prof in matching_professors:
                course_codes = prof["metadata"].get("course_codes", "").split(",")
                all_course_codes.update([code for code in course_codes if code.strip()])
            
            if not all_course_codes:
                return None
            logger.info(f"Found {len(all_course_codes) if all_course_codes else 0} courses for professor {canonical_name}")
        except Exception as e:
            logger.error(f"Error processing professor data: {str(e)}")
            return None
        try:     
            course_results = []
            if self.course_service:
                for course_code in all_course_codes:
                    course_data = self.course_service.get_course(course_code)
                    if course_data:
                        course_results.append(course_data)
        
            return course_results
        except Exception as e:
            logger.error(f"Error retrieving course data: {str(e)}")
            return None
    
    def consolidate_professor_names(self, interactive=False):
        """Consolidate professor names using embedding similarity"""
        import time
        from datetime import datetime
        from config.settings import SIMILARITY_THRESHOLD

        start_time = time.time()
        logger.info(f"Starting professor name consolidation at {datetime.now().strftime('%H:%M:%S')}")

        # 1. Extract all unique professor names
        logger.info("STEP 1: Extracting unique professor names from collection")
        all_professors = self.professor_collection.get()
        unique_names = []
        name_to_id_map = {}

        for i, metadata in enumerate(all_professors["metadatas"]):
            name = metadata.get("professor_name")
            if name and name not in unique_names:
                unique_names.append(name)
                name_to_id_map[name] = all_professors["ids"][i]

        logger.info(f"Found {len(unique_names)} unique professor names in {time.time() - start_time:.2f}s")
        if interactive:
            print(f"\n[DEBUG] Found {len(unique_names)} unique professor names")
            if len(unique_names) > 0:
                print(f"[DEBUG] Sample names: {unique_names[:5]}")

        # Check if we have the nlp service available for embeddings
        if not self.name_service or not self.name_service.nlp_service:
            logger.error("NLP service not available, cannot perform name consolidation")
            if interactive:
                print("[ERROR] NLP service not available, cannot perform name consolidation")
            return 0

        # 2. Create name groups based on embedding similarity
        logger.info("STEP 2: Creating name groups based on embedding similarity")
        step2_start = time.time()
        name_groups = []
        processed_names = set()

        logger.info(f"Generating embeddings for {len(unique_names)} names")
        embedding_start = time.time()
        try:
            embeddings = self.name_service.nlp_service.get_embeddings([name for name in unique_names])
            logger.info(f"Generated embeddings in {time.time() - embedding_start:.2f}s")
            name_to_embedding = {
                name: embedding for name, embedding in zip(unique_names, embeddings)
            }
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            if interactive:
                print(f"[ERROR] Failed to generate embeddings: {str(e)}")
            return 0

        logger.info(f"Using similarity threshold: {SIMILARITY_THRESHOLD}")

        group_formation_start = time.time()
        for i, name in enumerate(unique_names):
            if i % 10 == 0:
                logger.info(f"Processing name {i+1}/{len(unique_names)}: {name}")
                if interactive:
                    print(f"\r[DEBUG] Processing name {i+1}/{len(unique_names)}...", end="", flush=True)

            if name in processed_names:
                continue

            current_group = [name]
            processed_names.add(name)

            for j in range(i + 1, len(unique_names)):
                compare_name = unique_names[j]
                if compare_name in processed_names:
                    continue

                try:
                    embedding1 = name_to_embedding[name]
                    embedding2 = name_to_embedding[compare_name]
                    similarity = self.name_service.nlp_service.calculate_similarity(embedding1, embedding2)

                    if similarity > SIMILARITY_THRESHOLD:
                        current_group.append(compare_name)
                        processed_names.add(compare_name)
                        logger.info(f"Grouped '{compare_name}' with '{name}' (similarity: {similarity:.4f})")
                except Exception as e:
                    logger.error(f"Error calculating similarity between '{name}' and '{compare_name}': {str(e)}")
                    continue

            name_groups.append(current_group)

        if interactive:
            print("\n")

        logger.info(f"Formed {len(name_groups)} groups in {time.time() - group_formation_start:.2f}s")
        logger.info(f"STEP 2 completed in {time.time() - step2_start:.2f}s")

        # 3. Consolidate professors under canonical names
        logger.info(f"STEP 3: Consolidating courses under canonical names")
        step3_start = time.time()
        logger.info(f"Found {len(name_groups)} distinct professor entities from {len(unique_names)} name variants")

        consolidations_attempted = 0
        consolidations_succeeded = 0

        for group_index, group in enumerate(name_groups):
            logger.info(f"Processing group {group_index+1}/{len(name_groups)}: {group}")
            if interactive:
                print(f"\r[DEBUG] Processing group {group_index+1}/{len(name_groups)}...", end="", flush=True)

            if len(group) <= 1:
                logger.info(f"Group {group_index+1} has only one name, skipping")
                continue

            # Select canonical name
            canonical_name = self._select_canonical_name(group)
            logger.info(f"Selected canonical name: '{canonical_name}' for group: {group}")
            try:
                embeddings = self.name_service.nlp_service.get_embeddings([canonical_name])
                self.name_service.embedding_cache[canonical_name] = embeddings[0]
                logger.info(f"Generated and stored embedding for canonical name '{canonical_name}'")
            except Exception as e:
                logger.error(f"Error generating embedding for canonical name '{canonical_name}': {str(e)}")
            
            if interactive:
                print("\n" + "=" * 60)
                print(f"PROFESSOR GROUP {group_index+1}/{len(name_groups)}")
                print("=" * 60)
                print(f"Canonical name: {canonical_name}")
                print(f"Name variations: {', '.join([v for v in group if v != canonical_name])}")
                print("-" * 60)

                for variant in group:
                    variant_start = time.time()
                    courses = self.get_courses_by_professor(variant)
                    logger.info(f"Found {len(courses) if courses else 0} courses for '{variant}' in {time.time() - variant_start:.2f}s")
                    print(f"\nCourses for '{variant}':")

                    if not courses:
                        print("  No courses found")
                    else:
                        for idx, course in enumerate(courses, 1):
                            course_code = course.get('course_code', 'Unknown')
                            title = course.get('title', 'Unknown')
                            if course.get("metadata"):
                                year = course["metadata"].get("year", "Unknown")
                                semester = course["metadata"].get("semester", "Unknown")
                                print(f"  {idx}. {title} ({course_code})")
                                print(f"     Year: {year}, Semester: {semester}")
                            else:
                                print(f"  {idx}. {course_code} - {title}")

                try:
                    confirm = input(f"\nConsolidate these professors under '{canonical_name}'? (y/n/s): ")
                    if confirm.lower() == "n":
                        logger.info(f"User skipped consolidation of group {group_index+1}")
                        print("Skipping this group")
                        continue
                    elif confirm.lower() == "s":
                        logger.info("User requested to stop consolidation process")
                        print("Stopping consolidation process")
                        break
                except Exception as e:
                    logger.error(f"Error during user input: {str(e)}")
                    print(f"[ERROR] Input error: {str(e)}. Continuing with consolidation.")

            logger.info(f"Using '{canonical_name}' name for group: {group}")

            for variant in group:
                if variant != canonical_name:
                    consolidations_attempted += 1
                    logger.info(f"Attempting to add variation '{variant}' for canonical name '{canonical_name}'")

                    var_start = time.time()
                    variation_added = self.name_service.add_name_variation(canonical_name, variant)
                    logger.info(f"Added variation in {time.time() - var_start:.2f}s: {variation_added}")

                    if interactive:
                        print(f"Consolidating courses from '{variant}' to '{canonical_name}'...")

                    consol_start = time.time()
                    try:
                        success = self._consolidate_professor_courses(variant, canonical_name)
                        if success:
                            consolidations_succeeded += 1
                        logger.info(f"Course consolidation from '{variant}' to '{canonical_name}' in {time.time() - consol_start:.2f}s: {success}")
                    except Exception as e:
                        logger.error(f"Error during course consolidation: {str(e)}")
                        if interactive:
                            print(f"[ERROR] Failed to consolidate courses: {str(e)}")

                    if interactive and success:
                        print(f"Successfully consolidated courses from '{variant}' to '{canonical_name}'")

        if interactive:
            print("\n")

        # Save the name cache
        self.name_service.save_name_cache()
        self.name_service.save_embedding_cache()
        
        merge_duration = time.time() - step3_start
        logger.info(f"STEP 3 completed in {merge_duration:.2f}s")
        total_duration = time.time() - start_time
        logger.info(f"Professor name consolidation complete in {total_duration:.2f}s")
        logger.info(f"Consolidation summary: {consolidations_succeeded}/{consolidations_attempted} successful")

        if interactive:
            print(f"\n[SUMMARY] Consolidation complete in {total_duration:.2f}s")
            print(f"[SUMMARY] {len(name_groups)} professor groups found")
            print(f"[SUMMARY] {consolidations_succeeded}/{consolidations_attempted} successful consolidations")

        return len(name_groups)

    def _select_canonical_name(self, name_group):
        """Select the canonical name from a group of professor names"""
        if not name_group:
            return None
            
        # Simple heuristic: choose the longest name as it's likely the most complete form
        return max(name_group, key=len)

    def _consolidate_professor_courses(self, source_name, target_name):
        """Consolidate courses from source professor to target professor"""
        if not source_name or not target_name or source_name == target_name:
            return False
            
        try:
            # Convert names to IDs
            source_id = f"professor_{source_name.replace(' ', '_').lower()}"
            target_id = f"professor_{target_name.replace(' ', '_').lower()}"
            
            # Check if source professor exists
            try:
                source_entry = self.professor_collection.get(ids=[source_id])
                if len(source_entry["ids"]) == 0:
                    logger.info(f"Source professor '{source_name}' not found")
                    return False
            except Exception as e:
                logger.error(f"Error retrieving source professor: {str(e)}")
                return False
                
            # Check if target professor exists
            try:
                target_entry = self.professor_collection.get(ids=[target_id])
                target_exists = len(target_entry["ids"]) > 0
            except Exception as e:
                logger.error(f"Error retrieving target professor: {str(e)}")
                target_exists = False
                
            # Get source metadata
            source_metadata = source_entry["metadatas"][0]
            source_document = source_entry["documents"][0]
            source_courses = source_metadata.get("course_codes", "").split(",")
            source_courses = [c for c in source_courses if c.strip()]
            
            if target_exists:
                # Target professor exists, merge courses
                target_metadata = target_entry["metadatas"][0]
                target_document = target_entry["documents"][0]
                target_courses = target_metadata.get("course_codes", "").split(",")
                target_courses = [c for c in target_courses if c.strip()]
                
                # Combine courses
                all_courses = list(set(source_courses + target_courses))
                
                # Update target metadata
                updated_metadata = target_metadata.copy()
                updated_metadata["course_codes"] = ",".join(all_courses)
                
                # Update target document with source courses
                updated_document = target_document
                for course_code in source_courses:
                    if course_code not in target_document:
                        # Try to get course title
                        course_title = "Unknown"
                        if self.course_service:
                            course_data = self.course_service.get_course(course_code)
                            if course_data and isinstance(course_data, dict):
                                course_title = course_data.get("title", "Unknown")
                        
                        updated_document += f"\nTeaches course: {course_code} - {course_title}"
                
                # Update target professor
                self.professor_collection.update(
                    ids=[target_id],
                    documents=[updated_document],
                    metadatas=[updated_metadata]
                )
            else:
                # Target doesn't exist, rename source to target
                updated_metadata = source_metadata.copy()
                updated_metadata["professor_name"] = target_name
                
                # Add as new target
                self.professor_collection.add(
                    ids=[target_id],
                    documents=[source_document],
                    metadatas=[updated_metadata]
                )
            
            # Delete source 
            self.professor_collection.delete(ids=[source_id])
            logger.info(f"Deleted source professor '{source_name}' after consolidation")
            
            return True
        except Exception as e:
            logger.error(f"Error consolidating courses: {str(e)}")
        return False
    
    def rebuild_professor_data(self):
        """Rebuild professor data from existing courses"""
        if not self.course_service:
            logger.error("Course service not available, cannot rebuild professor data")
            return 0
            
        logger.info("Rebuilding professor data from existing courses...")
        
        # Clear existing professor data
        self.collections.reset_collections(reset_courses=False, reset_professors=True, reset_name_mappings=False)
        self.professor_collection = self.collections.get_professor_collection()
        
        # Get all courses
        courses = self.course_service.course_collection.get(include=["metadatas", "documents"])
        
        success_count = 0
        instructor_course_pairs = []
        
        # Extract instructors from courses
        for i, course_id in enumerate(courses["ids"]):
            try:
                doc = courses["documents"][i]
                metadata = courses["metadatas"][i]
                
                course_code = metadata.get("course_code", course_id)
                title = metadata.get("title", "Unknown")
                
                instructors = []
                for line in doc.split("\n"):
                    if line.startswith("Instructors:"):
                        instructor_text = line[len("Instructors:"):].strip()
                        instructors = [name.strip() for name in instructor_text.split(",")]
                        break
                
                for instructor in instructors:
                    if instructor:
                        instructor_course_pairs.append((instructor, course_code, title))
            except Exception as e:
                logger.error(f"Error processing course {course_id}: {str(e)}")
        
        logger.info(f"Processing {len(instructor_course_pairs)} instructor-course pairs...")
        for instructor, course_code, title in instructor_course_pairs:
            if self.add_professor(instructor, course_code, title):
                success_count += 1
        
        logger.info(f"Successfully added {success_count} professor-course relationships")
        return success_count