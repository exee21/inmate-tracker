import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# --- Configuration ---
CRAWFORD_URL = "https://inmates.crawfordcountysheriff.org/"
SEBASTIAN_URL = "https://inmate.sebastiancountyar.gov/NewWorld.InmateInquiry/AR0660000"
DATABASE_FILE = "database.json"
CURRENT_INMATES_FILE = "current_inmates.json"
METADATA_FILE = "metadata.json"
# A more convincing user agent
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
}

# --- Helper Functions ---
def normalize_name(name):
    return re.sub(r'[^A-Z0-9_]', '', name.upper().replace(',', '').replace(' ', '_'))

def generate_inmate_id(name, county):
    return f"{normalize_name(name)}_{county}"

# --- New Browser-Based Scraper Functions ---

def scrape_crawford_county_playwright(page):
    """Scrapes Crawford County using a browser instance."""
    print("Scraping Crawford County with browser...")
    inmates = []
    try:
        page.goto(CRAWFORD_URL, timeout=30000)
        page.wait_for_selector('div.inmate-single', timeout=15000)
        
        soup = BeautifulSoup(page.content(), 'html.parser')
        inmate_blocks = soup.find_all('div', class_='inmate-single')
        
        if not inmate_blocks:
            print("  - Warning: No inmate blocks found for Crawford County.")
            return []

        for block in inmate_blocks:
            name_tag = block.find('h2')
            if name_tag and name_tag.find('a'):
                name = name_tag.get_text(strip=True)
                details_link = name_tag.find('a')['href']
                img_id = details_link.split('/')[-1]
                image_url = f"https://inmates.crawfordcountysheriff.org/photos/{img_id}.jpg"
                
                inmates.append({
                    'inmateId': generate_inmate_id(name, 'crawford'),
                    'name': name,
                    'imageUrl': image_url,
                    'county': 'crawford'
                })
        print(f"  - Found {len(inmates)} inmates from Crawford County.")
    except PlaywrightTimeoutError:
        print("  - CRITICAL ERROR: Timed out waiting for Crawford County page content. The site may be down or blocking.")
    except Exception as e:
        print(f"  - An unexpected error occurred with Crawford County: {e}")
    return inmates

def scrape_sebastian_county_playwright(page):
    """Scrapes Sebastian County using a browser instance."""
    print("Scraping Sebastian County with browser...")
    inmates = []
    try:
        page.goto(SEBASTIAN_URL, timeout=30000)
        # The structure changed, we now wait for the new table class
        page.wait_for_selector('table.inmate-table', timeout=15000)
        
        soup = BeautifulSoup(page.content(), 'html.parser')
        rows = soup.select('table.inmate-table > tbody > tr')

        if not rows:
            print("  - Warning: No inmate rows found for Sebastian County.")
            return []

        for row in rows:
            name_cell = row.find('td', class_='col-md-4')
            if name_cell:
                name = name_cell.get_text(strip=True)
                img_tag = row.find('img')
                image_url = f"https://inmate.sebastiancountyar.gov/NewWorld.InmateInquiry/{img_tag['src']}" if img_tag else "No Image"
                inmates.append({
                    'inmateId': generate_inmate_id(name, 'sebastian'),
                    'name': name,
                    'imageUrl': image_url,
                    'county': 'sebastian'
                })
        print(f"  - Found {len(inmates)} inmates from Sebastian County.")
    except PlaywrightTimeoutError:
        print("  - CRITICAL ERROR: Timed out waiting for Sebastian County page content. The site may be down or blocking.")
    except Exception as e:
        print(f"  - An unexpected error occurred with Sebastian County: {e}")
    return inmates

# --- Database & File Functions ---
def load_database():
    if not os.path.exists(DATABASE_FILE): return {}
    try:
        with open(DATABASE_FILE, 'r') as f: return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return {}

def save_database(db):
    with open(DATABASE_FILE, 'w') as f: json.dump(db, f, indent=4)

def save_current_inmates(inmates):
    with open(CURRENT_INMATES_FILE, 'w') as f: json.dump(inmates, f, indent=4)

def save_metadata():
    now = datetime.utcnow()
    timestamp = now.strftime("%B %d, %Y at %I:%M %p UTC")
    with open(METADATA_FILE, 'w') as f: json.dump({"lastUpdatedAt": timestamp}, f, indent=4)

# --- Main Execution ---
if __name__ == "__main__":
    print("Starting browser-based inmate scraper...")
    
    scraped_inmates = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS['User-Agent'])
        
        scraped_inmates.extend(scrape_crawford_county_playwright(page))
        scraped_inmates.extend(scrape_sebastian_county_playwright(page))
        
        browser.close()

    if not scraped_inmates:
        print("\nCRITICAL: Scraper returned zero total inmates. Aborting update to preserve last known good data.")
    else:
        print(f"\nTotal inmates scraped: {len(scraped_inmates)}")
        master_db = load_database()
        current_inmates_with_status = []
        new_inmate_count = 0
        
        for inmate in scraped_inmates:
            is_new = inmate['inmateId'] not in master_db
            inmate['isNew'] = is_new
            current_inmates_with_status.append(inmate)
            if is_new:
                master_db[inmate['inmateId']] = inmate
                new_inmate_count += 1
        
        if new_inmate_count > 0:
            print(f"  - Found {new_inmate_count} new inmates.")
        
        print("Saving updated data files...")
        save_current_inmates(current_inmates_with_status)
        save_database(master_db)
        save_metadata()
        print("Script finished successfully.")

