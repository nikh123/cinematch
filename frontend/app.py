"""CineMatch -- Streamlit frontend for the Movie Recommendation System.

Communicates with the Flask backend via REST API.
"""

import os

import requests
import streamlit as st
from streamlit_searchbox import st_searchbox

BACKEND = os.environ.get("BACKEND_URL", "http://localhost:8080")

# -- Page config -----------------------------------------------
st.set_page_config(page_title="CineMatch", layout="wide", page_icon="\U0001F3AC")

# -- CSS -------------------------------------------------------
st.markdown(
    """
<style>
/* Hero */
.hero-wrap { text-align: center; padding: 28px 0 4px; }
.hero-title {
    font-size: 4.5rem; font-weight: 900; letter-spacing: -2px;
    background: linear-gradient(135deg, #0a1628 0%, #1b3a5c 40%, #d4a017 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    line-height: 1.05; margin-bottom: 0;
}
.hero-tagline {
    font-size: 1.15rem; color: #8899aa; margin-top: 4px; font-weight: 400;
    letter-spacing: 0.5px;
}

/* Genre badges */
.genre-badge {
    display: inline-block; padding: 4px 12px; margin: 2px 4px;
    border-radius: 12px; background: #1b3a5c; color: #d4a017;
    font-size: 0.75rem; font-weight: 600;
    border: 1px solid #2a5580;
}
.movie-title {
    font-weight: 600; font-size: 0.95rem; margin-top: 8px; margin-bottom: 4px;
    height: 2.5em; line-height: 1.25em;
    overflow: hidden; display: -webkit-box;
    -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.movie-rating { color: #d4a017; font-weight: 600; font-size: 0.9rem; margin: 4px 0; }

/* Movie card */
.movie-card {
    border-radius: 10px; padding: 0;
    display: flex; flex-direction: column; overflow: hidden;
}
.movie-card img {
    width: 100%; aspect-ratio: 2/3; object-fit: cover; border-radius: 8px;
}
.movie-card .no-poster {
    width: 100%; aspect-ratio: 2/3; display: flex; align-items: center;
    justify-content: center; background: #0d1f3c; border-radius: 8px; color: #556;
}
.movie-card .card-body {
    padding: 8px 2px;
}

/* Selection chips */
.sel-chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 12px; }
.sel-chip {
    display: inline-flex; align-items: center; gap: 6px;
    background: linear-gradient(135deg, #1b3a5c, #0d1f3c); color: #d4a017;
    padding: 8px 16px; border-radius: 24px; font-size: 0.88rem; font-weight: 600;
    border: 1px solid #2a5580;
}
</style>
""",
    unsafe_allow_html=True,
)


# -- Session state ---------------------------------------------
for key, default in {
    "selected_movies": [],
    "recommendations": [],
    "filter_results": [],
    "last_viewed_movie": None,
    "filter_genre": "All",
    "filter_language": "All",
    "filter_country": "All",
    "filter_year": (1900, 2026),
    "filter_rating": 0.0,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# -- Helpers ---------------------------------------------------
def _rating_display(val) -> str:
    """Convert any rating to /10 display (TMDB-style).

    Dataset ratings are 0-1, TMDB ratings are 0-10.
    """
    if val is None:
        return ""
    v = float(val)
    if v <= 1:  # dataset 0-1 scale -> multiply by 10
        v = v * 10
    return f"{v:.1f}/10"


# -- Cached loaders -------------------------------------------
@st.cache_data(ttl=3600)
def load_genres() -> list[str]:
    try:
        r = requests.get(f"{BACKEND}/genres", timeout=5)
        if r.ok:
            return ["All"] + r.json().get("genres", [])
    except Exception:
        pass
    return ["All", "Action", "Comedy", "Drama", "Horror", "Sci-Fi"]


@st.cache_data(ttl=3600)
def load_languages() -> list[str]:
    try:
        r = requests.get(f"{BACKEND}/languages", timeout=5)
        if r.ok:
            return ["All"] + r.json().get("languages", [])
    except Exception:
        pass
    return ["All"]


@st.cache_data(ttl=3600)
def load_countries() -> list[str]:
    try:
        r = requests.get(f"{BACKEND}/countries", timeout=5)
        if r.ok:
            return ["All"] + r.json().get("countries", [])
    except Exception:
        pass
    return ["All"]


@st.cache_data(ttl=600)
def load_popular_movies() -> list[dict]:
    try:
        r = requests.get(f"{BACKEND}/movies/popular", timeout=10)
        if r.ok:
            data = r.json()
            return data if isinstance(data, list) else data.get("movies", [])
    except Exception:
        pass
    return []


def search_movies(searchterm: str) -> list[str]:
    """Live autocomplete from Elasticsearch via backend."""
    if not searchterm or len(searchterm) < 1:
        return []
    try:
        r = requests.get(f"{BACKEND}/autocomplete", params={"q": searchterm}, timeout=3)
        return r.json().get("results", [])[:8] if r.ok else []
    except Exception:
        return []


def add_movie(title: str):
    """Add a movie to selections and always fetch its info."""
    if title not in st.session_state.selected_movies:
        st.session_state.selected_movies.append(title)
    # Always update the preview to the latest added movie
    try:
        info = requests.get(f"{BACKEND}/movie-info", params={"title": title}, timeout=5)
        if info.ok:
            st.session_state.last_viewed_movie = info.json().get("movie")
    except Exception:
        pass


# -- Header ----------------------------------------------------
st.markdown(
    """
<div class="hero-wrap">
    <div class="hero-title">\U0001F3AC CineMatch</div>
    <div class="hero-tagline">Discover any movie, explore its details, and tell us what you love \u2014 we\u2019ll help you find your next favourite film.</div>
</div>
""",
    unsafe_allow_html=True,
)

# -- Search + autocomplete ------------------------------------
_, center, _ = st.columns([1, 3, 1])
with center:
    selected = st_searchbox(
        search_movies,
        placeholder="Search for a movie ...",
        label="Search",
        key="movie_searchbox",
        debounce=200,
        clear_on_submit=True,
    )

    # Only process a genuinely new selection (avoids infinite rerun)
    if selected and selected != st.session_state.get("_last_added_movie"):
        st.session_state["_last_added_movie"] = selected
        add_movie(selected)
    elif not selected:
        st.session_state["_last_added_movie"] = None

    st.divider()

    # -- Selected movies chips ---------------------------------
    if st.session_state.selected_movies:
        st.markdown("**Your selections**")
        chips_html = '<div class="sel-chip-row">' + "".join(
            f'<span class="sel-chip">{name}</span>'
            for name in st.session_state.selected_movies
        ) + '</div>'
        st.markdown(chips_html, unsafe_allow_html=True)
        # Tiny ✕ buttons aligned under each chip
        n_sel = len(st.session_state.selected_movies)
        rm_cols = st.columns(n_sel * 2)  # double cols so buttons are narrow
        for idx in range(n_sel):
            with rm_cols[idx]:
                if st.button("\u2715", key=f"rm_{idx}", help=f"Remove {st.session_state.selected_movies[idx]}"):
                    st.session_state.selected_movies.pop(idx)
                    if not st.session_state.selected_movies:
                        st.session_state.last_viewed_movie = None
                    st.rerun()
        st.divider()

    # -- Filters -----------------------------------------------
    with st.expander("Filters", expanded=False):
        genres = load_genres()
        languages = load_languages()
        countries = load_countries()
        f_c1, f_c2 = st.columns(2)
        with f_c1:
            genre = st.selectbox("Genre", genres, key="filter_genre")
        with f_c2:
            year_range = st.slider("Year range", 1900, 2026, key="filter_year")
        f_c3, f_c4 = st.columns(2)
        with f_c3:
            language = st.selectbox("Language", languages, key="filter_language")
        with f_c4:
            country = st.selectbox("Country", countries, key="filter_country")
        min_rating = st.slider("Minimum rating (0 \u2013 10)", 0.0, 10.0, step=0.5, key="filter_rating")

        f1, f2 = st.columns(2)
        with f1:
            if st.button("Apply filters", use_container_width=True):
                with st.spinner("Filtering \u2026"):
                    try:
                        r = requests.post(
                            f"{BACKEND}/movies/filter",
                            json={
                                "genre": genre if genre != "All" else None,
                                "language": language if language != "All" else None,
                                "country": country if country != "All" else None,
                                "min_rating": min_rating / 10.0,
                                "year_min": year_range[0],
                                "year_max": year_range[1],
                                "n": 20,
                            },
                            timeout=15,
                        )
                        if r.ok:
                            st.session_state.filter_results = r.json()
                            st.session_state.recommendations = list(
                                st.session_state.filter_results
                            )
                    except Exception as e:
                        st.error(f"Filter error: {e}")
        with f2:
            def _clear_filters():
                st.session_state.filter_results = []
                st.session_state.recommendations = []
                st.session_state.filter_genre = "All"
                st.session_state.filter_language = "All"
                st.session_state.filter_country = "All"
                st.session_state.filter_year = (1900, 2026)
                st.session_state.filter_rating = 0.0

            st.button("Clear filters", use_container_width=True, on_click=_clear_filters)

    # -- Action buttons ----------------------------------------
    b1, b2, b3 = st.columns([2, 1, 1])
    with b1:
        if st.button(
            "\U0001F3AF Get Recommendations",
            type="primary",
            use_container_width=True,
        ):
            if st.session_state.selected_movies:
                with st.spinner("Finding recommendations \u2026"):
                    try:
                        r = requests.post(
                            f"{BACKEND}/recommend",
                            json={
                                "movies": st.session_state.selected_movies,
                                "n": st.session_state.get("top_n", 12),
                            },
                            timeout=30,
                        )
                        if r.ok:
                            data = r.json()
                            recs = (
                                data
                                if isinstance(data, list)
                                else data.get("recommendations", [])
                            )
                            st.session_state.recommendations = recs
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.warning("Select at least one movie first!")
    with b2:
        st.session_state["top_n"] = st.slider(
            "How many?", 1, 20, value=12, label_visibility="collapsed"
        )
    with b3:
        if st.button("\U0001F5D1 Clear all", use_container_width=True):
            st.session_state.selected_movies = []
            st.session_state.recommendations = []
            st.session_state.filter_results = []
            st.session_state.last_viewed_movie = None
            st.rerun()


# -- Movie grid renderer ---------------------------------------
def _build_card_html(movie: dict) -> str:
    """Build a single movie card as an HTML string (poster + title + badges + rating)."""
    import html as _html
    title = _html.escape(movie.get("title", "Unknown"))
    poster = movie.get("poster", "")
    img = f'<img src="{poster}" alt="{title}">' if poster else '<div class="no-poster">No poster</div>'
    genres_str = movie.get("genres", "")
    badges = " ".join(
        f'<span class="genre-badge">{_html.escape(g.strip())}</span>'
        for g in str(genres_str).split("|")[:3]
    ) if genres_str else ""
    rating = movie.get("avg_predicted_rating") or movie.get("avg_rating") or movie.get("rating")
    rating_html = f'<p class="movie-rating">\u2B50 {_rating_display(rating)}</p>' if rating else ""
    return (
        f'<div class="movie-card">'
        f'{img}'
        f'<div class="card-body">'
        f'<p class="movie-title">{title}</p>'
        f'{badges}'
        f'{rating_html}'
        f'</div></div>'
    )


def _render_movie_grid(movies: list[dict], cols_count: int = 4, selectable: bool = False):
    """Render a grid of movie cards in proper rows."""
    for row_start in range(0, len(movies), cols_count):
        row_movies = movies[row_start : row_start + cols_count]
        cols = st.columns(cols_count, gap="small")
        for j, movie in enumerate(row_movies):
            with cols[j]:
                st.markdown(_build_card_html(movie), unsafe_allow_html=True)
                overview = movie.get("overview", "") or ""
                cast = movie.get("cast", "") or ""
                if overview or (cast and cast != "N/A"):
                    with st.popover("More info", use_container_width=True):
                        if overview:
                            st.markdown(f"**Synopsis:** {overview}")
                        if cast and cast != "N/A":
                            st.markdown(f"🎭 **Cast:** {cast}")
                if selectable:
                    m_title = movie.get("title", "")
                    if m_title:
                        already = m_title in st.session_state.selected_movies
                        idx = row_start + j
                        if already:
                            st.button("Added", key=f"pop_{idx}", disabled=True, use_container_width=True)
                        else:
                            st.button(
                                "+ Add",
                                key=f"pop_{idx}",
                                use_container_width=True,
                                on_click=add_movie,
                                args=(m_title,),
                            )


# -- Main display area -----------------------------------------
st.divider()

if st.session_state.recommendations:
    st.subheader("Recommended for You")
    _render_movie_grid(st.session_state.recommendations, cols_count=4, selectable=True)
elif st.session_state.last_viewed_movie:
    movie = st.session_state.last_viewed_movie
    st.subheader(f"\U0001F50D {movie.get('title', '')}")
    col_img, col_info = st.columns([1, 3])
    with col_img:
        if movie.get("poster"):
            st.image(movie["poster"], use_container_width=True)
    with col_info:
        genres_str = movie.get("genres", "")
        if genres_str:
            badges = " ".join(f'<span class="genre-badge">{g.strip()}</span>' for g in str(genres_str).split("|")[:5])
            st.markdown(badges, unsafe_allow_html=True)
        rating = movie.get("avg_predicted_rating") or movie.get("avg_rating") or movie.get("rating")
        if rating:
            st.markdown(f"**Rating:** \u2B50 {_rating_display(rating)}")
        if movie.get("overview"):
            st.write(movie["overview"])
        if movie.get("cast") and movie["cast"] != "N/A":
            st.caption(f"\U0001F3AD Cast: {movie['cast']}")
        m_title = movie.get("title", "")
        if m_title and m_title not in st.session_state.selected_movies:
            st.button("+ Add to selections", key="search_add", on_click=add_movie, args=(m_title,))
else:
    st.subheader("Popular Movies")
    popular = load_popular_movies()
    if popular:
        _render_movie_grid(popular, cols_count=5, selectable=True)
    else:
        st.info("Loading popular movies ...")
