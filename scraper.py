from curl_cffi import requests
from bs4 import BeautifulSoup
import time
import random

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
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cookie": "font-size=small; theme=dark;"
    }

def get_watched_films(username, genre=None, decade=None, person=None, role="actor"):
    watched_films = {}
    page = 1
    browsers = ["chrome120", "safari15_5", "edge101"]

    print(f">>> STARTING SCRAPE FOR: {username}", flush=True)
    
    while True:
        genre_path = f"genre/{genre.lower()}/" if genre else ""
        decade_path = f"decade/{decade}/" if decade else ""

        person_path = ""
        if person:
            person_slug = person.lower().replace(" ", "-")
            person_path = f"with/{role}/{person_slug}/"

        url = f"https://letterboxd.com/{username}/films/{person_path}{decade_path}{genre_path}page/{page}/"
        
        success = False
        for attempt in range(len(browsers)*2):
            this_browser = browsers[attempt%len(browsers)]
            response = requests.get(url, headers=get_headers(this_browser), impersonate=this_browser, timeout=10)
            if response.status_code == 200:
                success = True
                break
            print(f"Attempt {attempt+1} failed with status {response.status_code}. Retrying...", flush=True)
            time.sleep(random.uniform(2, 4))

        print(f"Page {page} | Status: {response.status_code} | URL: {url}", flush=True)
        
        if not success:
            print(f"Final failure for {username} at page {page}: {response.status_code}", flush=True)
            raise RuntimeError(f"Letterboxd blocked the request (Status {response.status_code}).")

        soup = BeautifulSoup(response.content, 'lxml')
        posters = soup.find_all("div", attrs={"data-component-class": "LazyPoster"})

        if not posters:
            posters = soup.find_all(attrs={"data-target-link": True})

        if not posters:
            break

        for poster in posters:
            slug = poster.get('data-film-slug') or poster.get('data-target-link')
            rating = None
            parent_li = poster.find_parent('li')
            if parent_li:
                rating_tag = parent_li.select_one('span.rating')
                if rating_tag:
                    classes = rating_tag.get('class', [])
                    for c in classes:
                        if c.startswith('rated-'):
                            rating = int(c.split('-')[-1]) / 2.0
            if slug:
                clean_slug = slug.strip('/').replace('film/', '')
                watched_films[clean_slug] = rating
        
        print(f"Found {len(watched_films)} films after page {page}", flush=True)
        page += 1

        base_sleep = random.uniform(0.5, 0.8)
        if page % 10 == 0:
            time.sleep(2)
        else:
            time.sleep(base_sleep)

    return watched_films