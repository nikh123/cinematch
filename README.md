# Cloud & Advanced Analytics 2025 — Assignment 2
### CineMatch — Movie Recommendation System

## 🌐 Live URL
[**https://cinematch-frontend-97118476415.europe-west6.run.app**](https://cinematch-frontend-97118476415.europe-west6.run.app)

---

## Overview

A two-tier movie recommendation web application. The Flask backend serves a REST API powered by BigQuery ML (matrix-factorisation collaborative filtering), Elasticsearch (autocomplete search), and the TMDB API (poster and cast enrichment). The Streamlit frontend lets users search, filter, select movies they like, and receive personalised recommendations. Both services are containerised with Docker and deployed on Google Cloud Run.

---

## Features Implemented

| Feature | Implementation |
|---|---|
| **Autocomplete search** | Elasticsearch `match_phrase_prefix` query via `/autocomplete` endpoint |
| **Genre filter** | `WHERE genres LIKE '%genre%'` on movies table |
| **Language filter** | `WHERE language = ?` on `movies_db` table |
| **Country filter** | `WHERE country = ?` on `movies_db` table |
| **Year range filter** | `BETWEEN year_min AND year_max` |
| **Rating filter** | `JOIN` with ratings + `GROUP BY` + `HAVING AVG(rating_im) >= ?` |
| **Movie details** | TMDB API — poster, overview, cast (with title-based fallback) |
| **Recommendation engine** | Overlap-count user similarity → BigQuery ML `ML.RECOMMEND` → genre-boosted weighted scoring |
| **SQL logging** | All executed SQL printed to terminal via `run_query()` |

---

## Similarity Computation Method

CineMatch uses an **overlap-count similarity** approach to identify users with similar taste:

1. **Input**: The user selects one or more movies they enjoy in the Streamlit UI.
2. **High-rating filter**: We query the `ml-small-ratings` table for all users who rated the selected movies with `rating_im >= 0.7` (on a 0–1 normalised scale). This threshold corresponds to a "liked" rating.
3. **Overlap count**: For each candidate user, we count how many of the selected movies they rated highly. Users who liked **more** of the input movies are considered more similar.
4. **Ranking**: Candidate users are sorted by `common_count DESC` and the top-K (default 10) are retained.

```sql
SELECT userId, COUNT(*) AS common_count
FROM ratings
WHERE movieId IN (<selected_ids>) AND rating_im >= 0.7
GROUP BY userId
ORDER BY common_count DESC
LIMIT 10
```

5. **Weighted ML predictions**: These similar users are fed into `ML.RECOMMEND` (a BigQuery ML matrix-factorisation model). Each user's predicted ratings are weighted by their `common_count`, so users who share more liked movies have a greater influence on the final ranking:

```
score(m) = [ Σ_u  r̂(u,m) · w_u ] / [ Σ_u  w_u ]  ×  genre_boost(m)
```

   where `r̂(u,m)` is the model's `predicted_rating_im_confidence` for user `u` and movie `m`, and `w_u` is that user's `common_count`.

6. **Genre boost**: Movies whose genres overlap with the input selection receive an additional multiplier of `(1 + 0.5 × |shared genres|)`, promoting genre-relevant results.

---

## Project Structure

```
cinematch-deploy/
├── backend/
│   ├── app.py               # Flask REST API (routes)
│   ├── bigquery_utils.py    # All BigQuery/SQL functions
│   ├── recommender.py       # Recommendation pipeline orchestration
│   ├── elasticsearch_utils.py # Elasticsearch autocomplete + indexing
│   ├── tmdb_utils.py        # TMDB API calls
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile           # Backend container definition
├── frontend/
│   ├── app.py               # Streamlit UI
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile           # Frontend container definition
└── README.md
```

**Two-tier architecture:**
- **Backend (Flask)**: REST API on port 8080 — BigQuery ML, Elasticsearch, TMDB enrichment
- **Frontend (Streamlit)**: UI on port 8080 (Cloud Run) — communicates with backend via HTTP
- **Infrastructure**: Google Cloud Run (europe-west6), BigQuery ML (`Assignment_1` dataset), Elastic Cloud, TMDB API

---

## AI Disclosure

GitHub Copilot (Claude Sonnet) was used as an AI assistant during the development of this project. Specifically, it assisted with:

- Scaffolding the initial project structure and file layout
- Writing and debugging the BigQuery SQL queries in `bigquery_utils.py`
- Implementing the Streamlit `st.session_state` pattern to fix results disappearing on widget interaction
- Writing the TMDB API wrapper in `tmdb_utils.py`
- Implementing the Elasticsearch autocomplete integration
- Debugging Cloud Run deployment issues (environment variables, memory limits)
- Drafting this README

All code was reviewed, tested, and verified against the live BigQuery dataset and TMDB API by the author.
