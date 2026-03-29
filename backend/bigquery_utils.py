"""BigQuery utility functions for the Movie Recommendation System.

All SQL queries are printed to the terminal before execution,
as required by the assignment specification.

Uses the ml-small dataset:
  - ml-small-movies  (movieId, title, genres)
  - ml-small-ratings (userId, movieId, date, rating_im)
  - ml-small-links   (movieId, imdbId, tmdbId)
  - rec_model        (BigQuery ML matrix-factorization model)
"""

from __future__ import annotations

import os
import re

from google.cloud import bigquery
from google.oauth2 import service_account
import pandas as pd

# ── Configuration ─────────────────────────────────────
PROJECT_ID = "cloudproject-488613"
DATASET = "Assignment_1"
LOCATION = "europe-west6"

# Service-account key (look next to backend/ or one level up)
_KEY_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
if not _KEY_FILE:
    for candidate in [
        os.path.join(os.path.dirname(__file__), "..", "cloudproject-488613-8481e811e152.json"),
        os.path.join(os.path.dirname(__file__), "cloudproject-488613-8481e811e152.json"),
    ]:
        if os.path.isfile(candidate):
            _KEY_FILE = os.path.abspath(candidate)
            break

# Backtick-wrapped references (required for hyphenated table names)
MOVIES = f"`{PROJECT_ID}.{DATASET}.ml-small-movies`"
RATINGS = f"`{PROJECT_ID}.{DATASET}.ml-small-ratings`"
LINKS = f"`{PROJECT_ID}.{DATASET}.ml-small-links`"
REC_MODEL = f"`{PROJECT_ID}.{DATASET}.rec_model`"


# ── Helpers ───────────────────────────────────────────
def format_title(title: str) -> str:
    """Convert 'Title, The (Year)' → 'The Title (Year)'."""
    m = re.match(r"^(.*),\s*(The|A|An)\s*(\(\d{4}\))?\s*$", str(title).strip())
    if m:
        base, article, year = m.group(1).strip(), m.group(2), m.group(3) or ""
        return f"{article} {base} {year}".strip()
    return title


def get_client() -> bigquery.Client:
    if _KEY_FILE:
        creds = service_account.Credentials.from_service_account_file(_KEY_FILE)
        return bigquery.Client(project=PROJECT_ID, location=LOCATION, credentials=creds)
    return bigquery.Client(project=PROJECT_ID, location=LOCATION)


def run_query(sql: str) -> pd.DataFrame:
    """Execute SQL, print query + results to terminal, return DataFrame."""
    print(f"\n{'='*60}\n SQL QUERY\n{'='*60}\n{sql}\n{'='*60}")
    client = get_client()
    df = client.query(sql).to_dataframe()
    print(f"→ {len(df)} rows returned\n{df.to_string()}\n")
    return df


# ── Movie retrieval ───────────────────────────────────
def get_all_movies(limit: int = 50_000) -> pd.DataFrame:
    """All movies (for Elasticsearch bulk-indexing)."""
    df = run_query(f"SELECT movieId, title, genres FROM {MOVIES} LIMIT {limit}")
    if not df.empty:
        df["title"] = df["title"].apply(format_title)
    return df


def get_popular_movies(top_n: int = 20) -> pd.DataFrame:
    """Top-rated movies (>= 5 ratings). Used for the home page / cold-start."""
    sql = f"""
        SELECT m.movieId, m.title, m.genres, l.tmdbId,
               ROUND(AVG(r.rating_im), 2) AS avg_rating,
               COUNT(*) AS num_ratings
        FROM {MOVIES} m
        JOIN {RATINGS} r ON m.movieId = r.movieId
        LEFT JOIN {LINKS} l ON m.movieId = l.movieId
        GROUP BY m.movieId, m.title, m.genres, l.tmdbId
        HAVING COUNT(*) >= 5
        ORDER BY avg_rating DESC, num_ratings DESC
        LIMIT {top_n}
    """
    df = run_query(sql)
    if not df.empty:
        df["title"] = df["title"].apply(format_title)
    return df


def search_by_title(title: str, limit: int = 5) -> pd.DataFrame:
    """Search movies by title substring (used by /movie-info)."""
    safe = title.replace("'", "\\'")
    sql = f"""
        SELECT m.movieId, m.title, m.genres, l.tmdbId
        FROM {MOVIES} m
        LEFT JOIN {LINKS} l ON m.movieId = l.movieId
        WHERE LOWER(m.title) LIKE LOWER('%{safe}%')
        ORDER BY m.title
        LIMIT {limit}
    """
    df = run_query(sql)
    if not df.empty:
        df["title"] = df["title"].apply(format_title)
    return df


# ── Filters & genres ─────────────────────────────────
def get_genres() -> list[str]:
    """Distinct genres (pipe-separated values unnested)."""
    sql = f"""
        SELECT DISTINCT genre
        FROM {MOVIES}, UNNEST(SPLIT(genres, '|')) AS genre
        WHERE genre != '(no genres listed)'
        ORDER BY genre
    """
    df = run_query(sql)
    return df["genre"].tolist() if not df.empty else []


def get_movies_with_filters(
    genre: str | None = None,
    min_rating: float = 0,
    year_min: int = 1900,
    year_max: int = 2025,
    top_n: int = 20,
) -> pd.DataFrame:
    """Movies filtered by genre, year range and minimum average rating."""
    genre_clause = f"AND m.genres LIKE '%{genre}%'" if genre and genre != "All" else ""
    year_clause = f"""
        AND SAFE_CAST(REGEXP_EXTRACT(m.title, r'\\((\\d{{4}})\\)$') AS INT64)
            BETWEEN {year_min} AND {year_max}
    """
    sql = f"""
        SELECT m.movieId, m.title, m.genres, l.tmdbId,
               ROUND(AVG(r.rating_im), 2) AS avg_rating
        FROM {MOVIES} m
        JOIN {RATINGS} r ON m.movieId = r.movieId
        LEFT JOIN {LINKS} l ON m.movieId = l.movieId
        WHERE 1=1 {genre_clause} {year_clause}
        GROUP BY m.movieId, m.title, m.genres, l.tmdbId
        HAVING AVG(r.rating_im) >= {min_rating}
        ORDER BY avg_rating DESC
        LIMIT {top_n}
    """
    df = run_query(sql)
    if not df.empty:
        df["title"] = df["title"].apply(format_title)
    return df


# ── Recommendation pipeline ──────────────────────────
def get_movie_ids_from_titles(titles: list[str]) -> list[int]:
    """Resolve UI movie titles to movieIds.

    Handles both formatted titles ('The Matrix (1999)') and raw DB titles
    ('Matrix, The (1999)').
    """
    if not titles:
        return []

    conditions: list[str] = []
    for title in titles:
        safe = str(title).replace("'", "\\'")
        conditions.append(f"LOWER(title) = LOWER('{safe}')")

        # Reverse format_title: "The Matrix (1999)" -> "Matrix, The (1999)"
        rev = re.match(r"^(The|A|An)\s+(.+?)(\s*\(\d{4}\))?\s*$", str(title), re.IGNORECASE)
        if rev:
            article, base = rev.group(1), rev.group(2).replace("'", "\\'")
            year = rev.group(3) or ""
            conditions.append(f"LOWER(title) = LOWER('{base}, {article}{year}')")

        # Fuzzy: strip year, LIKE match
        base_title = re.sub(r"\s*\(\d{4}\)\s*$", "", str(title)).replace("'", "\\'").strip()
        if base_title:
            conditions.append(f"LOWER(title) LIKE LOWER('%{base_title}%')")

    sql = f"""
        SELECT DISTINCT movieId
        FROM {MOVIES}
        WHERE {' OR '.join(conditions)}
        LIMIT 100
    """
    df = run_query(sql)
    return df["movieId"].astype(int).tolist() if not df.empty else []


def find_similar_users(movie_ids: list[int], top_k: int = 10) -> list[dict]:
    """Find users who rated the given movies highly (rating_im >= 0.7).

    rating_im is on a 0-1 scale. Users are ranked by the number of
    overlapping high-rated movies.

    Returns list of dicts: [{"userId": int, "common_count": int}, ...].
    """
    if not movie_ids:
        return []
    ids_str = ", ".join(str(i) for i in movie_ids)
    sql = f"""
        SELECT userId, COUNT(*) AS common_count
        FROM {RATINGS}
        WHERE movieId IN ({ids_str}) AND rating_im >= 0.7
        GROUP BY userId
        ORDER BY common_count DESC
        LIMIT {top_k}
    """
    df = run_query(sql)
    if df.empty:
        return []
    return df.to_dict(orient="records")


def get_genres_for_movies(movie_ids: list[int]) -> list[str]:
    """Return the distinct genre tags for a set of movieIds."""
    if not movie_ids:
        return []
    ids_str = ", ".join(str(i) for i in movie_ids)
    sql = f"""
        SELECT DISTINCT genre
        FROM {MOVIES}, UNNEST(SPLIT(genres, '|')) AS genre
        WHERE movieId IN ({ids_str}) AND genre != '(no genres listed)'
    """
    df = run_query(sql)
    return df["genre"].tolist() if not df.empty else []


def get_ml_recommendations(
    user_weights: list[dict],
    exclude_movie_ids: list[int],
    top_n: int = 10,
    preferred_genres: list[str] | None = None,
) -> pd.DataFrame:
    """Generate recommendations with BigQuery ML.RECOMMEND.

    Uses the trained matrix-factorization model (rec_model) to
    predict ratings for the given similar users, weighted by their
    similarity score (common_count).

    When *preferred_genres* is supplied, movies that share genres with
    the user's input get a scoring boost so genre-relevant results
    float to the top.
    """
    if not user_weights:
        return pd.DataFrame()

    # Build a CTE with user weights so more-similar users count more
    union_parts = " UNION ALL ".join(
        f"SELECT {int(uw['userId'])} AS userId, {int(uw['common_count'])} AS weight"
        for uw in user_weights
    )
    exclude_str = ", ".join(str(i) for i in exclude_movie_ids) if exclude_movie_ids else "0"

    # Genre-boost CTE: each shared genre adds 0.5x boost
    if preferred_genres:
        safe_genres = ", ".join(f"'{g}'" for g in preferred_genres)
        genre_boost_cte = f""",
        input_genres AS (
            SELECT genre FROM UNNEST([{safe_genres}]) AS genre
        )"""
        genre_boost_expr = """(1 + 0.5 * (
                SELECT COUNT(DISTINCT g)
                FROM UNNEST(SPLIT(m.genres, '|')) AS g
                WHERE g IN (SELECT genre FROM input_genres)
            ))"""
    else:
        genre_boost_cte = ""
        genre_boost_expr = "1"

    sql = f"""
        WITH user_weights AS ({union_parts}){genre_boost_cte},
        recs AS (
            SELECT * FROM ML.RECOMMEND(
                MODEL {REC_MODEL},
                (SELECT userId FROM user_weights)
            )
        )
        SELECT r.movieId, m.title, m.genres, l.tmdbId,
               ROUND(SUM(r.predicted_rating_im_confidence * uw.weight)
                     / SUM(uw.weight) * {genre_boost_expr}, 3) AS avg_predicted_rating
        FROM recs r
        JOIN user_weights uw ON r.userId = uw.userId
        JOIN {MOVIES} m ON r.movieId = m.movieId
        LEFT JOIN {LINKS} l ON r.movieId = l.movieId
        WHERE r.movieId NOT IN ({exclude_str})
        GROUP BY r.movieId, m.title, m.genres, l.tmdbId
        ORDER BY avg_predicted_rating DESC
        LIMIT {top_n}
    """
    df = run_query(sql)
    if not df.empty:
        df["title"] = df["title"].apply(format_title)
    return df
