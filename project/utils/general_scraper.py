import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
from pathlib import Path
import time
import datetime
import re
import threading
import logging
from queue import Queue
import random
import hashlib


class EnhancedScraper:
    def __init__(
        self,
        base_url,
        output_dir="scraped_data",
        max_threads=10,
        max_depth=5,
        delay_range=(0.5, 1.0),
        respect_robots=True,
    ):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.max_threads = max_threads
        self.max_depth = max_depth
        self.delay_range = delay_range
        self.respect_robots = respect_robots

        self.visited_urls = set()
        self.queued_urls = set()
        self.url_queue = Queue()
        self.lock = threading.Lock()
        self.active_threads = 0
        self.thread_activity_event = threading.Event()
        self.thread_activity_event.set()

        self.today_date = datetime.datetime.now().strftime("%Y-%m-%d")
        self.today_dir = self.output_dir / f"scrape_{self.today_date}"
        self.today_dir.mkdir(exist_ok=True)

        self.headers = {
            "User-Agent": "(alaganis@uth.gr) Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

        self.logger = self._setup_logger()

        self.disallowed_paths = []
        if self.respect_robots:
            self._parse_robots_txt()

    def _setup_logger(self):
        """Configure enhanced logger for tracking scraping progress"""
        logger = logging.getLogger("EnhancedScraper")
        logger.setLevel(logging.INFO)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        file_handler = logging.FileHandler(
            self.today_dir / "scraper.log", encoding="utf-8"
        )
        file_handler.setLevel(logging.INFO)

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        logger.propagate = False

        return logger

    def _parse_robots_txt(self):
        """Parse robots.txt to respect website crawling rules"""
        try:
            robots_url = urljoin(self.base_url, "/robots.txt")
            response = requests.get(robots_url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                lines = response.text.split("\n")
                user_agent_applies = False

                for line in lines:
                    line = line.strip()

                    if line.lower().startswith("user-agent:"):
                        agent = line[11:].strip()
                        user_agent_applies = agent == "*" or "python" in agent.lower()

                    elif user_agent_applies and line.lower().startswith("disallow:"):
                        path = line[9:].strip()
                        if path:
                            self.disallowed_paths.append(path)

                self.logger.info(
                    f"Found {len(self.disallowed_paths)} disallowed paths in robots.txt"
                )
            else:
                self.logger.info("No robots.txt found or couldn't access it")
        except Exception as e:
            self.logger.error(f"Error parsing robots.txt: {e}")

    def is_allowed_url(self, url):
        if not self.respect_robots or not self.disallowed_paths:
            return True

        parsed_url = urlparse(url)
        path = parsed_url.path

        for disallowed in self.disallowed_paths:
            if path.startswith(disallowed):
                return False

        return True

    def is_valid_url(self, url):
        """Enhanced check if URL is valid for scraping"""
        try:
            parsed_url = urlparse(url)

            if not parsed_url.netloc and not parsed_url.path:
                return False

            if parsed_url.netloc and parsed_url.netloc != self.domain:
                return False

            if url in self.visited_urls or url in self.queued_urls:
                return False

            if re.search(
                r"\.(pdf|doc|docx|xls|xlsx|zip|rar|jpg|jpeg|png|gif|css|js)$",
                url,
                re.IGNORECASE,
            ):
                return False

            if len(parsed_url.fragment) > 0 or len(parsed_url.query) > 100:
                return False

            if not self.is_allowed_url(url):
                return False

            return True

        except Exception:
            return False

    def normalize_url(self, url):
        """Normalize URL to prevent duplicates"""
        url = url.rstrip("/")

        parsed_url = urlparse(url)
        if parsed_url.query:
            query_params = sorted(parsed_url.query.split("&"))
            new_query = "&".join(query_params)
            url = url.replace(parsed_url.query, new_query)

        return url

    def extract_all_links(self, soup, current_url):
        """links apo pantou"""
        links = []
        base_url = current_url

        base_tag = soup.find("base", href=True)
        if base_tag:
            base_url = base_tag["href"]

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]

            if not href or href.startswith(("javascript:", "mailto:", "tel:")):
                continue

            full_url = urljoin(base_url, href)

            full_url = self.normalize_url(full_url)

            if self.is_valid_url(full_url):
                links.append(full_url)

        navigation_elements = [
            soup.find_all(class_=re.compile(r"et_menu_container")),
            soup.find_all(class_=re.compile(r"et-menu")),
            soup.find_all(class_=re.compile(r"menu")),
            soup.find_all(class_=re.compile(r"nav")),
            soup.find_all("nav"),
            soup.find_all("header"),
        ]

        for nav_element_list in navigation_elements:
            for nav_element in nav_element_list:
                for a_tag in nav_element.find_all("a", href=True):
                    href = a_tag["href"]

                    if not href or href.startswith(("javascript:", "mailto:", "tel:")):
                        continue

                    full_url = urljoin(base_url, href)

                    full_url = self.normalize_url(full_url)

                    if self.is_valid_url(full_url):
                        links.append(full_url)

        unique_links = []
        seen = set()
        for link in links:
            if link not in seen:
                unique_links.append(link)
                seen.add(link)

        return unique_links

    def get_links_from_page(self, url, depth=0):
        """Get valid links from a page with comprehensive handling"""
        if depth >= self.max_depth:
            return []

        try:
            response = requests.get(
                url, headers=self.headers, timeout=15, allow_redirects=True
            )
            if response.status_code != 200:
                self.logger.warning(f"Got status code {response.status_code} for {url}")
                return []

            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type:
                self.logger.info(
                    f"Skipping non-HTML content type: {content_type} for {url}"
                )
                return []

            soup = BeautifulSoup(response.text, "html.parser")

            links = self.extract_all_links(soup, url)
            self.logger.info(f"Found {len(links)} valid links on {url}")

            return links

        except requests.exceptions.Timeout:
            self.logger.warning(f"Timeout when requesting {url}")
            return []
        except requests.exceptions.ConnectionError:
            self.logger.warning(f"Connection error when requesting {url}")
            return []
        except Exception as e:
            self.logger.error(f"Error getting links from {url}: {e}")
            return []

    def _find_content_sections_recursive(self, element, sections=None, prefix=""):
        if sections is None:
            sections = []

        if element.has_attr("class") and any(
            "et_pb_row" in cls for cls in element.get("class", [])
        ):
            section_id = element.get("id", f"{prefix}section_{len(sections) + 1}")

            text_inners = element.find_all(class_="et_pb_text_inner")
            content = ""
            headings = []
            links = []

            if text_inners:
                for text_elem in text_inners:

                    for heading in text_elem.find_all(
                        ["h1", "h2", "h3", "h4", "h5", "h6"]
                    ):
                        headings.append(
                            {
                                "level": heading.name,
                                "text": heading.get_text(strip=True),
                            }
                        )

                    paragraphs = text_elem.find_all("p")
                    if paragraphs:
                        for p in paragraphs:
                            if p.get_text(strip=True):
                                content += p.get_text(strip=True) + "\n\n"
                    else:

                        content += text_elem.get_text(separator="\n\n", strip=True)

                    for a_tag in text_elem.find_all("a", href=True):
                        link_text = a_tag.get_text(strip=True)
                        href = a_tag["href"]
                        if href and not href.startswith(
                            ("javascript:", "mailto:", "tel:")
                        ):
                            links.append({"text": link_text, "url": href})

            if content.strip() or headings or links:
                sections.append(
                    {
                        "section_id": section_id,
                        "content": content.strip(),
                        "headings": headings,
                        "links": links,
                    }
                )

        for i, child in enumerate(element.find_all(recursive=False)):
            self._find_content_sections_recursive(child, sections, f"{prefix}{i+1}_")

        return sections

    def extract_page_data(self, url, soup=None):
        """Extract data from a page with comprehensive recursive traversal"""
        try:
            if not soup:
                response = requests.get(url, headers=self.headers, timeout=15)

                if response.status_code != 200:
                    self.logger.warning(
                        f"Failed to fetch {url} - Status code: {response.status_code}"
                    )
                    return None

                soup = BeautifulSoup(response.text, "html.parser")

            page_data = {
                "url": url,
                "title": soup.title.string.strip() if soup.title else "",
                "extracted_on": datetime.datetime.now().isoformat(),
                "content_sections": [],
                "links": [],
                "metadata": {},
            }

            meta_tags = soup.find_all("meta")
            for tag in meta_tags:
                if tag.get("name") and tag.get("content"):
                    page_data["metadata"][tag.get("name")] = tag.get("content")

            all_page_links = []
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if href and not href.startswith(("javascript:", "mailto:", "tel:")):
                    link_text = a_tag.get_text(strip=True)
                    full_url = urljoin(url, href)
                    all_page_links.append({"text": link_text, "url": full_url})

            page_data["links"] = all_page_links

            sections = self._find_content_sections_recursive(soup)

            if sections:
                page_data["content_sections"] = sections
            else:

                for pattern in [
                    "et_pb_section",
                    "et_pb_row",
                    "et_pb_column",
                    "et_pb_module",
                    "et_pb_text",
                ]:
                    elements = soup.find_all(class_=re.compile(pattern))
                    for i, elem in enumerate(elements):
                        content = elem.get_text(separator="\n\n", strip=True)
                        if content:
                            section = {
                                "section_id": f"{pattern}_{i+1}",
                                "content": content,
                                "headings": [],
                                "links": [],
                            }

                            for heading in elem.find_all(
                                ["h1", "h2", "h3", "h4", "h5", "h6"]
                            ):
                                section["headings"].append(
                                    {
                                        "level": heading.name,
                                        "text": heading.get_text(strip=True),
                                    }
                                )

                            for a_tag in elem.find_all("a", href=True):
                                href = a_tag["href"]
                                if href and not href.startswith(
                                    ("javascript:", "mailto:", "tel:")
                                ):
                                    section["links"].append(
                                        {
                                            "text": a_tag.get_text(strip=True),
                                            "url": urljoin(url, href),
                                        }
                                    )

                            page_data["content_sections"].append(section)

            if not page_data["content_sections"]:

                main_elements = []
                for selector in [
                    "main",
                    "article",
                    "div.content",
                    "div.main-content",
                    ".et_pb_post_content",
                ]:
                    elements = soup.select(selector)
                    if elements:
                        main_elements.extend(elements)

                if not main_elements:

                    main_elements = [soup.find("body")]

                for i, elem in enumerate(main_elements):
                    if elem:

                        for s in elem.find_all(["script", "style", "meta", "link"]):
                            s.extract()

                        content = elem.get_text(separator="\n\n", strip=True)

                        if content:
                            page_data["content_sections"].append(
                                {
                                    "section_id": f"main_content_{i+1}",
                                    "content": content,
                                    "headings": [
                                        {
                                            "level": h.name,
                                            "text": h.get_text(strip=True),
                                        }
                                        for h in elem.find_all(
                                            ["h1", "h2", "h3", "h4", "h5", "h6"]
                                        )
                                    ],
                                    "links": [
                                        {
                                            "text": a.get_text(strip=True),
                                            "url": urljoin(url, a["href"]),
                                        }
                                        for a in elem.find_all("a", href=True)
                                        if a["href"]
                                        and not a["href"].startswith(
                                            ("javascript:", "mailto:", "tel:")
                                        )
                                    ],
                                }
                            )

            page_data["page_type"] = self.classify_page(url, page_data)

            return page_data

        except Exception as e:
            self.logger.error(f"Error extracting data from {url}: {e}")
            return None

    def classify_page(self, url, page_data):
        """Improved page type classification based on URL and content"""
        url_lower = url.lower()
        title_lower = page_data["title"].lower() if page_data["title"] else ""

        all_text = ""
        for section in page_data["content_sections"]:
            all_text += section["content"].lower() + " "
            for heading in section.get("headings", []):
                all_text += heading.get("text", "").lower() + " "

        classifications = {
            "course": [
                "course",
                "μάθημα",
                "mathima",
                "syllabus",
                "διδασκαλία",
                "διαλέξεις",
            ],
            "faculty": [
                "staff",
                "faculty",
                "professor",
                "καθηγητής",
                "καθηγητές",
                "διδάσκοντες",
                "ακαδημαϊκό προσωπικό",
            ],
            "department": ["department", "τμήμα", "τμηματ"],
            "program": [
                "program",
                "πρόγραμμα σπουδών",
                "curriculum",
                "προπτυχιακό",
                "μεταπτυχιακό",
            ],
            "news": ["news", "announcement", "ανακοίνωση", "νέα", "ειδήσεις"],
            "event": ["event", "εκδήλωση", "συνέδριο", "ημερίδα", "workshop"],
            "research": [
                "research",
                "έρευνα",
                "ερευνητικό",
                "publications",
                "δημοσιεύσεις",
            ],
            "contact": [
                "contact",
                "επικοινωνία",
                "address",
                "διεύθυνση",
                "τηλέφωνο",
                "email",
            ],
            "about": ["about", "σχετικά", "history", "ιστορία", "mission", "αποστολή"],
        }

        path = urlparse(url).path
        path_parts = [p.lower() for p in path.split("/") if p]

        detected_types = []

        for page_type, keywords in classifications.items():
            for part in path_parts:
                if any(keyword in part for keyword in keywords):
                    detected_types.append(page_type)
                    break

        for page_type, keywords in classifications.items():
            if page_type not in detected_types:
                if any(keyword in title_lower for keyword in keywords):
                    detected_types.append(page_type)
                    continue

                if any(keyword in all_text for keyword in keywords):
                    detected_types.append(page_type)

        if not detected_types:
            detected_types.append("general")

        return detected_types

    def save_page_data(self, page_data):
        """Save the extracted page data"""
        if not page_data:
            return False

        try:

            url_hash = hashlib.md5(page_data["url"].encode()).hexdigest()[:10]

            primary_type = (
                page_data["page_type"][0] if page_data["page_type"] else "general"
            )

            type_dir = self.today_dir / primary_type
            type_dir.mkdir(exist_ok=True)

            filename = f"{url_hash}.json"
            filepath = type_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(page_data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"Saved data from {page_data['url']} to {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving page data for {page_data['url']}: {e}")
            return False

    def worker(self):
        """Improved worker function for threads"""
        with self.lock:
            self.active_threads += 1

        while True:
            try:

                try:
                    url_data = self.url_queue.get(timeout=2)
                    if not url_data:
                        break

                    url, depth = url_data
                except Exception:

                    if self.url_queue.empty() and self.active_threads <= 1:
                        break
                    continue

                self.thread_activity_event.set()

                try:

                    with self.lock:
                        if url in self.visited_urls:
                            self.url_queue.task_done()
                            continue
                        self.visited_urls.add(url)

                    self.logger.info(f"Processing: {url} (depth: {depth})")

                    time.sleep(random.uniform(*self.delay_range))

                    response = requests.get(url, headers=self.headers, timeout=15)

                    if response.status_code == 200:

                        soup = BeautifulSoup(response.text, "html.parser")

                        page_data = self.extract_page_data(url, soup)

                        if page_data:
                            self.save_page_data(page_data)

                        if depth < self.max_depth:
                            links = self.extract_all_links(soup, url)

                            for link in links:
                                with self.lock:
                                    if (
                                        link not in self.visited_urls
                                        and link not in self.queued_urls
                                    ):
                                        self.url_queue.put((link, depth + 1))
                                        self.queued_urls.add(link)
                    else:
                        self.logger.warning(
                            f"Failed to fetch {url}: HTTP {response.status_code}"
                        )

                except requests.RequestException as e:
                    self.logger.warning(f"Request error for {url}: {e}")
                except Exception as e:
                    self.logger.error(f"Error processing {url}: {e}")
                finally:
                    self.url_queue.task_done()

            except Exception as e:
                self.logger.error(f"Unexpected worker error: {e}")

        with self.lock:
            self.active_threads -= 1

    def scrape(self):
        """Start the scraping process with improved coordination"""
        self.logger.info(f"Starting scraper for {self.base_url}")
        self.logger.info(f"Output directory: {self.today_dir}")
        self.logger.info(
            f"Max depth: {self.max_depth}, Max threads: {self.max_threads}"
        )

        start_time = time.time()

        normalized_base_url = self.normalize_url(self.base_url)
        self.url_queue.put((normalized_base_url, 0))
        self.queued_urls.add(normalized_base_url)

        threads = []
        for i in range(self.max_threads):
            thread = threading.Thread(target=self.worker, name=f"Worker-{i}")
            thread.daemon = True
            thread.start()
            threads.append(thread)
            time.sleep(0.1)

        try:
            while any(thread.is_alive() for thread in threads):
                queue_size = self.url_queue.qsize()
                visited = len(self.visited_urls)

                self.logger.info(
                    f"Progress: {visited} pages processed, {queue_size} in queue"
                )

                self.thread_activity_event.clear()
                activity_detected = self.thread_activity_event.wait(timeout=30)

                if not activity_detected and self.url_queue.empty():
                    self.logger.info(
                        "No activity detected and queue empty, finishing up"
                    )
                    break

                time.sleep(5)

        except KeyboardInterrupt:
            self.logger.info("Scraping interrupted by user!")

        end_time = time.time()
        duration = end_time - start_time
        pages_per_second = len(self.visited_urls) / duration if duration > 0 else 0

        self.logger.info(f"Scraping completed!")
        self.logger.info(f"Total pages visited: {len(self.visited_urls)}")
        self.logger.info(
            f"Duration: {duration:.2f} seconds ({pages_per_second:.2f} pages/second)"
        )
        self.logger.info(f"Data saved to: {self.today_dir}")

        self._create_summary()

        return len(self.visited_urls)

    def _create_summary(self):
        """Create a summary file with scraping statistics"""
        try:

            type_counts = {}
            for path in self.today_dir.glob("*/*.json"):
                page_type = path.parent.name
                type_counts[page_type] = type_counts.get(page_type, 0) + 1

            summary = {
                "scrape_date": self.today_date,
                "base_url": self.base_url,
                "total_pages": len(self.visited_urls),
                "by_type": type_counts,
                "settings": {
                    "max_depth": self.max_depth,
                    "max_threads": self.max_threads,
                    "respect_robots": self.respect_robots,
                },
            }

            with open(self.today_dir / "summary.json", "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)

        except Exception as e:
            self.logger.error(f"Error creating summary: {e}")


if __name__ == "__main__":
    scraper = EnhancedScraper(
        base_url="https://ds.uth.gr/",
        max_threads=10,
        max_depth=5,
        delay_range=(0.3, 1.0),
    )
    scraper.scrape()
