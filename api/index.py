import json
from urllib.parse import parse_qs
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def fetch_html(url):
    """Fetch HTML content from the URL."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
    try:
        driver.get(url)
        # Wait for the page to load
        driver.implicitly_wait(10)  # Wait for elements to load
        return driver.page_source
    finally:
        driver.quit()  # Ensure browser is closed even if an error occurs

def parse_ark(html_content):
    """Parse the HTML content specific to Ark.no."""
    soup = BeautifulSoup(html_content, 'html.parser')
    title = soup.find('h3').text.strip() if soup.find('h3') else "-"
    authors_div = soup.find('div', class_='text-cap overflow-ellipsis whitespace-nowrap overflow-hidden text-xs md:text-sm leading-superTight md:leading-superTight mt-1')
    authors = authors_div.text.strip() if authors_div else "-"
    price_span = soup.find('span', class_='product-price-current')
    price = price_span.text.strip().replace(',-', '').strip() if price_span else "0"
    product_url = price_span.find_next('a')['href'] if price_span and price_span.find_next('a') else "-"
    product_url = f"https://www.ark.no{product_url}" if product_url else "-"
    
    return {
        "TITLE": title,
        "AUTHORS": authors,
        "PRICE": float(price) if price.isdigit() else 0,
        "PRODUCT_URL": product_url
    }

def parse_norli(html_content, isbn):
    """Parse the HTML content specific to Norli.no."""
    soup = BeautifulSoup(html_content, 'html.parser')
    product_div = soup.find('div', class_=lambda x: x and 'item-imageWrapper-' in x)
    if product_div:
        img_tag = product_div.find('img', src=lambda x: x and isbn in x)  # Use dynamic ISBN
        if img_tag:
            title = product_div.find('a')['aria-label'] if product_div.find('a') else "-"
            authors_div = product_div.find('div', class_=lambda x: x and x.startswith('itemNorli-authorName-'))
            authors = authors_div.text.strip() if authors_div else "-"
            price_span = product_div.find('span', class_=lambda x: x and x.startswith('productPrice-price-'))
            price = price_span.text.strip().replace(',-', '').strip() if price_span else "0"
            product_url = product_div.find('a')['href'] if product_div.find('a') else "-"
            product_url = f"https://www.norli.no{product_url}" if product_url else "-"
            
            return {
                "TITLE": title,
                "AUTHORS": authors,
                "PRICE": float(price) if price.isdigit() else 0,
                "PRODUCT_URL": product_url
            }
    return {"TITLE": "-", "AUTHORS": "-", "PRICE": 0, "PRODUCT_URL": "-"}

def handler(request):
    # Get the ISBN from query parameters
    query = request.query_params.get('ISBN', [None])[0]
    
    if not query:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing ISBN parameter"})
        }

    # Scrape both sites
    response = {
        "MESSAGE": "Data fetched successfully",
        "ISBN": query,
        "SITES": {}
    }

    # Scrape Ark.no
    ark_url = f'https://www.ark.no/search?text={query}'
    ark_html = fetch_html(ark_url)
    ark_data = parse_ark(ark_html)
    response["SITES"]["ark.no"] = ark_data

    # Scrape Norli.no
    norli_url = f'https://www.norli.no/search?query={query}'
    norli_html = fetch_html(norli_url)
    norli_data = parse_norli(norli_html, query)
    response["SITES"]["norli.no"] = norli_data

    return {
        "statusCode": 200,
        "body": json.dumps(response)
    }