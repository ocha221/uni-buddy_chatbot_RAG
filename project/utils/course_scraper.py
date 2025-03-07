import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
from pathlib import Path
import time
import re
from datetime import datetime
import concurrent.futures
import os
import importlib.util
import sys


def import_module_from_path(script_name):
    script_path = Path(__file__).parent / f"{script_name}.py"
    spec = importlib.util.spec_from_file_location(script_name, script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[script_name] = module
    spec.loader.exec_module(module)
    return module

class CourseScraper:
    def __init__(self, base_url, output_dir="course_data"):
        self.base_url = base_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def get_semester_links(self):
        response = requests.get(self.base_url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        semester_courses = {}
        semester_pattern = r'/(\d+)(?:st|nd|rd|th)-semester/([^/]+/?$)'
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            match = re.search(semester_pattern, href)
            if match:
                semester_num = match.group(1)
                full_url = urljoin(self.base_url, href)
                if semester_num not in semester_courses:
                    semester_courses[semester_num] = set() 
                semester_courses[semester_num].add(full_url)
        
        return {key: list(value) for key, value in sorted(semester_courses.items(), key=lambda x: int(x[0]))}

    def extract_course_data(self, url, semester):
        response = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        course_data = {
            'url': url,
            'title': soup.title.string.strip() if soup.title else '',
            'course_code': '',
            'semester': semester,
            'hours': '',
            'ects': '',
            'instructors': [],
            'learning_outcomes': [],
            'course_content': [],
            'syllabus_link': '',
            'eclass_url': ''
        }

        main_content = soup.find('div', class_='entry-content') or soup.find('article')
        if not main_content:
            return course_data

    
        def get_content_after_marker(marker):
            header = main_content.find(string=lambda x: x and marker in x)
            if header:
                parent = header.find_parent()
                next_elem = parent.find_next(['p', 'div', 'ul'])
                if next_elem:
                    if next_elem.name == 'ul':
                        return [li.get_text().strip() for li in next_elem.find_all('li')]
                    return next_elem.get_text().strip()
            return None

    
        markers_and_fields = {
            'Κωδικός Μαθήματος': ('course_code', str),
            'Εξάμηνο Σπουδών': ('semester', int),
            'Ώρες/Εβδομάδα - ECTS': ('hours_ects', str),
            'Μαθησιακά Αποτελέσματα': ('learning_outcomes', list),
            'Ενδεικτικό Περιεχόμενο Μαθήματος': ('course_content', list)
        }

        for marker, (field, type_) in markers_and_fields.items():
            content = get_content_after_marker(marker)
            if content:
                if field == 'hours_ects':
                    parts = content.split('–') if '–' in content else content.split('-')
                    if len(parts) == 2:
                        course_data['hours'] = parts[0].strip()
                        course_data['ects'] = parts[1].strip()
                else:
                    course_data[field] = content

    
        pdf_link = main_content.find('a', href=lambda x: x and x.endswith('.pdf'))
        if pdf_link:
            course_data['syllabus_link'] = pdf_link['href']

    
        eclass_link = main_content.find('a', href=lambda x: x and 'eclass.uth.gr' in x)
        if eclass_link:
            course_data['eclass_url'] = eclass_link['href']

    
        instructor_links = main_content.find_all('a', href=lambda x: x and 'staff' in x)
        instructor_names = [link.get_text().strip() for link in instructor_links if link.get_text().strip()]
        if not instructor_names:
            if main_content.find(string=lambda x: x and 'θα οριστεί' in x):
                instructor_names = ['θα οριστεί']
        course_data['instructors'] = instructor_names

        return course_data

    def _scrape_semester(self, semester, urls, base_dir):
        """
        Scrape all courses for a specific semester.
        
        Args:
            semester: The semester number
            urls: List of course URLs for this semester
            base_dir: Base directory to save results
        """
        semester_dir = base_dir / f"semester_{semester}"
        semester_dir.mkdir(exist_ok=True)
        
        print(f"\nProcessing Semester {semester}")
        print(f"Found {len(urls)} courses")
        
        for url in urls:
            try:
                print(f"Scraping: {url}")
                course_data = self.extract_course_data(url, semester)
                
                filename = url.split('/')[-2] + '.json'
                with open(semester_dir / filename, 'w', encoding='utf-8') as f:
                    json.dump(course_data, ensure_ascii=False, indent=2, fp=f)
                
            except Exception as e:
                print(f"Error scraping {url}: {e}")
        
        print(f"Completed Semester {semester}")
        return semester

    def scrape_courses(self, max_workers=None):
        """
        Scrape all courses for all semesters in parallel.
        
        Args:
            max_workers: Maximum number of worker threads to use (default: number of CPUs)
        """
        if max_workers is None:
            max_workers = os.cpu_count()
            
        semester_links = self.get_semester_links()
        print(f"Found courses in {len(semester_links)} semesters")
        print(f"Using up to {max_workers} workers for parallel scraping")
        
        
        timestamp = datetime.now().strftime("%d_%m_%Y_scraped_on")
        timestamped_dir = self.output_dir / timestamp
        timestamped_dir.mkdir(exist_ok=True)
        
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            
            future_to_semester = {
                executor.submit(self._scrape_semester, semester, urls, timestamped_dir): semester
                for semester, urls in semester_links.items()
            }
            
            
            for future in concurrent.futures.as_completed(future_to_semester):
                semester = future_to_semester[future]
                try:
                    future.result()  
                except Exception as e:
                    print(f"Error processing semester {semester}: {e}")

        print(f"\nScraping completed! Files saved in: {timestamped_dir}")
        
       
        try:
            import subprocess
            print("\nRunning post-processing scripts...")    
            subprocess.run([sys.executable, str(Path(__file__).parent / "add_year.py"), str(timestamped_dir)])
            
            subprocess.run([sys.executable, str(Path(__file__).parent / "change_to_int.py"), str(timestamped_dir)])
            
            print("Post-processing completed successfully!")
        except Exception as e:
            print(f"Error during post-processing: {e}")

if __name__ == "__main__":
    scraper = CourseScraper("https://ds.uth.gr/undergraduate-studies/")
    scraper.scrape_courses()