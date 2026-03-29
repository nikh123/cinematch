# CineMatch — Movie Recommendation System

2-tier web app: Flask backend (BigQuery ML + Elasticsearch + TMDB) and Streamlit frontend.

## Live Application

**URL:** https://cinematch-frontend-97118476415.europe-west6.run.app

## Architecture

- **Backend** (`/backend`): Flask REST API on port 8080 — BigQuery ML, Elasticsearch autocomplete, TMDB enrichment
- **Frontend** (`/frontend`): Streamlit UI on port 8080 (Cloud Run)
- **Infrastructure**: Google Cloud Run (europe-west6), BigQuery ML, Elastic Cloud, TMDB API

## Similarity Computation Method

CineMatch uses an **overlap-count similarity** approach to identify users with similar taste:

1. **Input**: The user selects one or more movies they enjoy in the Streamlit UI.
2. **High-rating filter**: We query the `ml-small-ratings` table for all users who rated **every** selected movie with `rating_im >= 0.7` (on a 0–1 normalised scale). This threshold corresponds to a "liked" rating.
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

$$\text{score}(m) = \frac{\sum_{u} \hat{r}_{u,m} \cdot w_u}{\sum_{u} w_u} \cdot \text{genre\_boost}(m)$$

   where $\hat{r}_{u,m}$ is the model's `predicted_rating_im_confidence` for user $u$ and movie $m$, and $w_u$ is the user's `common_count`.

6. **Genre boost**: Movies whose genres overlap with the input selection receive an additional multiplier of $(1 + 0.5 \times |\text{shared genres}|)$, promoting genre-relevant results.

## Building Locally with Docker

```bash
# Backend
cd backend
docker build -t cinematch-backend .
docker run -p 8080:8080 \
  -e ES_URL="<your-es-url>" \
  -e ES_API_KEY="<your-es-api-key>" \
  -e TMDB_API_KEY="<your-tmdb-key>" \
  cinematch-backend

# Frontend (in a second terminal)
cd frontend
docker build -t cinematch-frontend .
docker run -p 8501:8080 \
  -e BACKEND_URL="http://host.docker.internal:8080" \
  cinematch-frontend
```

All executed SQL queries and their outputs are printed to the terminal (stdout) by the `run_query()` function in `bigquery_utils.py`.

## Deployment

Both services are deployed as Docker containers on Google Cloud Run (europe-west6), built via Cloud Build and stored in Artifact Registry.
