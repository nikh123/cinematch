"""TMDB (The Movie Database) API wrapper.

Fetches movie poster, synopsis, cast and metadata for display in the UI.
"""

import os

import requests

TMDB_API_KEY = os.environ["TMDB_API_KEY"]
BASE_URL = "https://api.themoviedb.org/3"
IMG_BASE = "https://image.tmdb.org/t/p/w500"


def _search_tmdb_by_title(title: str) -> dict:
    """Fallback: search TMDB by title when tmdb_id is missing or invalid."""
    if not TMDB_API_KEY or not title:
        return {}
    import re
    clean = re.sub(r"\s*\(\d{4}\)\s*$", "", str(title)).strip()
    try:
        resp = requests.get(
            f"{BASE_URL}/search/movie",
            params={"api_key": TMDB_API_KEY, "query": clean},
            timeout=10,
        )
        if resp.status_code != 200:
            return {}
        results = resp.json().get("results", [])
        if not results:
            return {}
        hit = results[0]
        poster_path = hit.get("poster_path")
        return {
            "title": hit.get("title"),
            "overview": hit.get("overview"),
            "poster": f"{IMG_BASE}{poster_path}" if poster_path else None,
            "cast": "N/A",
            "genres": "N/A",
            "rating": hit.get("vote_average"),
            "release": hit.get("release_date"),
            "runtime": None,
            "language": hit.get("original_language", ""),
        }
    except requests.RequestException:
        return {}


def get_movie_details(tmdb_id: int, fallback_title: str = "") -> dict:
    """Fetch poster, overview, cast and metadata from TMDB.

    Returns dict with keys: title, overview, poster, cast, genres, rating, release, runtime, language.
    Falls back to search-by-title if tmdb_id lookup fails.
    Returns empty dict on failure.
    """
    if not TMDB_API_KEY:
        return {}

    if tmdb_id:
        url = f"{BASE_URL}/movie/{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=credits"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                poster_path = data.get("poster_path")
                cast_list = [c["name"] for c in data.get("credits", {}).get("cast", [])[:5]]
                genre_list = [g["name"] for g in data.get("genres", [])]
                return {
                    "title": data.get("title"),
                    "overview": data.get("overview"),
                    "poster": f"{IMG_BASE}{poster_path}" if poster_path else None,
                    "cast": ", ".join(cast_list) if cast_list else "N/A",
                    "genres": ", ".join(genre_list) if genre_list else "N/A",
                    "rating": data.get("vote_average"),
                    "release": data.get("release_date"),
                    "runtime": data.get("runtime"),
                    "language": data.get("original_language", ""),
                }
        except requests.RequestException:
            pass

    # Fallback: search by title
    if fallback_title:
        return _search_tmdb_by_title(fallback_title)
    return {}
