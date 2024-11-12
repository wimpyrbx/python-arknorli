import os
import sys
import json
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Global variable to hold verbosity flag
verbose = False
stacktrace_enabled = False

def output(message):
    """Output message to console if verbose mode is enabled."""
    if verbose:
        print(message)

def error_output(message):
    """Output error message to console if stacktrace mode is enabled."""
    if stacktrace_enabled:
        print(message)

class BaseScraper:
    """Base class for scrapers."""
    
    def __init__(self, url):
        self.url = url
        output(f"Initializing scraper for {url}")

    def fetch_html(self):
        """Fetch HTML content from the URL."""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        output(f"Fetching content from {self.url}")
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), 
                                options=chrome_options)
        try:
            driver.get(self.url)

            # Wait for the cookie consent popup and accept it
            try:
                WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".CybotCookiebotDialogBodyLevelButtonAccept"))
                ).click()
                output("Accepted cookie consent.")
            except Exception as e:
                output(f"No cookie consent popup found or could not click it: {e}")

            # Get the page source after a short wait to ensure content is loaded
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            html_content = driver.page_source
            return html_content
        finally:
            driver.quit()  # Ensure browser is closed even if an error occurs

    def parse_html(self, html_content):
        """Parse the HTML content. This should be implemented by subclasses."""
        raise NotImplementedError("Subclasses should implement this method.")

class ArkScraper(BaseScraper):
    """Scraper for Ark.no."""
    
    def parse_html(self, html_content):
        """Parse the HTML content specific to Ark.no."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            title = soup.find('h3')
            title = title.text.strip() if title else "-"
            
            authors_div = soup.find('div', class_='text-cap overflow-ellipsis whitespace-nowrap overflow-hidden text-xs md:text-sm leading-superTight md:leading-superTight mt-1')
            authors = authors_div.text.strip() if authors_div else "-"
            
            price_span = soup.find('span', class_='product-price-current')
            price = price_span.text.strip().replace(',-', '').strip() if price_span else "0"
            
            product_url = ""
            if price_span:
                next_link = price_span.find_next('a')
                if next_link and 'href' in next_link.attrs:
                    product_url = f"https://www.ark.no{next_link['href']}"
            
            output(f"Ark.no - Title: {title}, Authors: {authors}, Price: {price}, URL: {product_url}")
            
            return {
                "title": title,
                "authors": authors,
                "PRICE": float(price) if price.isdigit() else 0,
                "PRODUCT_URL": product_url if product_url else "-"
            }
        except Exception as e:
            error_output(f"Error parsing Ark.no HTML: {e}")
            return {"title": "-", "authors": "-", "PRICE": 0, "PRODUCT_URL": "-"}

class NorliScraper(BaseScraper):
    """Scraper for Norli.no."""
    
    def parse_html(self, html_content):
        """Parse the HTML content specific to Norli.no."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find first product container
            product_div = soup.find('div', class_=lambda x: x and 'item-imageWrapper-' in x)
            
            if product_div:
                # Find title
                title = product_div.find('a')['aria-label'] if product_div.find('a') else "-"
                
                # Find authors using updated selector (class starts with 'itemNorli-authorName-')
                authors_div = soup.find('div', class_=lambda x: x and x.startswith('itemNorli-authorName-'))
                authors = authors_div.text.strip() if authors_div else "-"
                
                # Find price using updated selector (class starts with 'productPrice-price-')
                price_span = soup.find('span', class_=lambda x: x and x.startswith('productPrice-price-'))
                price = price_span.text.strip().replace(',-', '').strip() if price_span else "0"
                
                # Find product URL
                product_url = product_div.find('a')['href'] if product_div.find('a') else "-"
                product_url = f"https://www.norli.no{product_url}" if product_url != "-" else "-"
                
                output(f"Norli.no - Title: {title}, Authors: {authors}, Price: {price}, URL: {product_url}")
                
                return {
                    "title": title,
                    "authors": authors,
                    "PRICE": float(price) if price.isdigit() else 0,
                    "PRODUCT_URL": product_url
                }
            return {"title": "-", "authors": "-", "PRICE": 0, "PRODUCT_URL": "-"}
        except Exception as e:
            error_output(f"Error parsing Norli.no HTML: {e}")
            return {"title": "-", "authors": "-", "PRICE": 0, "PRODUCT_URL": "-"}

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Check if the request is for favicon and ignore it
        if self.path == '/favicon.ico':
            self.send_response(204)  # No content
            self.end_headers()
            return

        # Parse the URL and query parameters
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        
        # Get ISBN from query parameters
        isbn = query_params.get('ISBN', [None])[0]
        
        if not isbn:
            self.send_error(400, 'Missing ISBN parameter')
            return

        try:
            # Start timestamp
            start_time = datetime.now()
            output(f"Starting scrape for ISBN {isbn}: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

            # Initialize response structure
            response = {
                "MESSAGE": "Data fetch initiated",
                "ISBN": isbn,
                "SITES": {}
            }

            # Scrape both sites
            sites = {
                "ark.no": ArkScraper,
                "norli.no": NorliScraper
            }

            for site_domain, scraper_class in sites.items():
                try:
                    # Use different query parameters for each site
                    if site_domain == "ark.no":
                        url = f'https://www.{site_domain}/search?text={isbn}'
                    else:  # for norli.no
                        url = f'https://www.{site_domain}/search?query={isbn}'
                    
                    output(f"Scraping {site_domain}")
                    
                    scraper = scraper_class(url)
                    html_content = scraper.fetch_html()
                    result = scraper.parse_html(html_content)  # Pass dynamic ISBN
                    
                    # Store site-specific data in the response
                    response["SITES"][site_domain] = {
                        "TITLE": result["title"],
                        "AUTHORS": result["authors"],
                        "PRICE": result["PRICE"],
                        "PRODUCT_URL": result["PRODUCT_URL"]
                    }

                except Exception as e:
                    error_output(f"Error scraping {site_domain}: {e}")
                    response["SITES"][site_domain] = {"TITLE": "-", "AUTHORS": "-", "PRICE": 0, "PRODUCT_URL": "-"}

            # Update response with collected data
            response["MESSAGE"] = "Data fetched successfully"

            # End timestamp
            end_time = datetime.now()
            duration = end_time - start_time
            output(f"Scrape finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')} (Duration: {duration})")

            # Send successful response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')  # Allow CORS
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            error_output(f"Error processing request: {e}")
            self.send_error(500, f'Internal server error: {str(e)}')

def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, RequestHandler)
    output(f"Starting server on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='API for fetching book data.')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--stacktrace', action='store_true', help='Enable stacktrace output')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    args = parser.parse_args()

    verbose = args.verbose  # Set the global verbose flag
    stacktrace_enabled = args.stacktrace  # Set the global stacktrace flag
    
    try:
        run_server(args.port)
    except KeyboardInterrupt:
        print("\nShutting down server...")
        sys.exit(0)