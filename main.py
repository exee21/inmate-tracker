import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime

# --- Configuration ---
CRAWFORD_URL = "https://inmates.crawfordcountysheriff.org/"
SEBASTIAN_URL = "https://inmate.sebastiancountyar.gov/NewWorld.InmateInquiry/AR0660000"
DATABASE_FILE = "database.json"
CURRENT_INMATES_FILE = "current_inmates.json"
METADATA_FILE = "metadata.json"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- Helper Functions ---
def normalize_name(name):
    return re.sub(r'[^A-Z0-9_]', '', name.upper().replace(',', '').replace(' ', '_'))

def generate_inmate_id(name, county):
    return f"{normalize_name(name)}_{county}"

# --- Scraper Functions ---
def scrape_crawford_county():
    print("Scraping Crawford County...")
    inmates = []
    try:
        response = requests.get(CRAWFORD_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        inmate_blocks = soup.find_all('div', class_='inmate-single')
        if not inmate_blocks:
            print("  - Warning: No inmate blocks found for Crawford County. HTML structure may have changed.")
            return []
        for block in inmate_blocks:
            name_tag = block.find('h2')
            if name_tag and name_tag.find('a'):
                name = name_tag.get_text(strip=True)
                details_link = name_tag.find('a')['href']
                details_url = f"https://inmates.crawfordcountysheriff.org{details_link}"
                try:
                    details_response = requests.get(details_url, headers=HEADERS, timeout=10)
                    details_soup = BeautifulSoup(details_response.content, 'html.parser')
                    img_tag = details_soup.find('div', class_='inmate-photo').find('img')
                    image_url = f"https://inmates.crawfordcountysheriff.org{img_tag['src']}" if img_tag else "No Image"
                    inmates.append({'inmateId': generate_inmate_id(name, 'crawford'), 'name': name, 'imageUrl': image_url, 'county': 'crawford'})
                except requests.RequestException as e:
                    print(f"  - Could not fetch details for {name}: {e}")
    except requests.RequestException as e:
        print(f"  - Error scraping Crawford County: {e}")
    print(f"  - Found {len(inmates)} inmates.")
    return inmates

def scrape_sebastian_county():
    print("Scraping Sebastian County...")
    inmates = []
    try:
        response = requests.get(SEBASTIAN_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        rows = soup.select('table.inmate-table > tbody > tr')
        if not rows:
            print("  - Warning: No inmate rows found for Sebastian County. HTML structure may have changed.")
            return []
        for row in rows:
            name_cell = row.find('td', class_='col-md-4')
            if name_cell:
                name = name_cell.get_text(strip=True)
                img_tag = row.find('img')
                image_url = f"https://inmate.sebastiancountyar.gov/NewWorld.InmateInquiry/{img_tag['src']}" if img_tag else "No Image"
                inmates.append({'inmateId': generate_inmate_id(name, 'sebastian'), 'name': name, 'imageUrl': image_url, 'county': 'sebastian'})
    except requests.RequestException as e:
        print(f"  - Error scraping Sebastian County: {e}")
    print(f"  - Found {len(inmates)} inmates.")
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
    print("Starting inmate scraper...")
    master_db = load_database()
    print(f"Loaded {len(master_db)} records from the master database.")
    
    scraped_inmates = scrape_crawford_county() + scrape_sebastian_county()
    
    # --- THIS IS THE CRITICAL FIX ---
    # Only proceed if we actually found some inmates.
    if not scraped_inmates:
        print("\nCRITICAL: Scraper returned zero inmates. Assuming this is an error. Aborting update to preserve last known good data.")
    else:
        print(f"\nTotal inmates scraped: {len(scraped_inmates)}")
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

