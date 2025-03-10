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


class NewsScraper:
    def __init__(self, base_url, output_dir="news_data"):
        self.base_url = base_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        self.today_date = datetime.datetime.now().strftime("%d_%m_%Y")
        self.today_dir = self.output_dir / f"{self.today_date}_scraped_on"
        self.today_dir.mkdir(exist_ok=True)

        self.month_mapping = {
            "Ιαν": "01",
            "Φεβ": "02",
            "Μαρ": "03",
            "Απρ": "04",
            "Μάι": "05",
            "Ιούν": "06",
            "Ιούλ": "07",
            "Αύγ": "08",
            "Σεπ": "09",
            "Οκτ": "10",
            "Νοέ": "11",
            "Δεκ": "12",
        }

    def format_date(self, date_str):
        """from YYYY-GreekMonth-DD to DD_MM_YYYY (gia to epoch)"""
        try:
            parts = date_str.split("-")
            if len(parts) == 3:
                year = parts[0]
                month_abbr = parts[1]
                day = parts[2]

                month_num = self.month_mapping.get(month_abbr, "00")
                return f"{day}_{month_num}_{year}"
            return date_str
        except Exception:
            return date_str

    def classify_news_by_keywords(self, content):
        keywords = {
            "internship-related": ["πρακτική", "άσκηση", "internship", "πρακτικη", "ασκηση"],
            "student-related": ["φοιτητ", "σπουδαστ", "εξάμην", "φοιτητές", "μαθητ", "εξεταστική", "διαλέξ"],
            "distinctions-awards": ["διάκρισ", "βραβε", "award", "βραβείο", "αριστεί", "διακρίθηκ"],
            "events-activities": ["εκδήλωση", "σεμινάριο", "workshop", "διάλεξη", "ημερίδα", "συνέδριο", "παρουσίαση"],
            "vacancies": ["θέση", "προκήρυξη", "vacancy", "διδασκόντων", "πρόσληψη", "αίτηση", "εργασία"]
        }
        
        detected_types = []
        for type_name, words in keywords.items():
            if any(word in content for word in words):
                detected_types.append(type_name)
        
        return detected_types

    def get_news(self):
        """Fetch all news from #"""
        response = requests.get(self.base_url, headers=self.headers)
        soup = BeautifulSoup(response.text, "html.parser")

        links = []
        for article in soup.find_all("article"):
            link_elem = article.find("a", href=True)
            if link_elem:
                full_url = urljoin(self.base_url, link_elem["href"])
                links.append(full_url)

        return links

    def extract_news_data(self, url):
        """Extract data from individual npages"""
        response = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, "html.parser")

        news_data = {
            "url": url,
            "title": soup.title.string.strip() if soup.title else "",
            "date_published": "",
            "content": "",
            "links": [],
            "files": [],
            "parsed_on": self.today_date,
        }

        date_elem = soup.find(class_="published")
        if date_elem:
            news_data["date_published"] = date_elem.text.strip()

        news_types = []
        type_mapping = {
            "Φοιτητικά": "student-related",
            "Διακρίσεις": "distinctions-awards",
            "Πρακτική Άσκηση": "internship-related",
            "Εκδηλώσεις-Δραστηριότητες": "events-activities",
            "Προκήρυξη Θέσεων": "vacancies",
        }

        meta_container = soup.find(class_="et_pb_title_meta_container")
        if meta_container:
            for link in meta_container.find_all("a"):
                link_text = link.get_text().strip()
                if link_text in type_mapping:
                    news_types.append(type_mapping[link_text])

        if not news_types or len(news_types) < 2:  
            content_for_classification = f"{news_data['title']} {news_data['content']}".lower()
            keyword_types = self.classify_news_by_keywords(content_for_classification)
            
            for kw_type in keyword_types:
                if kw_type not in news_types:
                    news_types.append(kw_type)
                    
        news_data["news_types"] = news_types or ["general"]

        if news_data["date_published"]:
            try:
                date_parts = news_data["date_published"].split("-")
                if len(date_parts) == 3:
                    year = int(date_parts[0])
                    month_abbr = date_parts[1]
                    day = int(date_parts[2])

                    month_num = int(self.month_mapping.get(month_abbr, "1"))

                    date_obj = datetime.datetime(year, month_num, day)
                    epoch_timestamp = int(date_obj.timestamp())

                    news_data["date_epoch"] = epoch_timestamp
            except Exception as e:
                print(f"Error converting date to epoch: {e}")

        content_elem = soup.find(
            class_="et_pb_module et_pb_post_content et_pb_post_content_0_tb_body"
        )
        if content_elem:
            news_data["content"] = content_elem.get_text(
                separator="\n", strip=True
            )

            for link in content_elem.find_all("a", href=True):
                href = link["href"]
                text = link.get_text().strip()
                news_data["links"].append({"text": text, "url": href})

                if href.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx")):
                    news_data["files"].append({"text": text, "url": href})

        return news_data

    def scrape_news(self):
        """scrape everything""" #TODO multithreaded
        links = self.get_news()
        print(f"Found {len(links)} announcements")

        for i, url in enumerate(links, 1):
            try:
                print(f"Scraping [{i}/{len(links)}]: {url}")
                news_data = self.extract_news_data(url)

                slug = (
                    url.split("/")[-2]
                    if url.split("/")[-1] == ""
                    else url.split("/")[-1]
                )
                slug = re.sub(r"[^\w\-_]", "_", slug)

                if news_data["date_published"]:
                    formatted_date = self.format_date(news_data["date_published"])
                    filename = f"{formatted_date}_{slug}.json"
                else:
                    filename = f"{slug}.json"

                with open(self.today_dir / filename, "w", encoding="utf-8") as f:
                    json.dump(news_data, ensure_ascii=False, indent=2, fp=f)

                time.sleep(0.5)

            except Exception as e:
                print(f"Error scraping {url}: {e}")

        print(f"\nScraping completed! Files saved in: {self.today_dir}")


if __name__ == "__main__":
    scraper = NewsScraper("https://ds.uth.gr/announcements/")
    scraper.scrape_news()
