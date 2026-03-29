"""CineMatch -- Streamlit frontend for the Movie Recommendation System.

Communicates with the Flask backend via REST API.
"""

import os

import requests
import streamlit as st

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
    background: linear-gradient(135deg, #e50914 0%, #ff6b35 40%, #ffd700 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    line-height: 1.05; margin-bottom: 0;
}
.hero-tagline {
    font-size: 1.15rem; color: #999; margin-top: 4px; font-weight: 400;
    letter-spacing: 0.5px;
}

/* Genre badges */
.genre-badge {
    display: inline-block; padding: 4px 12px; margin: 2px 4px;
    border-radius: 12px; background: #e50914; color: #fff;
    font-size: 0.75rem; font-weight: 600;
}
.movie-title { font-weight: 600; font-size: 0.95rem; margin-top: 8px; }
.movie-rating { color: #ff6b35; font-weight: 600; font-size: 0.9rem; }

/* Chips */
.chip {
    display: inline-block; background: #e50914; color: #fff;
    padding: 6px 14px; border-radius: 20px; margin: 4px; font-size: 0.85rem;
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


def fetch_suggestions(q: str) -> list[str]:
    """Autocomplete from Elasticsearch via backend."""
    if not q or len(q) < 2:
        return []
    try:
        r = requests.get(f"{BACKEND}/autocomplete", params={"q": q}, timeout=3)
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
    <div class="hero-tagline">Tell us what you love. We\u2019ll find your next favourite film.</div>
</div>
""",
    unsafe_allow_html=True,
)

# -- Search + autocomplete ------------------------------------
_, center, _ = st.columns([1, 3, 1])
with center:
    query = st.text_input(
        "search",
        placeholder="Search for a movie ...",
        label_visibility="collapsed",
        key="search_input",
    )

    # Inline suggestion list (Google/YouTube style)
    if query and len(query) >= 2:
        suggestions = fetch_suggestions(query)
        if suggestions:
            for i, title in enumerate(suggestions):
                c_title, c_btn = st.columns([5, 0.6])
                with c_title:
                    st.markdown(f"**{title}**")
                with c_btn:
                    if st.button("\u002B", key=f"ac_{i}", help=f"Add {title}"):
                        add_movie(title)
                        st.rerun()

    # -- Last-viewed movie details -----------------------------
    movie = st.session_state.last_viewed_movie
    if movie:
        st.markdown("---")
        col_img, col_txt = st.columns([1, 3])
        with col_img:
            if movie.get("poster"):
                st.image(movie["poster"], use_column_width=True)
        with col_txt:
            st.markdown(f"### {movie.get('title', '')}")
            st.markdown(f"**Genres:** {movie.get('genres', 'N/A')}")
            rating = (
                movie.get("avg_predicted_rating")
                or movie.get("avg_rating")
                or movie.get("rating")
            )
            if rating:
                st.markdown(f"**Rating:** \u2B50 {_rating_display(rating)}")
            if movie.get("overview"):
                st.write(movie["overview"])
            if movie.get("cast") and movie["cast"] != "N/A":
                st.caption(f"\U0001F3AD Cast: {movie['cast']}")

    st.divider()

    # -- Selected movies chips ---------------------------------
    if st.session_state.selected_movies:
        st.markdown("**Your selections**")
        chip_html = " ".join(
            f'<span class="chip">{name}</span>'
            for name in st.session_state.selected_movies
        )
        st.markdown(chip_html, unsafe_allow_html=True)

        rm_cols = st.columns(min(len(st.session_state.selected_movies), 6))
        for idx, name in enumerate(st.session_state.selected_movies):
            with rm_cols[idx % len(rm_cols)]:
                if st.button(f"\u2715 {name[:20]}", key=f"rm_{idx}"):
                    st.session_state.selected_movies.pop(idx)
                    if not st.session_state.selected_movies:
                        st.session_state.last_viewed_movie = None
                    st.rerun()
        st.divider()

    # -- Filters -----------------------------------------------
    with st.expander("Filters", expanded=False):
        genres = load_genres()
        f_c1, f_c2 = st.columns(2)
        with f_c1:
            genre = st.selectbox("Genre", genres, key="filter_genre")
        with f_c2:
            year_range = st.slider("Year range", 1900, 2026, key="filter_year")
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
        st.session_state["top_n"] = st.selectbox(
            "Top-N", [6, 8, 10, 12, 16, 20], index=3, label_visibility="collapsed"
        )
    with b3:
        if st.button("\U0001F5D1 Clear all", use_container_width=True):
            st.session_state.selected_movies = []
            st.session_state.recommendations = []
            st.session_state.filter_results = []
            st.session_state.last_viewed_movie = None
            st.rerun()


# -- Movie grid renderer ---------------------------------------
def _render_movie_grid(movies: list[dict], cols_count: int = 4, selectable: bool = False):
    """Render a grid of movie cards. If selectable, show an Add button."""
    cols = st.columns(cols_count, gap="small")
    for i, movie in enumerate(movies):
        with cols[i % cols_count]:
            poster = movie.get("poster", "")
            if poster:
                st.image(poster, use_column_width=True)
            else:
                st.markdown(
                    '<div style="background:#e0e0e0;height:220px;display:flex;'
                    'align-items:center;justify-content:center;border-radius:8px;'
                    'color:#999;">No poster</div>',
                    unsafe_allow_html=True,
                )

            st.markdown(
                f'<p class="movie-title">{movie.get("title", "Unknown")}</p>',
                unsafe_allow_html=True,
            )

            genres_str = movie.get("genres", "")
            if genres_str:
                badges = " ".join(
                    f'<span class="genre-badge">{g.strip()}</span>'
                    for g in str(genres_str).split("|")[:3]
                )
                st.markdown(badges, unsafe_allow_html=True)

            rating = (
                movie.get("avg_predicted_rating")
                or movie.get("avg_rating")
                or movie.get("rating")
            )
            if rating:
                st.markdown(
                    f'<p class="movie-rating">\u2B50 {_rating_display(rating)}</p>',
                    unsafe_allow_html=True,
                )

            overview = movie.get("overview", "")
            if overview:
                with st.expander("Synopsis"):
                    st.caption(
                        overview[:250] + ("\u2026" if len(overview) > 250 else "")
                    )

            cast = movie.get("cast", "")
            if cast and cast != "N/A":
                with st.expander("Cast"):
                    st.caption(cast)

            if selectable:
                m_title = movie.get("title", "")
                if m_title:
                    already = m_title in st.session_state.selected_movies
                    if already:
                        st.button("Added", key=f"pop_{i}", disabled=True, use_container_width=True)
                    else:
                        st.button(
                            "+ Add",
                            key=f"pop_{i}",
                            use_container_width=True,
                            on_click=add_movie,
                            args=(m_title,),
                        )


# -- Main display area -----------------------------------------
st.divider()

if st.session_state.recommendations:
    st.subheader("Recommended for You")
    _render_movie_grid(st.session_state.recommendations, cols_count=4)
else:
    st.subheader("Popular Movies")
    popular = load_popular_movies()
    if popular:
        _render_movie_grid(popular, cols_count=5, selectable=True)
    else:
        st.info("Loading popular movies ...")
