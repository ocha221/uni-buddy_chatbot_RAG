import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
from pathlib import Path
import time
import datetime
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
from pathlib import Path
import time
import datetime
import re

class InternshipScraper:
    def __init__(self, base_url, output_dir="news_data"):
        self.base_url = base_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        self.today_date = datetime.datetime.now().strftime('%d_%m_%Y')
        self.today_dir = self.output_dir / f"{self.today_date}_scraped_on"
        self.today_dir.mkdir(exist_ok=True)
        
        self.month_mapping = {
            'Ιαν': '01',
            'Φεβ': '02',
            'Μαρ': '03',
            'Απρ': '04',
            'Μάι': '05',
            'Ιούν': '06',
            'Ιούλ': '07',
            'Αύγ': '08',
            'Σεπ': '09',
            'Οκτ': '10',
            'Νοέ': '11',
            'Δεκ': '12'
        }
    
    def format_date(self, date_str):
        """Convert date from YYYY-GreekMonth-DD to DD_MM_YYYY format"""
        try:
            parts = date_str.split('-')
            if len(parts) == 3:
                year = parts[0]
                month_abbr = parts[1]
                day = parts[2]
    
                month_num = self.month_mapping.get(month_abbr, '00')
                return f"{day}_{month_num}_{year}"
            return date_str
        except Exception:
            return date_str
        
    def get_internship_announcements(self):
        """Fetch all internship announcement URLs from the main page"""
        response = requests.get(self.base_url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        internship_links = []
        
        for article in soup.find_all('article'):
            link_elem = article.find('a', href=True)
            if link_elem:
                full_url = urljoin(self.base_url, link_elem['href'])
                internship_links.append(full_url)
        
        return internship_links
    
    def extract_internship_data(self, url):
        """Extract data from an individual internship announcement page"""
        response = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        internship_data = {
            'url': url,
            'title': soup.title.string.strip() if soup.title else '',
            'date_published': '',
            'content': '',
            'links': [],
            'files': [],
            'parsed_on': self.today_date
        }
        
        date_elem = soup.find(class_='published')
        if date_elem:
            internship_data['date_published'] = date_elem.text.strip()
        
        
        content_elem = soup.find(class_='et_pb_module et_pb_post_content et_pb_post_content_0_tb_body')
        if content_elem:
            internship_data['content'] = content_elem.get_text(separator='\n', strip=True)
            
            
            for link in content_elem.find_all('a', href=True):
                href = link['href']
                text = link.get_text().strip()
                internship_data['links'].append({
                    'text': text,
                    'url': href
                })
                
                
                if href.endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx')):
                    internship_data['files'].append({
                        'text': text,
                        'url': href
                    })
        
        return internship_data
    
    def scrape_internships(self):
        """Main method to scrape all internship announcements"""
        internship_links = self.get_internship_announcements()
        print(f"Found {len(internship_links)} internship announcements")
        
        for i, url in enumerate(internship_links, 1):
            try:
                print(f"Scraping [{i}/{len(internship_links)}]: {url}")
                internship_data = self.extract_internship_data(url)
                
                slug = url.split('/')[-2] if url.split('/')[-1] == '' else url.split('/')[-1]
                slug = re.sub(r'[^\w\-_]', '_', slug)
                
                if internship_data['date_published']:
                    formatted_date = self.format_date(internship_data['date_published'])
                    filename = f"{formatted_date}_{slug}.json"
                else:
                    filename = f"{slug}.json"
                
                with open(self.today_dir / filename, 'w', encoding='utf-8') as f:
                    json.dump(internship_data, ensure_ascii=False, indent=2, fp=f)
                
                time.sleep(0.5) 
                
            except Exception as e:
                print(f"Error scraping {url}: {e}")
        
        print(f"\nScraping completed! Files saved in: {self.today_dir}")

if __name__ == "__main__":
    scraper = InternshipScraper("https://ds.uth.gr/announcements/internship-related/")
    scraper.scrape_internships()