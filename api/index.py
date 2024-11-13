import os
import sys
import json
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse, urlencode
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
                WebDriverWait(driver, 1).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".CybotCookiebotDialogBodyLevelButtonAccept"))
                ).click()
                output("Accepted cookie consent.")
            except Exception as e:
                output(f"No cookie consent popup found or could not click it: {e}")

            # Get the page source after a short wait to ensure content is loaded
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            html_content = driver.page_source
            return html_content
        finally:
            driver.quit()

    def parse_html(self, html_content):
        """Parse the HTML content. This should be implemented by subclasses."""
        raise NotImplementedError("Subclasses should implement this method.")

class ArkScraper(BaseScraper):
    """Scraper for Ark.no."""
    
    def parse_html(self, html_content):
        """Parse the HTML content specific to Ark.no."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Verify we have exactly one result
            results_header = soup.find('h1')
            if not results_header or "1 resultat:" not in results_header.text:
                output("Ark.no - Skipping: Did not find exactly one result")
                return {"title": "-", "authors": "-", "PRICE": 0, "PRODUCT_URL": "-"}

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
                "PRICE": int(price) if price.isdigit() else 0,
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
            
            # Verify we have exactly one product
            stats_span = soup.find('span', class_='ais-Stats-text')
            if not stats_span or stats_span.text.strip() != "Produkter (1)":
                output("Norli.no - Skipping: Did not find exactly one product")
                return {"title": "-", "authors": "-", "PRICE": 0, "PRODUCT_URL": "-"}
            
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
                    "PRICE": int(price) if price.isdigit() else 0,
                    "PRODUCT_URL": product_url
                }
            return {"title": "-", "authors": "-", "PRICE": 0, "PRODUCT_URL": "-"}
        except Exception as e:
            error_output(f"Error parsing Norli.no HTML: {e}")
            return {"title": "-", "authors": "-", "PRICE": 0, "PRODUCT_URL": "-"}

class AdlibrisScraper(BaseScraper):
    """Scraper for Adlibris.no."""
    
    def parse_html(self, html_content):
        """Parse the HTML content specific to Adlibris.no."""
        try:
            with open('adlibris.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
            output("Saved HTML content to adlibris.html")

            soup = BeautifulSoup(html_content, 'html.parser')
            
            # First verify we have exactly one result - with proper text cleaning
            result_amount = soup.find('h3', class_='search-result__result__amount')
            if result_amount:
                # Clean the text: strip whitespace, newlines, and normalize spacing
                result_text = ' '.join(result_amount.get_text().split())
                output(f"Found result amount text: '{result_text}'")
                if result_text != "1 treff":
                    output(f"Adlibris.no - Skipping: Not exactly one result (got: {result_text})")
                    return {"title": "-", "authors": "-", "PRICE": 0, "PRODUCT_URL": "-"}
            else:
                output("Adlibris.no - Skipping: No result amount found")
                return {"title": "-", "authors": "-", "PRICE": 0, "PRODUCT_URL": "-"}

            # Find the product wrapper - this is the key container
            product_wrapper = soup.find('div', class_='search-result__list-view__product__wrapper')
            if not product_wrapper:
                output("Adlibris.no - Skipping: No product wrapper found")
                return {"title": "-", "authors": "-", "PRICE": 0, "PRODUCT_URL": "-"}
            
            # Get title from product name link
            title = "-"
            title_link = product_wrapper.find('a', class_='search-result__product__name')
            if title_link:
                title = ' '.join(title_link.get_text().split())

            # Get author - using the author link inside product-item__authors
            authors = "-"
            author_link = product_wrapper.find('a', {'itemprop': 'author'})
            if author_link:
                authors = ' '.join(author_link.get_text().split())

            # Get price from the price div within variants section
            price = "0"
            price_div = product_wrapper.find('div', class_='price nok')
            if price_div and price_div.find('span'):
                price_text = ' '.join(price_div.find('span').get_text().split())
                price_text = price_text.replace(',-', '').strip()
                if price_text.isdigit():
                    price = price_text

            # Get product URL
            product_url = "-"
            if title_link and 'href' in title_link.attrs:
                product_url = f"https://www.adlibris.com{title_link['href']}"

            output(f"Adlibris.no - Title: {title}, Authors: {authors}, Price: {price}, URL: {product_url}")

            return {
                "title": title,
                "authors": authors,
                "PRICE": int(price) if price.isdigit() else 0,
                "PRODUCT_URL": product_url if product_url != "-" else "-"
            }
            
        except Exception as e:
            error_output(f"Error parsing Adlibris.no HTML: {str(e)}")
            return {"title": "-", "authors": "-", "PRICE": 0, "PRODUCT_URL": "-"}
        
def scrape_book_data(isbn):
    """Scrape book data directly without using a server."""
    start_time = datetime.now()
    output(f"Starting scrape for ISBN {isbn}: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    response = {
        "MESSAGE": "Data fetch initiated",
        "ISBN": isbn,
        "TIMESTAMP": "",
        "SITES": {}
    }

    sites = {
        "ark.no": (ArkScraper, lambda isbn: f'https://www.ark.no/search?text={isbn}'),
        "norli.no": (NorliScraper, lambda isbn: f'https://www.norli.no/search?query={isbn}'),
        "adlibris.no": (AdlibrisScraper, lambda isbn: f'https://www.adlibris.com/no/sok?q={isbn}')
    }

    for site_domain, (scraper_class, url_builder) in sites.items():
        try:
            url = url_builder(isbn)
            output(f"Scraping {site_domain}")
            
            scraper = scraper_class(url)
            html_content = scraper.fetch_html()
            result = scraper.parse_html(html_content)

            response["SITES"][site_domain] = {
                "TITLE": result["title"],
                "AUTHORS": result["authors"],
                "PRICE": result["PRICE"],
                "PRODUCT_URL": result["PRODUCT_URL"]
            }

        except Exception as e:
            error_output(f"Error scraping {site_domain}: {e}")
            response["SITES"][site_domain] = {
                "TITLE": "-",
                "AUTHORS": "-",
                "PRICE": 0,
                "PRODUCT_URL": "-"
            }

    response["MESSAGE"] = "Data fetched successfully"
    response["TIMESTAMP"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    end_time = datetime.now()
    duration = end_time - start_time
    output(f"Scrape finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')} (Duration: {duration})")

    return response

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return

        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        isbn = query_params.get('ISBN', [None])[0]
        
        if not isbn:
            self.send_error(400, 'Missing ISBN parameter')
            return

        try:
            response = scrape_book_data(isbn)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            error_output(f"Error processing request: {e}")
            self.send_error(500, f'Internal server error: {str(e)}')

def save_to_json(data, isbn):
    """Save the scraped data to a JSON file."""
    # Create isbn directory if it doesn't exist
    os.makedirs('isbn', exist_ok=True)
    
    # Save to isbn/<isbn>.json
    filepath = os.path.join('isbn', f'{isbn}.json')
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, indent=4, ensure_ascii=False, fp=f)
    
    output(f"Data saved to {filepath}")

def run_server(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, RequestHandler)
    output(f"Starting server on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='API for fetching book data.')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--stacktrace', action='store_true', help='Enable stacktrace output')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    parser.add_argument('--isbn', type=str, help='ISBN to fetch data for')
    args = parser.parse_args()

    verbose = args.verbose
    stacktrace_enabled = args.stacktrace
    
    if args.isbn:
        output(f"Fetching data for ISBN: {args.isbn}")
        data = scrape_book_data(args.isbn)
        save_to_json(data, args.isbn)
        print(json.dumps(data, indent=4))  # Print the data to console as well
    else:
        run_server(args.port)