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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64 ) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- Helper Functions ---

def normalize_name(name):
    """Normalizes a name to be used as a key."""
    return re.sub(r'[^A-Z0-9_]', '', name.upper().replace(',', '').replace(' ', '_'))

def generate_inmate_id(name, county):
    """Generates a unique ID for an inmate."""
    return f"{normalize_name(name)}_{county}"

# --- Scraper Functions ---

def scrape_crawford_county():
    """Scrapes inmate data from Crawford County Sheriff's Office."""
    print("Scraping Crawford County...")
    inmates = []
    try:
        response = requests.get(CRAWFORD_URL, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        inmate_blocks = soup.find_all('div', class_='inmate-single')
        for block in inmate_blocks:
            name_tag = block.find('h2')
            if name_tag:
                name = name_tag.get_text(strip=True)
                details_link = name_tag.find('a')['href']
                details_url = f"https://inmates.crawfordcountysheriff.org{details_link}"

                try:
                    details_response = requests.get(details_url, headers=HEADERS )
                    details_soup = BeautifulSoup(details_response.content, 'html.parser')
                    img_tag = details_soup.find('div', class_='inmate-photo').find('img')
                    image_url = f"https://inmates.crawfordcountysheriff.org{img_tag['src']}" if img_tag else "No Image"
                    
                    inmate_id = generate_inmate_id(name, 'crawford' )
                    inmates.append({
                        'inmateId': inmate_id,
                        'name': name,
                        'imageUrl': image_url,
                        'county': 'crawford'
                    })
                except requests.RequestException as e:
                    print(f"  - Could not fetch details for {name}: {e}")
                    continue
        print(f"  - Found {len(inmates)} inmates.")
    except requests.RequestException as e:
        print(f"  - Error scraping Crawford County: {e}")
    return inmates

def scrape_sebastian_county():
    """Scrapes inmate data from Sebastian County Adult Detention Center."""
    print("Scraping Sebastian County...")
    inmates = []
    try:
        response = requests.get(SEBASTIAN_URL, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        rows = soup.select('table.inmate-table > tbody > tr')
        for row in rows:
            name_cell = row.find('td', class_='col-md-4')
            if name_cell:
                name = name_cell.get_text(strip=True)
                img_tag = row.find('img')
                image_url = f"https://inmate.sebastiancountyar.gov/NewWorld.InmateInquiry/{img_tag['src']}" if img_tag else "No Image"

                inmate_id = generate_inmate_id(name, 'sebastian' )
                inmates.append({
                    'inmateId': inmate_id,
                    'name': name,
                    'imageUrl': image_url,
                    'county': 'sebastian'
                })
        print(f"  - Found {len(inmates)} inmates.")
    except requests.RequestException as e:
        print(f"  - Error scraping Sebastian County: {e}")
    return inmates

# --- Database & File Functions ---

def load_database():
    if not os.path.exists(DATABASE_FILE):
        return {}
    try:
        with open(DATABASE_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def save_database(db):
    with open(DATABASE_FILE, 'w') as f:
        json.dump(db, f, indent=4)

def save_current_inmates(inmates):
    with open(CURRENT_INMATES_FILE, 'w') as f:
        json.dump(inmates, f, indent=4)

def save_metadata():
    now = datetime.utcnow()
    timestamp = now.strftime("%B %d, %Y at %I:%M %p UTC")
    metadata = {"lastUpdatedAt": timestamp}
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=4)

# --- Main Execution ---

if __name__ == "__main__":
    print("Starting inmate scraper...")
    
    master_db = load_database()
    print(f"Loaded {len(master_db)} records from the master database.")
    
    scraped_inmates = scrape_crawford_county() + scrape_sebastian_county()
    print(f"Total inmates scraped: {len(scraped_inmates)}")
    
    current_inmates_with_status = []
    for inmate in scraped_inmates:
        is_new = inmate['inmateId'] not in master_db
        inmate_data = {
            'inmateId': inmate['inmateId'],
            'name': inmate['name'],
            'imageUrl': inmate['imageUrl'],
            'county': inmate['county'],
            'isNew': is_new
        }
        current_inmates_with_status.append(inmate_data)
        
        if is_new:
            master_db[inmate['inmateId']] = inmate # Add new inmate to master DB
            print(f"  - New inmate found: {inmate['name']} ({inmate['county']})")
            
    print(f"Processed {len(current_inmates_with_status)} total inmates.")
    
    save_current_inmates(current_inmates_with_status)
    save_database(master_db)
    save_metadata()
    
    print("Script finished. All files saved.")
