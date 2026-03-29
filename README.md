# CineMatch — Movie Recommendation System

2-tier web app: Flask backend (BigQuery ML + Elasticsearch + TMDB) and Streamlit frontend.

## Architecture
- **Backend** (`/backend`): Flask REST API on port 8080
- **Frontend** (`/frontend`): Streamlit UI on port 8080 (Cloud Run)

## Deployment
Both services are deployed as Docker containers on Google Cloud Run.
