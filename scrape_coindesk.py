import trafilatura
import requests
from bs4 import BeautifulSoup
from scrapy import Spider, Request
from scrapy.crawler import CrawlerProcess
import json
import os
import re
from datetime import datetime
import logging
import traceback
import sys

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
        crawl_time = datetime.utcnow().isoformat()
        logging.info(f"Starting extraction at {crawl_time}")
        
        print(f"\n{'='*50}")  # Visual separator
        logging.info(f"Starting extraction for URL: {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Step 1: Download HTML
        logging.info("Fetching URL with requests...")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html_content = response.text
        logging.info(f"Downloaded HTML length: {len(html_content)} characters")
        
        # Step 2: Trafilatura fetch
        logging.info("Fetching URL with trafilatura...")
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            logging.info("Trafilatura fetch successful")
        else:
            logging.warning("Trafilatura fetch failed, using requests response")
            downloaded = html_content
        
        # Step 3: Extract content
        logging.info("Extracting content with trafilatura...")
        extracted_content = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            output_format='txt'
        )
        
        if extracted_content:
            logging.info(f"Extracted content length: {len(extracted_content)} characters")
            logging.info("First 200 characters of content:")
            logging.info(extracted_content[:200])
        else:
            logging.error("No content extracted!")
            return None
            
        # Step 4: Get metadata
        logging.info("Extracting metadata...")
        metadata = trafilatura.metadata.extract_metadata(downloaded)
        
        published_time = None
        updated_time = None
        author = None
        editor = None
        
        # Parse HTML for CoinDesk specific date formats
        soup = BeautifulSoup(downloaded, 'html.parser')
        
        # Extract editor
        editor_element = soup.find('p', class_='kDZZDY')
        if editor_element:
            editor_text = editor_element.text
            # Extract name after "Edited by"
            if "Edited by" in editor_text:
                editor = editor_text.split("Edited by")[-1].strip().rstrip('.')
                logging.info(f"Found editor: {editor}")
        
        # Extract published time
        published_element = soup.find('div', {'class': 'at-created'})
        if published_element:
            published_text = published_element.find('span', {'class': 'iOUkmj'})
            if published_text:
                published_time = published_text.text.strip()
                logging.info(f"Found published time: {published_time}")
        
        # Extract updated time
        updated_element = soup.find('div', {'class': 'at-updated'})
        if updated_element:
            updated_text = updated_element.find('span', {'class': 'iOUkmj'})
            if updated_text:
                updated_time = updated_text.text.replace('Updated', '').strip()
                logging.info(f"Found updated time: {updated_time}")
        
        # Extract author
        author_element = soup.find('a', href=lambda x: x and '/author/' in x)
        if author_element:
            author = author_element.text.strip()
            logging.info(f"Found author: {author}")
        
        # Fallback to metadata if direct HTML parsing fails
        if not any([published_time, updated_time, author]) and metadata:
            logging.info("Using metadata fallback...")
            if not published_time:
                published_time = str(metadata.date) if metadata.date else None
            if not updated_time:
                updated_time = str(metadata.modified) if hasattr(metadata, 'modified') else None
            if not author:
                author = str(metadata.author) if metadata.author else None
        
        result = {
            "content": extracted_content,
            "published_time": published_time,
            "updated_time": updated_time,
            "author": author,
            "editor": editor,
            "url": url,
            "crawl_time": crawl_time
        }
        
        logging.info("Extraction completed successfully")
        return result
        
    except Exception as e:
        logging.error(f"Error extracting content from {url}: {str(e)}")
        logging.error(traceback.format_exc())
        return None

# Generalized Scrapy Spider to crawl articles
class GeneralSpider(Spider):
    name = 'general_spider'
    allowed_domains = ['coindesk.com']
    start_urls = ['https://www.coindesk.com/']
    
    def __init__(self):
        super().__init__()
        self.seen_urls = set()
        # Use today's date for the output file
        self.date = datetime.now().strftime('%Y-%m-%d')
        self.output_file = f'articles_{self.date}.json'
        
        # Create or clear the output file
        with open(self.output_file, 'w') as f:
            pass

    def parse(self, response):
        logging.info(f"Parsing page: {response.url}")
        
        article_links = response.css('a[href*="/2024/"]::attr(href), a[href*="/2023/"]::attr(href)').getall()
        
        try:
            with open(self.output_file, 'a') as f:
                for href in article_links:
                    full_url = response.urljoin(href)
                    if (re.search(r'/(?:markets|business|tech|opinion)/\d{4}/\d{2}/\d{2}/', full_url) 
                        and full_url not in self.seen_urls):
                        logging.info(f"Found new matching article URL: {full_url}")
                        json.dump({'url': full_url, 'processed': False}, f)
                        f.write('\n')
                        self.seen_urls.add(full_url)
        except IOError as e:
            logging.error(f"Error writing to {self.output_file}: {str(e)}")

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler('spider.log'),
            logging.StreamHandler()
        ]
    )
    
    # Run the spider
    logging.info("Starting spider...")
    process = CrawlerProcess()
    process.crawl(GeneralSpider)
    process.start()
    
    # Process articles
    today = datetime.now().strftime('%Y-%m-%d')
    articles_file = f'articles_{today}.json'
    output_dir = "extracted_articles/coindesk"
    
    # Create output directory structure
    os.makedirs(output_dir, exist_ok=True)
    
    # Track processed URLs
    processed_urls = set()
    
    # Read and process articles
    try:
        with open(articles_file, 'r') as f:
            articles = [json.loads(line) for line in f]
        
        # Update articles with processing status
        for article in articles:
            url = article['url']
            if url in processed_urls:
                continue
                
            # Create filename using datetime and article name
            url_parts = url.rstrip('/').split('/')
            date_str = f"{url_parts[-4]}-{url_parts[-3]}-{url_parts[-2]}"
            article_name = url_parts[-1]
            filename = f"{date_str}_{article_name}.json"
            output_path = os.path.join(output_dir, filename)
            
            # Skip if already processed
            if os.path.exists(output_path):
                processed_urls.add(url)
                continue
            
            logging.info(f"Processing article: {url}")
            content = extract_content(url)
            
            if content:
                try:
                    with open(output_path, 'w', encoding='utf-8') as outfile:
                        json.dump(content, outfile, ensure_ascii=False, indent=2)
                    logging.info(f"Saved content to {output_path}")
                    processed_urls.add(url)
                except IOError as e:
                    logging.error(f"Error saving content to {output_path}: {str(e)}")
            else:
                logging.error(f"Failed to extract content from {url}")
        
        # Update the articles file with processed status
        with open(articles_file, 'w') as f:
            for article in articles:
                article['processed'] = article['url'] in processed_urls
                json.dump(article, f)
                f.write('\n')
                
    except Exception as e:
        logging.error(f"Error processing articles: {str(e)}")
        logging.error(traceback.format_exc())
