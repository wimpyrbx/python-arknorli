import os
import sys
import time
import argparse
import json
from flask import Flask, jsonify, request
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread  # Import threading to run Flask app

app = Flask(__name__)

# Global variable to hold verbosity flag
verbose = False

def output(message):
    """Output message to console if verbose mode is enabled."""
    if verbose:
        print(message)

class BaseScraper:
    """Base class for scrapers."""
    
    def __init__(self, url):
        self.url = url

    def fetch_html(self):
        """Fetch HTML content from the URL."""
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
        driver.get(self.url)

        # Wait for the cookie consent popup and accept it
        try:
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".CybotCookiebotDialogBodyLevelButtonAccept"))
            ).click()
            output("Accepted cookie consent.")  # Debug output
        except Exception as e:
            output(f"No cookie consent popup found or could not click it: {e}")

        # Get the page source
        html_content = driver.page_source
        driver.quit()  # Close the browser
        return html_content

    def parse_html(self, html_content):
        """Parse the HTML content. This should be implemented by subclasses."""
        raise NotImplementedError("Subclasses should implement this method.")

class ArkScraper(BaseScraper):
    """Scraper for Ark.no."""
    
    def parse_html(self, html_content):
        """Parse the HTML content specific to Ark.no."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            title = soup.find('h3').text.strip() if soup.find('h3') else "-"
            authors = soup.find('div', class_='text-cap overflow-ellipsis whitespace-nowrap overflow-hidden text-xs md:text-sm leading-superTight md:leading-superTight mt-1').text.strip() if soup.find('div', class_='text-cap overflow-ellipsis whitespace-nowrap overflow-hidden text-xs md:text-sm leading-superTight md:leading-superTight mt-1') else "-"
            price = soup.find('span', class_='product-price-current').text.strip().replace(',-', '').strip() if soup.find('span', class_='product-price-current') else 0
            product_url = soup.find('span', class_='product-price-current').find_next('a')['href'] if soup.find('span', class_='product-price-current') and soup.find('span', class_='product-price-current').find_next('a') else "-"
            product_url = f"https://www.ark.no{product_url}" if product_url != "-" else "-"
            
            return {
                "Title": title,
                "Authors": authors,
                "Price": float(price) if isinstance(price, str) and price.isdigit() else 0,
                "Product_URL": product_url
            }
        except Exception as e:
            return {"Title": "-", "Authors": "-", "Price": 0, "Product_URL": "-", "ISBN": "-"}

class NorliScraper(BaseScraper):
    """Scraper for Norli.no."""
    
    def parse_html(self, html_content):
        """Parse the HTML content specific to Norli.no."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            title = soup.find('h1').text.strip() if soup.find('h1') else "-"
            
            # Extract authors with class starting with itemNorli-authorName-
            authors_div = soup.find('div', class_=lambda x: x and x.startswith('itemNorli-authorName-'))
            authors = authors_div.text.strip() if authors_div else "-"
            
            # Extract price with class starting with productPrice-price-
            price_div = soup.find('div', class_=lambda x: x and x.startswith('productPrice-price-'))
            price = price_div.text.strip().replace(',-', '').strip() if price_div else 0
            
            # Extract product URL from <a> inside div with class starting with item-imageWrapper-
            product_url_div = soup.find('div', class_=lambda x: x and x.startswith('item-imageWrapper-'))
            product_url = product_url_div.find('a')['href'] if product_url_div and product_url_div.find('a') else "-"
            product_url = f"https://www.norli.no{product_url}" if product_url != "-" else "-"
            
            return {
                "Title": title,
                "Authors": authors,
                "Price": float(price) if isinstance(price, str) and price.isdigit() else 0,
                "Product_URL": product_url
            }
        except Exception as e:
            return {"Title": "-", "Authors": "-", "Price": 0, "Product_URL": "-", "ISBN": "-"}

def get_scraper(url):
    """Factory method to get the appropriate scraper based on the URL."""
    if "ark.no" in url:
        return ArkScraper(url)
    elif "norli.no" in url:
        return NorliScraper(url)
    else:
        raise ValueError("Unsupported URL")

@app.route('/data', methods=['GET'])
def get_data():
    query = request.args.get('query')
    if not query:
        return jsonify({'error': 'No query parameters provided.'}), 400

    # Initialize results
    results = []
    prices = {}

    # Scrape both sites
    for site in ["ark.no", "norli.no"]:
        url = f'https://www.{site}/search?text={query}'
        output(f"Scraping {site} for ISBN: {query}")  # Indicate which site is being scraped
        scraper = get_scraper(url)
        html_content = scraper.fetch_html()
        data = scraper.parse_html(html_content)
        
        # Store results
        results.append(data)
        prices[site] = {
            "price": data.get("Price", 0),
            "product_url": data.get("Product_URL", "")
        }

    # Combine results
    combined_authors = set()
    longest_title = ""

    for result in results:
        combined_authors.update(result.get("Authors", "").split(", "))  # Split authors by comma
        if len(result.get("Title", "")) > len(longest_title):
            longest_title = result.get("Title", "")

    # Prepare final response
    response = {
        "MESSAGE": "Data fetched successfully.",
        "ISBN": query,
        "TITLE": longest_title,
        "AUTHORS": ", ".join(combined_authors),
        "SITES": prices
    }

    return jsonify(response)

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        # Check if the request is for favicon and ignore it
        if self.path == '/favicon.ico':
            self.send_response(204)  # No content
            self.end_headers()
            return

        # Extract ISBN from the query string
        query = self.path.split('?')[-1]  # Get the query part of the URL
        if not query:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'No query parameters provided.'}).encode('utf-8'))
            return

        params = dict(param.split('=') for param in query.split('&') if '=' in param)  # Parse query parameters
        isbn = params.get('ISBN')  # Get the ISBN value
        output(f"Received request for ISBN: {isbn}")  # Debug output
        
        if not isbn:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'ISBN parameter is missing.'}).encode('utf-8'))
            return
        
        # Construct the search URL
        url = f'https://www.ark.no/search?text={isbn}'
        output(f"Fetching HTML content from URL: {url}")  # Debug output
        
        try:
            # Start timestamp
            start_time = datetime.now()
            output(f"Starting scrape: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")  # Print start time

            # Set up headless Chrome options
            chrome_options = Options()
            # Uncomment the next line to run in non-headless mode for debugging
            # chrome_options.add_argument("--headless")  # Run in headless mode
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")

            # Start the headless browser
            driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
            driver.get(url)

            # Wait for the cookie consent popup and accept it
            try:
                WebDriverWait(driver, 5).until(  # Reduced wait time to 5 seconds
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".CybotCookiebotDialogBodyLevelButtonAccept"))  # Update this selector as needed
                ).click()
                output("Accepted cookie consent.")  # Debug output
            except Exception as e:
                output(f"No cookie consent popup found or could not click it: {e}")

            # Wait for the price element to load using the correct class
            output("Waiting for the price element to load...")  # Debug output
            WebDriverWait(driver, 5).until(  # Reduced wait time to 5 seconds
                EC.presence_of_element_located((By.CSS_SELECTOR, ".product-price-current"))  # Use the class for the price
            )

            # Get the page source
            html_content = driver.page_source
            driver.quit()  # Close the browser

            output("Successfully fetched HTML content.")  # Debug output
            
            # Parse the HTML content to extract data
            data = parse_html_from_content(html_content)
            data['ISBN'] = isbn  # Add ISBN to the data

            # Write the extracted data to test.json in the current directory
            with open(os.path.join(os.getcwd(), 'test.json'), 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            output("Data saved to test.json.")  # Debug output

            # End timestamp
            end_time = datetime.now()
            duration = end_time - start_time
            output(f"Scrape finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')} (Duration: {duration})")  # Print end time and duration

            self.send_response(200)
            self.send_header('Content-type', 'application/json')  # Set content type to JSON
            self.end_headers()
            self.wfile.write(json.dumps({'message': 'Data fetched and saved to test.json', 'data': data}).encode('utf-8'))  # Send JSON response
        except Exception as e:
            output(f"Error fetching HTML content: {e}")  # Debug output
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({'error': f'Error fetching HTML content: {str(e)}'}).encode('utf-8'))  # Send JSON error response
        return

def parse_html_from_content(html_content):
    """Parse the HTML content and extract title, authors, price, and product URL."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        title = soup.find('h3').text.strip() if soup.find('h3') else "-"
        authors = soup.find('div', class_='text-cap overflow-ellipsis whitespace-nowrap overflow-hidden text-xs md:text-sm leading-superTight md:leading-superTight mt-1').text.strip() if soup.find('div', class_='text-cap overflow-ellipsis whitespace-nowrap overflow-hidden text-xs md:text-sm leading-superTight md:leading-superTight mt-1') else "-"
        price = soup.find('span', class_='product-price-current').text.strip().replace(',-', '').strip() if soup.find('span', class_='product-price-current') else 0
        product_url = soup.find('span', class_='product-price-current').find_next('a')['href'] if soup.find('span', class_='product-price-current') and soup.find('span', class_='product-price-current').find_next('a') else "-"
        product_url = f"https://www.ark.no{product_url}" if product_url != "-" else "-"
        
        return {
            "Title": title,
            "Authors": authors,
            "Price": float(price) if isinstance(price, str) and price.isdigit() else 0,
            "Product_URL": product_url
        }
    except Exception as e:
        return {"Title": "-", "Authors": "-", "Price": 0, "Product_URL": "-", "ISBN": "-"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='API for fetching book data.')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    verbose = args.verbose  # Set the global verbose flag

    # Start the Flask app in a separate thread
    flask_thread = Thread(target=app.run, kwargs={'debug': True, 'use_reloader': False})  # Avoid reloader
    flask_thread.start()

    output(f"Running Server")
    output(f"{'-' * 30}")  # Print a line of dashes, 30 characters long
    # Start the HTTP server
    server_address = ('', 8000)  # Listen on all interfaces, port 8000
    httpd = HTTPServer(server_address, handler)
    output("Starting server on port 8000...")
    httpd.serve_forever()