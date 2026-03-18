import streamlit as st
from curl_cffi import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from streamlit.runtime.scriptrunner_utils.script_run_context import add_script_run_ctx, get_script_run_ctx
import time
import random
from scraper import get_watched_films
from scraper import get_total_films

# Apply the cache here in the main app
#@st.cache_data(ttl="1d")
def cached_scrape(username, session, genre, decade, person, role, _p_bar=None, total_films=None):
    try:
        data =  get_watched_films(username, session, genre, decade, person, role, progressBar=_p_bar, totalFilms=total_films)
        return data
    except Exception as e:
        st.error(f"Scraper blocked for {username}. Please wait a minute and retry.")
        return None

st.set_page_config(
    page_title="Letterboxd Comparison",
    initial_sidebar_state="expanded", # Forces it open on desktop/tablets
    layout="wide"
)

# Custom CSS to make the sidebar toggle pulse or stay visible on mobile
st.markdown("""
    <style>
        [data-testid="stSidebarNav"] { background-image: none; }
        /* This makes the sidebar arrow more visible on mobile */
        .st-emotion-cache-16idsys p { font-weight: bold; color: #ff8000; }
    </style>
""", unsafe_allow_html=True)

st.title("Letterboxd Comparison Tool")

# Initialize the persistent web session
if 'web_session' not in st.session_state:
    st.session_state.web_session = requests.Session()

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

st.sidebar.header("Watchlist Settings")
filter_watchlist = st.sidebar.radio(
    "User 2's Watchlist:",
    ["Ignore", "Exclude these", "Only show these"],
    help="Filter results based on what is in User 2's watchlist. Ignore is quickest!"
)

if st.sidebar.button("Clear Cache & Retry"):
    st.cache_data.clear()
    st.rerun()

user1 = st.text_input("First Username")
user2 = st.text_input("Second Username")

if st.button("Calculate Difference"):
    if not user1 or not user2:
        st.error("Please enter both usernames")
    else:
        col1, col2 = st.columns(2)
        with col1:
            p1 = st.empty()
            p_bar1 = st.progress(0, text="Waiting...")
        with col2:
            p2 = st.empty()
            p_bar2 = st.progress(0, text="Waiting...")

        p_watch = st.empty()
        p_bar_watch = st.progress(0, text="Waiting...") if filter_watchlist != "Ignore" else None

        ctx = get_script_run_ctx()

        def scrape_with_ctx(username, session, p_holder, p_bar_ref, total_count):
            add_script_run_ctx(None, ctx) 
            p_holder.info(f"🔍 Scraping {username}...")
            data =  cached_scrape(username, session, selected_genre, selected_decade, person_search, selected_role, _p_bar=p_bar_ref, total_films=total_count)
            if data is not None:
                p_holder.success(f"✅ {username}: {len(data)} films found.")
            else:
                p_holder.error(f"❌ {username}: Failed to fetch data.")
            return data
        
        def scrape_watchlist_with_ctx(username, session, p_holder, p_bar_ref):
            add_script_run_ctx(None, ctx) # 'ctx' must be in scope
            p_holder.info(f"📋 Fetching {username}'s Watchlist...")
            # We pass is_watchlist=True here
            data = get_watched_films(username, session, selected_genre, selected_decade, 
                                    person_search, selected_role, is_watchlist=True, 
                                    progressBar=p_bar_ref)
            if data:
                p_holder.success(f"✅ {username} Watchlist: {len(data)} films.")
            return data

        start_time = time.time()
        # Get totals first (this is fast)
        total1 = get_total_films(user1,st.session_state.web_session)
        total2 = get_total_films(user2,st.session_state.web_session)

        with ThreadPoolExecutor(max_workers=3) as executor:
            future1 = executor.submit(scrape_with_ctx, user1, st.session_state.web_session, p1, p_bar1, total1)
            time.sleep(random.uniform(0.2,0.4))
            future2 = executor.submit(scrape_with_ctx, user2, st.session_state.web_session, p2, p_bar2, total2)
            
            future_watch = None
            if filter_watchlist != "Ignore":
                time.sleep(random.uniform(0.2, 0.4))
                future_watch = executor.submit(
                    scrape_watchlist_with_ctx, # New helper needed
                    user2, st.session_state.web_session, p_watch, p_bar_watch
                )
            
            data1 = future1.result()
            data2 = future2.result()
            watchlist_data = future_watch.result() if future_watch else None

        if p_bar_watch:
            p_bar_watch.empty()

        end_time  = time.time()
        st.caption(f"⏱️ Scrape completed in {end_time - start_time:.2f} seconds.")

        if data1 is not None and data2 is not None:

            unseen_slugs = set(data1.keys()) - set(data2.keys())

            if watchlist_data:
                watchlist_slugs = set(watchlist_data.keys())
                if filter_watchlist == "Exclude these":
                    # Remove movies that are in User 2's watchlist
                    unseen_slugs = unseen_slugs - watchlist_slugs
                elif filter_watchlist == "Only show these":
                    # Only keep movies that ARE in User 2's watchlist
                    unseen_slugs = unseen_slugs.intersection(watchlist_slugs)

            results = []
            for slug in unseen_slugs:
                film_info = data1[slug]
                results.append({
                    "Movie": film_info["title"],
                    "User 1 Rating": film_info["rating"],
                    "Link": f"https://letterboxd.com/film/{slug}/"
                })

            df = pd.DataFrame(results)
            if not df.empty:
                dynamic_column_name = f"{user1}'s Rating"
                df = df.rename(columns={"User 1 Rating": dynamic_column_name})
                df = df.sort_values(by=[dynamic_column_name, "Movie"], ascending=[False, True])
                if filter_watchlist == "Exclude these":
                    header_msg = f"### Found {len(df)} movies {user1} has seen that {user2} hasn't (That are not on {user2}'s Watchlist)"
                elif filter_watchlist == "Only show these":
                    header_msg = f"### Found {len(df)} movies {user1} has seen that {user2} hasn't (That are on {user2}'s Watchlist)"
                else:
                    header_msg = f"### Found {len(df)} movies {user1} has seen that {user2} hasn't"

                # 2. Render the header
                st.write(header_msg)
                
                st.dataframe(
                    df,
                    column_config={
                        "Link": st.column_config.LinkColumn("Letterboxd Link"),
                        "Movie": st.column_config.TextColumn("Film Title", width="large"),
                        dynamic_column_name: st.column_config.NumberColumn(format="%.1f ⭐")
                    },
                    hide_index=True,
                    width="stretch"
                )
            else:
                st.warning("No differences found!")