"""Flask REST API for the Movie Recommendation System.

Endpoints
─────────
GET  /                  → Health check
GET  /health            → Health check
GET  /autocomplete?q=   → Title autocomplete (Elasticsearch)
GET  /genres            → Distinct genres from dataset
GET  /movies/popular    → Popular movies (BigQuery)
POST /movies/filter     → Filtered movies by genre/year/rating
POST /recommend         → ML-based recommendations
GET  /movie/<tmdb_id>   → TMDB movie details
GET  /movie-info?title= → Movie info by title search

All SQL queries are printed to the terminal via run_query().
"""

from flask import Flask, jsonify, request
from flask_cors import CORS

from bigquery_utils import (
    get_genres,
    get_movies_with_filters,
    get_popular_movies,
    search_by_title,
)
from elasticsearch_utils import autocomplete_search
from recommender import get_recommendations, _enrich_row
from tmdb_utils import get_movie_details

app = Flask(__name__)
CORS(app)


# ── Health ────────────────────────────────────────────
@app.route("/")
@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "movie-recommender-backend"})


# ── Autocomplete ──────────────────────────────────────
@app.route("/autocomplete")
def autocomplete():
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"results": []})
    results = autocomplete_search(q)
    return jsonify({"results": results})


# ── Genres ────────────────────────────────────────────
@app.route("/genres")
def genres():
    try:
        return jsonify({"genres": get_genres()})
    except Exception as e:
        return jsonify({"genres": [], "error": str(e)}), 500


# ── Languages (from TMDB config) ─────────────────────
LANGUAGE_MAP = {
    "en": "English", "fr": "French", "de": "German", "es": "Spanish",
    "it": "Italian", "ja": "Japanese", "ko": "Korean", "zh": "Chinese",
    "hi": "Hindi", "pt": "Portuguese", "ru": "Russian", "ar": "Arabic",
    "nl": "Dutch", "sv": "Swedish", "da": "Danish", "no": "Norwegian",
    "fi": "Finnish", "pl": "Polish", "tr": "Turkish", "th": "Thai",
    "cs": "Czech", "el": "Greek", "he": "Hebrew", "hu": "Hungarian",
    "ro": "Romanian", "ta": "Tamil", "te": "Telugu",
}


@app.route("/languages")
def languages():
    return jsonify({"languages": LANGUAGE_MAP})


# ── Popular movies ────────────────────────────────────
@app.route("/movies/popular")
def popular():
    df = get_popular_movies(20)
    movies = [_enrich_row(r) for r in df.to_dict(orient="records")]
    return jsonify({"movies": movies})


# ── Filtered movies ───────────────────────────────────
@app.route("/movies/filter", methods=["POST"])
def movies_filter():
    try:
        body = request.get_json() or {}
        df = get_movies_with_filters(
            genre=body.get("genre"),
            min_rating=float(body.get("min_rating", 0)),
            year_min=int(body.get("year_min", 1900)),
            year_max=int(body.get("year_max", 2025)),
            top_n=int(body.get("n", 20)),
        )
        results = [_enrich_row(r) for r in df.to_dict(orient="records")]
        return jsonify(results)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "recommendations": []}), 200


# ── Recommendations ───────────────────────────────────
@app.route("/recommend", methods=["POST"])
def recommend():
    """Get ML-based recommendations.

    Body: {"movies": ["Inception (2010)", ...], "n": 10}
    """
    try:
        data = request.get_json() or {}
        movies = data.get("movies", data.get("movie_titles", []))
        n = data.get("n", data.get("top_n", 10))
        results = get_recommendations(movies, top_n=n)
        return jsonify({"recommendations": results})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "recommendations": []}), 200


# ── Movie details (TMDB) ─────────────────────────────
@app.route("/movie/<int:tmdb_id>")
def movie_detail(tmdb_id):
    title = request.args.get("title", "")
    return jsonify(get_movie_details(tmdb_id, fallback_title=title))


@app.route("/movie-info")
def movie_info():
    """Dataset + TMDB lookup by title."""
    title = request.args.get("title", "").strip()
    if not title:
        return jsonify({"error": "Missing title"}), 400
    try:
        df = search_by_title(title, limit=1)
        if df.empty:
            return jsonify({"movie": None})
        enriched = _enrich_row(df.to_dict(orient="records")[0])
        return jsonify({"movie": enriched})
    except Exception as e:
        return jsonify({"error": str(e), "movie": None}), 200


# ── Entry point ───────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
