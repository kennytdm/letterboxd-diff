from curl_cffi import requests
from bs4 import BeautifulSoup
import time
import random
import re

def get_headers(browser):
    if "safari" in browser:
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    elif "edge" in browser:
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    else:
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    return {
        "User-Agent": ua,
        "Referer": "https://letterboxd.com/",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cookie": "font-size=small; theme=dark;"
    }

def get_total_films(username, session):
    url = f"https://letterboxd.com/{username}/"
    try:
        response = session.get(url, headers=get_headers("chrome"), impersonate="chrome", timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Method 1: The most reliable - look for the 'Films' stat link
            films_stat = soup.select_one('li.stats-video-count a, a[href$="/films/"]')
            if films_stat:
                # Often the number is inside a <span> or just the text of a child element
                val = films_stat.find('span', class_='value') or films_stat.find('span', class_='count')
                if val:
                    return int(val.text.replace(',', '').strip())
            
            # Method 2: Fallback - Search for the navigation item by text
            nav_items = soup.find_all('li', class_='navitem')
            for item in nav_items:
                if 'Films' in item.text:
                    count = item.find('span', class_='count')
                    if count:
                        return int(count.text.replace(',', '').strip())
                        
    except Exception as e:
        print(f"Could not get total films for {username}: {e}")
    return None

def get_filtered_count(url, session):
    browsers = ["chrome120", "safari15_5", "edge101"]
    for attempt in range(1, 4):
        this_browser = browsers[attempt % len(browsers)]
        try:
            response = session.get(url, headers=get_headers(this_browser), impersonate=this_browser, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'lxml')
                
                if "/watchlist/" in url:
                    #Watchlists use the 'filtered-message' section or the specific heading inside it
                    target = soup.select_one('.filtered-message .ui-block-heading, .filtered-message, .ui-block-heading')
                else:
                    target = soup.select_one('.replace-if-you, .breadcrumb, .ui-block-heading')
                
                if target:
                    raw_text = target.get_text(" ", strip=True)
                    # 1. Normalize: "amber <3 has watched 113 action films ."
                    clean_text = " ".join(raw_text.split()).replace(',', '')

                    genres = r'Action|Adventure|Animation|Comedy|Crime|Documentary|Drama|Family|Fantasy|History|Horror|Music|Mystery|Romance|Sci-Fi|Science Fiction|Thriller|War|Western|Noir|Tv Movie'
                    
                    # 2. THE "LAST NUMBER" REGEX:
                    # (\d+)      -> Capture a number
                    # (?!.*\d)   -> Negative Lookahead: Ensure NO OTHER digits exist after this one...
                    # (?=.*films?) -> Positive Lookahead: ...until we hit the word "films"
                    #match = re.search(r'(\d+)(?!.*\d)(?=.*films?)', clean_text, re.IGNORECASE)
                    pattern = rf'(\d+)(?:\s*(?:films?)|(?:\s+(?:{genres})))'

                    match = re.search(pattern, clean_text, re.IGNORECASE)

                    if match:
                        count = int(match.group(1))
                        print(f"DEBUG: Final Success! Count: {count}", flush=True)
                        return count, soup
                        
                    # 3. THE "HITCHCOCK" FALLBACK (Manual Split)
                    # If Regex fails, we walk backwards from the word "films"
                    words = clean_text.lower().split()
                    for i, word in enumerate(words):
                        if "film" in word:
                            # Check the previous 3 words for the first digit we find
                            # This handles "113 films", "113 action films", "113 animated action films"
                            for lookback in range(1, 4):
                                if i - lookback >= 0:
                                    prev = words[i - lookback]
                                    if prev.isdigit():
                                        return int(prev), soup

        except Exception as e:
            print(f"DEBUG: Extraction Exception: {e}", flush=True)
    return None

def get_watched_films(username, session, genre=None, decade=None, person=None, role="actor", progressBar=None, totalFilms=None, is_watchlist=None):
    watched_films = {}
    page = 1
    first_page_soup = None
    browsers = ["safari15_5", "chrome120", "edge101"]

    page_size = 72 #default for film grids, 28 for watchlist
    list_type = "watchlist" if is_watchlist else "films"
    
    genre_path = f"genre/{genre.lower()}/" if genre else ""
    decade_path = f"decade/{decade}/" if decade else ""
    person_path = f"with/{role}/{person.lower().replace(' ', '-')}/" if person else ""
    
    # We build the URL using the list_type variable
    base_url = f"https://letterboxd.com/{username}/{list_type}/{person_path}{decade_path}{genre_path}"
    base_url = base_url.replace("//", "/").replace("https:/", "https://")

    # 2. THE RECON PHASE
    # Now we ALWAYS run recon to establish the grid size and total count
    result = get_filtered_count(base_url, session=session)
    if result:
        totalFilms, first_page_soup = result
        
        # Count posters on Page 1 to determine the grid limit
        posters_on_p1 = first_page_soup.find_all("div", attrs={"data-component-class": "LazyPoster"}) or \
                        first_page_soup.find_all(attrs={"data-target-link": True})
        
        p1_count = len(posters_on_p1)
        
        # If total films exceed what's on p1, then p1_count is our confirmed page_size
        if totalFilms > p1_count and p1_count > 0:
            page_size = p1_count
        else:
            # Total emergency fallback if BeautifulSoup tripped 
            page_size = 28 if is_watchlist else 72
            
        print(f"DEBUG: [Recon] {username} | Total: {totalFilms} | Page Size: {page_size}", flush=True)
    else:
        print(f"DEBUG: Recon Failed for {username}. Using standard defaults.", flush=True)

    print(f">>> STARTING {list_type.upper()} SCRAPE: {username}", flush=True)

    # 3. THE HYBRID LOOP
    while True:
        # Stop immediately if we've reached the known target (Prevents empty last scrape)
        if totalFilms and len(watched_films) >= totalFilms:
            print(f"DEBUG: Target {totalFilms} reached for {username}. Stopping.", flush=True)
            break

        # LOGIC: Reuse the recon soup for Page 1, otherwise hit the network
        if page == 1 and first_page_soup:
            soup = first_page_soup
            print(f"DEBUG: Reusing Recon HTML for {username} Page 1", flush=True)
        else:
            url = f"{base_url}page/{page}/"
            success = False
            
            # Browser Rotation / Retry Logic
            for attempt in range(len(browsers) * 2):
                this_browser = browsers[attempt % len(browsers)]
                try:
                    response = session.get(url, headers=get_headers(this_browser), impersonate=this_browser, timeout=10)
                    if response.status_code == 200:
                        success = True
                        soup = BeautifulSoup(response.content, 'lxml')
                        print(f"DEBUG: [Page {page}] {username} | Success | Total so far: {len(watched_films)}", flush=True)
                        break
                    elif response.status_code == 404:
                        break # End of the line
                    elif response.status_code == 429:
                        print("!!! RATE LIMITED !!! Taking a 30s breather...", flush=True)
                        time.sleep(30)
                        #Then retry the request one last time
                    else:
                        print(f"DEBUG: [Page {page}] {username} | Attempt {attempt+1} FAILED (Status: {response.status_code})", flush=True)
                except Exception as e:
                    print(f"Request error: {e}")
                
                time.sleep((attempt+1)*random.uniform(0.3, 0.6))

            if not success:
                break # Exit loop if blocked or 404

        # 4. PARSE POSTERS
        posters = soup.find_all("div", attrs={"data-component-class": "LazyPoster"}) or \
                  soup.find_all(attrs={"data-target-link": True})

        if not posters:
            break # No more films found

        for poster in posters:
            slug = poster.get('data-film-slug') or poster.get('data-target-link', '')
            if not slug or slug == "#":
                continue
            
            # Extraction: Title and Rating
            img = poster.find('img')
            real_title = img.get('alt') if img else slug.strip('/').split('/')[-1].replace('-', ' ').title()
            
            rating = None
            parent_li = poster.find_parent('li')
            if parent_li:
                rating_tag = parent_li.select_one('span.rating')
                if rating_tag:
                    classes = rating_tag.get('class', [])
                    for c in classes:
                        if c.startswith('rated-'):
                            rating = int(c.split('-')[-1]) / 2.0
            
            clean_slug = slug.strip('/').replace('film/', '')
            if clean_slug not in watched_films:
                watched_films[clean_slug] = {"title": real_title, "rating": rating}

        # 5. DYNAMIC UI UPDATES
        if progressBar:
            current_count = len(watched_films)
            if totalFilms and totalFilms > 0:
                # Percentage Progress
                progress_perc = min(current_count / totalFilms, 1.0)
                progressBar.progress(progress_perc, text=f"Scraping {username}: {current_count}/{totalFilms} films")
            else:
                # Indeterminate Progress (Spinner Style)
                progressBar.progress(0, text=f"Scraping {username}: {current_count} found...")

        page += 1
        # Only sleep if we expect more pages
        if not totalFilms or len(watched_films) < totalFilms:
            time.sleep(random.uniform(0.05, 0.1))

    return watched_films