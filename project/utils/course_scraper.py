import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
from pathlib import Path
import time
import re

class CourseScraper:
    def __init__(self, base_url, output_dir="courses_data"):
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


    def scrape_courses(self):
        semester_links = self.get_semester_links()
        print(f"Found courses in {len(semester_links)} semesters")
       
        for semester, urls in semester_links.items():
        
            semester_dir = self.output_dir / f"semester_{semester}"
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
                    
                    time.sleep(0.5) 
                    
                except Exception as e:
                    print(f"Error scraping {url}: {e}")

            print(f"Completed Semester {semester}")

        print(f"\nScraping completed! Files saved in: {self.output_dir}")


if __name__ == "__main__":
    scraper = CourseScraper("https://ds.uth.gr/undergraduate-studies/")
    scraper.scrape_courses()