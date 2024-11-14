import trafilatura
from bs4 import BeautifulSoup
from scrapy import Spider, Request
from scrapy.crawler import CrawlerProcess
import json
import os
import re
from datetime import datetime
import logging
from scrapy.downloadermiddlewares.useragent import UserAgentMiddleware
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import time
from http.cookies import SimpleCookie
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class RandomUserAgentMiddleware(UserAgentMiddleware):
    def __init__(self, user_agent=''):
        super().__init__()
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/119.0.0.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0'
        ]

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings['USER_AGENT'])

    def process_request(self, request, spider):
        request.headers['User-Agent'] = random.choice(self.user_agents)

def extract_content_with_selenium(url):
    crawl_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-gpu')
    options.add_argument('--lang=en-US')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--enable-javascript')
    
    try:
        driver = uc.Chrome(
            options=options,
            version_main=130,
            use_subprocess=True
        )
        driver.get(url)
        time.sleep(random.uniform(5, 10))  # Wait for page load
        
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Updated view count extraction
        views = 0
        shares = 0
        try:
            # Find all elements with the same class pattern
            number_elements = driver.find_elements(By.CSS_SELECTOR, "span.text-black.text-13.font-semibold")
            for element in number_elements:
                text = element.text.strip()
                if text.isdigit():
                    # Get the following span to determine if this is views or shares
                    parent = element.find_element(By.XPATH, "./..")
                    label = parent.find_element(By.CSS_SELECTOR, "span.text-13.text-custom-coh-gray-dark.font-light").text.strip()
                    
                    if "Total views" in label:
                        views = int(text)
                    if "Total shares" in label:
                        shares = int(text)
            
            logging.debug(f"Found view count: {views}")
            logging.debug(f"Found share count: {shares}")
        except Exception as e:
            logging.warning(f"Error extracting views/shares: {str(e)}")
            
        html_content = driver.page_source
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Log the page source for debugging
        html_content = driver.page_source
        logging.debug(f"Page source length: {len(html_content)}")
        logging.debug("Sample of page source:")
        logging.debug(html_content[:1000])
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Try multiple selectors for content
        content_parts = []
        
        # Try to get title
        title_selectors = ['h1.post__title', 'h1.article__title', 'h1']
        for selector in title_selectors:
            title = soup.select_one(selector)
            if title:
                content_parts.append(title.text.strip())
                logging.debug(f"Found title using selector {selector}: {title.text.strip()}")
                break
                
        # Try to get main content
        content_selectors = [
            'div.post__content',
            'div.article-content',
            'article',
            'main'
        ]
        
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                logging.debug(f"Found content using selector {selector}")
                # Get all paragraphs
                paragraphs = content_div.find_all(['p', 'h2', 'h3'])
                for p in paragraphs:
                    # Skip if it's a social media embed or has specific classes to ignore
                    if not p.has_attr('class') or not any(c in ['social-embed', 'post__lead'] for c in p.get('class', [])):
                        text = p.text.strip()
                        if text:
                            content_parts.append(text)
                            logging.debug(f"Added paragraph: {text[:50]}...")
                break
        
        article_text = '\n\n'.join(filter(None, content_parts))
        logging.debug(f"Total extracted content length: {len(article_text)}")
        
        if not article_text:
            logging.error("No content extracted using standard selectors, trying alternative method")
            # Try using trafilatura as backup
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                article_text = trafilatura.extract(downloaded)
                logging.debug("Content extracted using trafilatura")
        
        # Get metadata
        try:
            author_selectors = [
                'span.post-meta__author-name',
                'a.article__author-link',
                'div.article__author'
            ]
            author = "Unknown"
            for selector in author_selectors:
                author_elem = soup.select_one(selector)
                if author_elem:
                    author = author_elem.text.strip()
                    break
            
            time_selectors = [
                'time.post-meta__publish-date',
                'time.article__date',
                'time'
            ]
            time_published = "Unknown"
            for selector in time_selectors:
                time_elem = soup.select_one(selector)
                if time_elem:
                    time_published = time_elem.text.strip()
                    break
                    
            logging.debug(f"Found metadata - Author: {author}, Time: {time_published}")
        except Exception as e:
            logging.warning(f"Error extracting metadata: {str(e)}")
            author = "Unknown"
            time_published = "Unknown"

        return {
            'url': url,
            'author': author,
            'time_published': time_published,
            'views': views,
            'shares': shares,
            'text': article_text,
            'crawl_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'timestamp': datetime.now().isoformat()
        }
            
    except Exception as e:
        logging.error(f"Error during content extraction: {str(e)}")
        return None
    finally:
        if driver:
            driver.quit()

class CointelegraphSpider(Spider):
    name = 'cointelegraph_spider'
    allowed_domains = ['cointelegraph.com']
    start_urls = ['https://cointelegraph.com/']
    
    # Add user agents list
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/119.0.0.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0'
    ]

    def __init__(self):
        super().__init__()
        options = uc.ChromeOptions()
        # Add more random viewport sizes
        width = random.randint(1200, 1920)
        height = random.randint(800, 1080)
        options.add_argument(f'--window-size={width},{height}')
        
        # Add more realistic browser behavior
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument(f'--user-agent={random.choice(self.user_agents)}')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-web-security')
        options.add_argument('--allow-running-insecure-content')
        
        # Add timezone and language randomization
        options.add_argument('--lang=en-US,en;q=0.9')
        timezones = ['America/New_York', 'Europe/London', 'Asia/Tokyo']
        options.add_argument(f'--timezone={random.choice(timezones)}')
        
        try:
            self.driver = uc.Chrome(
                options=options,
                version_main=130,
                use_subprocess=True,
                driver_executable_path=None
            )
            
            # Add more stealth
            stealth_js = """
                // Override navigator properties
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                
                // Add random screen properties
                Object.defineProperty(window, 'innerWidth', {get: () => Math.floor(Math.random() * (1920 - 1200) + 1200)});
                Object.defineProperty(window, 'innerHeight', {get: () => Math.floor(Math.random() * (1080 - 800) + 800)});
                
                // Add random browser features
                Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => Math.floor(Math.random() * (16 - 2) + 2)});
                Object.defineProperty(navigator, 'deviceMemory', {get: () => Math.floor(Math.random() * (32 - 2) + 2)});
            """
            self.driver.execute_script(stealth_js)
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Chrome: {str(e)}")
            raise

    def start_requests(self):
        for url in self.start_urls:
            try:
                # Add random delays before starting
                time.sleep(random.uniform(2, 5))
                
                self.logger.info(f"Starting request to {url}")
                self.driver.get(url)
                
                # Simulate human scrolling behavior
                def scroll_randomly():
                    total_height = self.driver.execute_script("return document.body.scrollHeight")
                    current_position = 0
                    while current_position < total_height:
                        scroll_amount = random.randint(100, 300)
                        current_position += scroll_amount
                        self.driver.execute_script(f"window.scrollTo(0, {current_position});")
                        time.sleep(random.uniform(0.5, 1.5))
                
                # Wait for Cloudflare with more sophisticated checks
                max_attempts = 15  # Increased attempts
                attempt = 0
                
                while attempt < max_attempts:
                    self.logger.info(f"Attempt {attempt + 1}/{max_attempts} to pass Cloudflare")
                    
                    # Random waiting period
                    time.sleep(random.uniform(3, 7))
                    
                    # Simulate human-like behavior
                    try:
                        actions = ActionChains(self.driver)
                        
                        # Random mouse movements
                        for _ in range(random.randint(2, 5)):
                            x_offset = random.randint(-100, 100)
                            y_offset = random.randint(-100, 100)
                            actions.move_by_offset(x_offset, y_offset).perform()
                            time.sleep(random.uniform(0.1, 0.3))
                        
                        # Sometimes click random coordinates
                        if random.random() < 0.3:
                            actions.click().perform()
                        
                        # Sometimes scroll
                        if random.random() < 0.3:
                            scroll_randomly()
                            
                    except Exception as e:
                        self.logger.error(f"Error during mouse movement: {str(e)}")
                    
                    # Check if we've passed the challenge
                    try:
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "article, .post-card-inline, .posts-listing"))
                        )
                        self.logger.info("Found content elements, likely passed Cloudflare!")
                        break
                    except:
                        self.logger.info("Still waiting for content to load...")
                    
                    attempt += 1
                
                # Final verification
                html = self.driver.page_source
                if "Just a moment" not in html:
                    self.logger.info("Successfully bypassed Cloudflare!")
                    cookies = self.driver.get_cookies()
                    cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                    
                    yield Request(
                        url=url,
                        cookies=cookie_dict,
                        callback=self.parse,
                        dont_filter=True,
                        meta={'html': html},
                        headers={
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'Connection': 'keep-alive',
                            'Upgrade-Insecure-Requests': '1',
                            'Sec-Fetch-Dest': 'document',
                            'Sec-Fetch-Mode': 'navigate',
                            'Sec-Fetch-Site': 'none',
                            'Sec-Fetch-User': '?1',
                            'TE': 'trailers'
                        }
                    )
                else:
                    self.logger.error("Failed to bypass Cloudflare after all attempts")
                    
            except Exception as e:
                self.logger.error(f"Error in start_requests: {str(e)}")

    def parse(self, response):
        html = response.meta.get('html', response.text)
        soup = BeautifulSoup(html, 'html.parser')
        
        articles = soup.find_all('a', href=True)
        for article in articles:
            href = article['href']
            if '/news/' in href:
                full_url = response.urljoin(href)
                yield Request(
                    url=full_url,
                    callback=self.parse_article,
                    dont_filter=True
                )

    def parse_article(self, response):
        try:
            # Extract content using Selenium
            article_data = extract_content_with_selenium(response.url)
            
            if article_data and article_data.get('text'):
                # Create output directories
                output_dir = 'extracted_articles/coin_telegraph'
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                articles_dir = os.path.join(output_dir, timestamp)
                os.makedirs(articles_dir, exist_ok=True)

                # Extract title from URL for filename
                url_path = response.url.rstrip('/').split('/')[-1]
                filename = f"{timestamp}_{url_path}.txt"
                filepath = os.path.join(articles_dir, filename)
                
                # Write content to file
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"URL: {article_data['url']}\n")
                    f.write(f"Author: {article_data.get('author', 'Unknown')}\n")
                    f.write(f"Time Published: {article_data.get('time_published', 'Unknown')}\n")
                    f.write(f"Views: {article_data.get('views', 0)}\n")
                    f.write(f"Shares: {article_data.get('shares', 0)}\n")
                    f.write(f"Crawl Time: {article_data['crawl_time']}\n\n")
                    f.write("Content:\n\n")
                    f.write(article_data['text'])
                
                self.logger.info(f"Successfully saved article to {filepath}")
                
                # Yield the data for the JSON feed
                yield article_data
            else:
                self.logger.error(f"No content extracted for {response.url}")
                
        except Exception as e:
            self.logger.error(f"Error in parse_article for {response.url}: {str(e)}")

    def closed(self, reason):
        if hasattr(self, 'driver'):
            self.driver.quit()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        handlers=[
            logging.FileHandler('spider_debug.log'),
            logging.StreamHandler()  # This will print to console as well
        ]
    )
    
    # Create output directories
    output_dir = 'extracted_articles'
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    process = CrawlerProcess(settings={
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'ROBOTSTXT_OBEY': False,
        'FEEDS': {
            f'{output_dir}/cointelegraph_articles_{timestamp}.json': {'format': 'jsonlines'},
        },
        'DOWNLOAD_DELAY': 3,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'CONCURRENT_REQUESTS': 1,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'RETRY_TIMES': 5,
        'RETRY_HTTP_CODES': [403, 429, 500, 502, 503, 504],
        'LOG_LEVEL': 'DEBUG',
        'LOG_FILE': 'scrapy_debug.log',
        'COOKIES_ENABLED': True,
        'COOKIES_DEBUG': True,
        'DOWNLOADER_MIDDLEWARES': {
            'scrape_cointelegraph.RandomUserAgentMiddleware': 400,
        }
    })
    
    try:
        process.crawl(CointelegraphSpider)
        process.start()
        
        print(f"\nExtraction complete!")
        print(f"Individual articles saved in: {output_dir}/{timestamp}")
        # print(f"Combined JSON saved as: {output_dir}/cointelegraph_articles_{timestamp}.json")
        
    except Exception as e:
        logging.error(f"Crawler failed with error: {str(e)}", exc_info=True)