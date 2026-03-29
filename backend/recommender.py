"""Recommendation orchestration layer.

Pipeline: titles → movieIds → similar users → ML recommendations → TMDB enrichment.
Falls back to popular movies when any stage returns no results.
"""

from __future__ import annotations

import math
from typing import Any

from bigquery_utils import (
    find_similar_users,
    get_genres_for_movies,
    get_ml_recommendations,
    get_movie_ids_from_titles,
    get_popular_movies,
)
from tmdb_utils import get_movie_details


def _safe_tmdb_id(value: Any) -> int | None:
    if value is None:
        return None
    try:
        if isinstance(value, float) and math.isnan(value):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _enrich_row(row: dict) -> dict:
    """Attach TMDB poster, overview and cast to a movie row."""
    tmdb_id = _safe_tmdb_id(row.get("tmdbId"))
    title = row.get("title", "")
    details = get_movie_details(tmdb_id, fallback_title=title) if (tmdb_id or title) else {}

    enriched = dict(row)
    enriched["poster"] = details.get("poster") if isinstance(details, dict) else None
    enriched["overview"] = details.get("overview", "") if isinstance(details, dict) else ""
    enriched["cast"] = details.get("cast", "") if isinstance(details, dict) else ""
    enriched["language"] = details.get("language", "") if isinstance(details, dict) else ""
    return enriched


def _popular_fallback(top_n: int) -> list[dict]:
    """Return enriched popular movies as a fallback."""
    df = get_popular_movies(top_n=top_n)
    return [_enrich_row(r) for r in df.to_dict(orient="records")]


def get_recommendations(movie_titles: list, top_n: int = 10) -> list[dict]:
    """Main recommendation entry-point.

    Cold-start (no movies selected) → global popular movies.
    Otherwise → find similar users → ML.RECOMMEND → enrich with TMDB.
    """
    if not isinstance(movie_titles, list):
        movie_titles = []
    top_n = max(int(top_n or 10), 1)

    # Cold start: no selection
    if not movie_titles:
        return _popular_fallback(top_n)

    # Step 1 — resolve titles to movieIds
    movie_ids = get_movie_ids_from_titles(movie_titles)
    if not movie_ids:
        return _popular_fallback(top_n)

    # Step 2 — find similar users (with similarity weights)
    similar_users = find_similar_users(movie_ids)
    if not similar_users:
        return _popular_fallback(top_n)

    # Step 2.5 — extract genres from input movies for boosting
    preferred_genres = get_genres_for_movies(movie_ids)

    # Step 3 — ML recommendations (weighted by similarity + genre boost)
    try:
        rec_df = get_ml_recommendations(
            similar_users,
            exclude_movie_ids=movie_ids,
            top_n=top_n,
            preferred_genres=preferred_genres,
        )
    except Exception:
        return _popular_fallback(top_n)

    if rec_df.empty:
        return _popular_fallback(top_n)

    return [_enrich_row(r) for r in rec_df.to_dict(orient="records")]
