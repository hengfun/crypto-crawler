import trafilatura
import requests
from bs4 import BeautifulSoup
from scrapy import Spider, Request
from scrapy.crawler import CrawlerProcess
import json
import os
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Add at the top of the file
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('scraper_debug.log'),
        logging.StreamHandler()
    ]
)

# Extract content function
def extract_content(url):
    try:
        logging.debug(f"Starting extraction for URL: {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        # Step 1: Download the HTML content
        logging.debug("Fetching URL with requests...")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html_content = response.text
        
        # Step 2: Extract content using trafilatura
        logging.debug("Fetching URL with trafilatura...")
        downloaded = trafilatura.fetch_url(url, headers=headers)
        
        if not downloaded:
            logging.warning(f"trafilatura.fetch_url failed for {url}, using requests response")
            downloaded = html_content
        
        logging.debug("Extracting content with trafilatura...")
        extracted_content = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            output_format='text'
        )
        
        if not extracted_content:
            logging.warning("Trafilatura extraction failed, trying BeautifulSoup fallback")
            soup = BeautifulSoup(html_content, 'html.parser')
            article_content = soup.find('article') or soup.find('div', class_='article-content')
            if article_content:
                extracted_content = article_content.get_text(strip=True)
                logging.debug("Successfully extracted content with BeautifulSoup")
            else:
                logging.error("Failed to extract content with both methods")
                return None
        
        logging.debug(f"Extracted content length: {len(extracted_content) if extracted_content else 0}")
        
        # Extract metadata
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # More robust metadata extraction
        published_time = None
        modified_time = None
        author = None

        # Try multiple meta tag variations
        meta_tags = {
            'published_time': soup.find('meta', {'property': 'article:published_time'}) or
                            soup.find('meta', {'name': 'published_time'}) or
                            soup.find('meta', {'name': 'publication_date'}),
            'author': soup.find('meta', {'name': 'author'}) or
                     soup.find('meta', {'property': 'article:author'})
        }
        
        if meta_tags['published_time'] and meta_tags['published_time'].has_attr('content'):
            published_time = meta_tags['published_time']['content']
            logging.debug(f"Found published time: {published_time}")
            
        if meta_tags['author'] and meta_tags['author'].has_attr('content'):
            author = meta_tags['author']['content']
            logging.debug(f"Found author: {author}")

        result = {
            "url": url,
            "content": extracted_content,
            "published_time": published_time,
            "modified_time": modified_time,
            "author": author
        }
        
        logging.debug("Successfully created result dictionary")
        return result

    except Exception as e:
        logging.error(f"Error extracting content from {url}: {str(e)}", exc_info=True)
        return None

# Generalized Scrapy Spider to crawl articles
class GeneralSpider(Spider):
    name = 'general_spider'
    allowed_domains = ['coindesk.com']  # Update as needed
    start_urls = ['https://www.coindesk.com/']  # Update as needed

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'ROBOTSTXT_OBEY': False,  # Ignore robots.txt rules
        'FEEDS': {
            'articles.json': {'format': 'jsonlines'},  # Change to jsonlines to avoid extra data issues
        },
        'DOWNLOAD_DELAY': 0.5,  # To avoid getting blocked, reduce delay but not to zero
        'CONCURRENT_REQUESTS': 16,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
    }

    def parse(self, response):
        articles = response.css('a::attr(href)').getall()
        for href in articles:
            if href.startswith('/') or 'http' in href:  # Generalize for different types of URLs
                full_url = response.urljoin(href)
                yield {'url': full_url}

if __name__ == "__main__":
    # Step 1: Crawl for the latest articles
    process = CrawlerProcess(settings={
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'ROBOTSTXT_OBEY': False,  # Ignore robots.txt to avoid getting blocked
        'FEEDS': {
            'articles.json': {'format': 'jsonlines'},  # Change to jsonlines to avoid extra data issues
        },
        'DOWNLOAD_DELAY': 0.5,
        'CONCURRENT_REQUESTS': 16,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 8,
    })
    process.crawl(GeneralSpider)
    process.start()

    # Step 2: Load crawled articles and extract content using ThreadPoolExecutor for parallel processing
    output_dir = 'extracted_articles'
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    articles_dir = os.path.join(output_dir, timestamp)
    os.makedirs(articles_dir, exist_ok=True)

    all_articles = []

    with open('articles.json', 'r') as f:
        urls = []
        for line in f:
            line = line.strip()
            if line:
                try:
                    article_data = json.loads(line)
                    if 'url' in article_data:
                        urls.append(article_data['url'])
                except json.JSONDecodeError:
                    print(f"Skipping invalid JSON line: {line}")

    # Using ThreadPoolExecutor to extract content in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(extract_content, url): url for url in urls}
        for future in as_completed(future_to_url):
            try:
                content_data = future.result()
                if content_data:
                    content = content_data["content"]
                    published_time = content_data["published_time"]
                    modified_time = content_data["modified_time"]
                    url = content_data["url"]

                    match = re.search(r'/(\d{4}/\d{2}/\d{2})/([^/]+)/?$', url)
                    if match:
                        date_str = match.group(1).replace('/', '-')
                        title = match.group(2)

                        all_articles.append({
                            'url': url,
                            'date': date_str,
                            'title': title,
                            'content': content,
                            'published_time': published_time,
                            'modified_time': modified_time
                        })

                        filename = f"{date_str}_{title}.txt"
                        filepath = os.path.join(articles_dir, filename)
                        try:
                            with open(filepath, 'w', encoding='utf-8') as article_file:
                                article_file.write(f"URL: {url}\n")
                                if content_data.get("author"):
                                    article_file.write(f"Author: {content_data['author']}\n")
                                if content_data.get("published_time"):
                                    article_file.write(f"Time Published: {content_data['published_time']}\n")
                                article_file.write(f"Views: 0\n")
                                article_file.write(f"Shares: 0\n")
                                article_file.write(f"Crawl Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                                article_file.write("Content:\n\n")
                                
                                if content_data.get("content"):
                                    logging.debug(f"Writing content of length {len(content_data['content'])} to file")
                                    article_file.write(content_data["content"])
                                else:
                                    logging.error(f"No content available for {url}")
                                    article_file.write("No content extracted")
                                
                            logging.info(f"Successfully saved article: {filename}")
                            
                        except Exception as e:
                            logging.error(f"Error writing file {filepath}: {str(e)}", exc_info=True)
                    else:
                        print(f"Error: Unable to extract date and title from URL: {url}")
            except Exception as e:
                print(f"Error processing URL: {str(e)}")

    json_output_path = os.path.join(output_dir, f'all_articles_{timestamp}.json')
    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)

    print(f"\nExtraction complete!")
    print(f"Individual articles saved in: {articles_dir}")
    print(f"Combined JSON saved as: {json_output_path}")
