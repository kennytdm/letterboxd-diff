from curl_cffi import requests
from bs4 import BeautifulSoup
import time
import random

def get_watched_films(username, genre=None, decade=None, person=None, role="actor"):
    watched_films = {}
    page = 1

    print(f">>> STARTING SCRAPE FOR: {username}", flush=True)
    
    while True:
        genre_path = f"genre/{genre.lower()}/" if genre else ""
        decade_path = f"decade/{decade}/" if decade else ""

        person_path = ""
        if person:
            person_slug = person.lower().replace(" ", "-")
            person_path = f"with/{role}/{person_slug}/"

        url = f"https://letterboxd.com/{username}/films/{person_path}{decade_path}{genre_path}page/{page}/"
        response = requests.get(url, impersonate="chrome120", timeout=10)

        print(f"Page {page} | Status: {response.status_code} | URL: {url}", flush=True)

        if response.status_code == 403:
            time.sleep(5)
            continue 
        
        if response.status_code != 200:
            break

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

        base_sleep = random(0.5, 0.8)
        if page % 10 == 0:
            time.sleep(2)
        else:
            time.sleep(base_sleep)

    return watched_films