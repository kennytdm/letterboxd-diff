from curl_cffi import requests
from bs4 import BeautifulSoup
import time
import random

def get_watched_films(username, genre=None, decade=None, person=None, role="actor"):
    watched_films = {}
    page = 1
    
    while True:
        genre_path = f"genre/{genre.lower()}/" if genre else ""
        decade_path = f"decade/{decade}/" if decade else ""

        person_path = ""
        if person:
            person_slug = person.lower().replace(" ", "-")
            person_path = f"with/{role}/{person_slug}/"

        url = f"https://letterboxd.com/{username}/films/{person_path}{decade_path}{genre_path}page/{page}/"
        response = requests.get(url, impersonate="chrome120", timeout=10)

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

        page += 1
        time.sleep(random.uniform(0.5, 0.8)) 

    return watched_films