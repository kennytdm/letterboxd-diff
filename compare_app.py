import streamlit as st
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from streamlit.runtime.scriptrunner_utils.script_run_context import add_script_run_ctx, get_script_run_ctx
import time
import random
from scraper import get_watched_films

# Apply the cache here in the main app
@st.cache_data(ttl="1d")
def cached_scrape(username, genre, decade, person, role):
    try:
        data =  get_watched_films(username, genre, decade, person, role)
        return data
    except Exception as e:
        st.error(f"Scraper blocked for {username}. Please wait a minute and retry.")
        return None

st.title("Letterboxd Comparison Tool")

st.sidebar.header("Advanced Filters")
person_search = st.sidebar.text_input("Person's Name", placeholder="e.g. Steven Spielberg")
role_options = {
    "Director": "director", "Actor": "actor", "Writer": "writer",
    "Original Writer": "author", "Composer": "composer",
    "Cinematographer": "cinematographer", "Producer": "producer", "Editor": "editor"
}
selected_role = role_options[st.sidebar.selectbox("In the role of:", list(role_options.keys()))]
selected_decade = st.sidebar.selectbox("Select Decade", [None, "2020s", "2010s", "2000s", "1990s", "1980s", "1970s", "1960s", "1950s"])
selected_genre = st.sidebar.selectbox("Filter by Genre (Optional)", [None, "Action", "Animation", "Comedy", "Crime", "Drama", "Horror", "Sci-Fi", "Thriller"])

if st.sidebar.button("Clear Cache & Retry"):
    st.cache_data.clear()
    st.rerun()

user1 = st.text_input("First Username")
user2 = st.text_input("Second Username")

if st.button("Calculate Difference"):
    if not user1 or not user2:
        st.error("Please enter both usernames")
    else:
        p1 = st.empty()
        p2 = st.empty()
        ctx = get_script_run_ctx()

        def scrape_with_ctx(username, p_holder):
            add_script_run_ctx(None, ctx) 
            p_holder.info(f"🔍 Scraping {username}...")
            data =  cached_scrape(username, selected_genre, selected_decade, person_search, selected_role)
            if data is not None:
                p_holder.success(f"✅ {username}: {len(data)} films found.")
            else:
                p_holder.error(f"❌ {username}: Failed to fetch data.")
            return data

        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(scrape_with_ctx, user1, p1)
            time.sleep(random.uniform(0.5,1))
            future2 = executor.submit(scrape_with_ctx, user2, p2)
            data1 = future1.result()
            data2 = future2.result()

        if data1 and data2 is not None:

            unseen_slugs = set(data1.keys()) - set(data2.keys())
            results = []
            for slug in unseen_slugs:
                results.append({
                    "Movie": slug.replace('-', ' ').title(),
                    "User 1 Rating": data1[slug],
                    "Link": f"https://letterboxd.com/film/{slug}/"
                })

            df = pd.DataFrame(results)
            if not df.empty:
                dynamic_column_name = f"{user1}'s Rating"
                df = df.rename(columns={"User 1 Rating": dynamic_column_name})
                df = df.sort_values(by=[dynamic_column_name, "Movie"], ascending=[False, True])
                st.write(f"### Found {len(df)} movies {user1} has seen that {user2} hasn't")
                st.dataframe(
                    df,
                    column_config={
                        "Link": st.column_config.LinkColumn("Letterboxd Link"),
                        dynamic_column_name: st.column_config.NumberColumn(format="%.1f ⭐")
                    },
                    hide_index=True,
                    width="stretch"
                )
            else:
                st.warning("No differences found!")