import requests
from bs4 import BeautifulSoup
import json
import os
import re

# --- Configuration ---
CRAWFORD_URL = "https://inmates.crawfordcountysheriff.org/"
SEBASTIAN_URL = "https://inmate.sebastiancountyar.gov/NewWorld.InmateInquiry/AR0660000"
DATABASE_FILE = "database.json"
NEWLY_ADDED_FILE = "newly_added.json"
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

                # Visit details page to get image
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
                    continue # Skip this inmate if details page fails
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

# --- Database Functions ---

def load_database():
    """Loads the master inmate database from the JSON file."""
    if not os.path.exists(DATABASE_FILE):
        return {}
    with open(DATABASE_FILE, 'r') as f:
        return json.load(f)

def save_database(db):
    """Saves the master inmate database to the JSON file."""
    with open(DATABASE_FILE, 'w') as f:
        json.dump(db, f, indent=4)

def save_newly_added(inmates):
    """Saves the list of newly added inmates to a JSON file for the website."""
    with open(NEWLY_ADDED_FILE, 'w') as f:
        json.dump(inmates, f, indent=4)

# --- Main Execution ---

if __name__ == "__main__":
    print("Starting inmate scraper...")
    
    # Load existing database
    master_db = load_database()
    print(f"Loaded {len(master_db)} records from the master database.")
    
    # Scrape live data
    scraped_inmates = scrape_crawford_county() + scrape_sebastian_county()
    print(f"Total inmates scraped: {len(scraped_inmates)}")
    
    # Identify new inmates
    newly_added = []
    for inmate in scraped_inmates:
        if inmate['inmateId'] not in master_db:
            newly_added.append(inmate)
            master_db[inmate['inmateId']] = inmate # Add to master DB
            print(f"  - New inmate found: {inmate['name']} ({inmate['county']})")
            
    print(f"Found {len(newly_added)} new inmates.")
    
    # Save the results
    save_newly_added(newly_added)
    save_database(master_db)
    
    print("Script finished. Results saved.")

