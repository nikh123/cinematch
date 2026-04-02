"""Elasticsearch utilities — indexing and autocomplete search.

Uses 'match_phrase_prefix' for autocomplete queries (cf. Lab 6).
Run this file directly to re-index: python elasticsearch_utils.py
"""

import os

import pandas as pd
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

ES_URL = os.environ.get("ES_URL", "")
ES_API_KEY = os.environ.get("ES_API_KEY", "")
INDEX_NAME = "assignment2"


def get_es_client() -> Elasticsearch:
    return Elasticsearch(ES_URL, api_key=ES_API_KEY, request_timeout=30)


def index_movies(movies_df: pd.DataFrame) -> int:
    """Drop + recreate the index, then bulk-insert movies."""
    client = get_es_client()

    if client.indices.exists(index=INDEX_NAME):
        client.indices.delete(index=INDEX_NAME)

    client.indices.create(
        index=INDEX_NAME,
        body={
            "mappings": {
                "properties": {
                    "movieId": {"type": "integer"},
                    "title": {"type": "text"},
                    "genres": {"type": "text"},
                }
            }
        },
    )

    actions = [
        {
            "_index": INDEX_NAME,
            "_source": {
                "movieId": int(row["movieId"]),
                "title": row["title"],
                "genres": row["genres"],
            },
        }
        for _, row in movies_df.iterrows()
    ]
    success, failed = bulk(client, actions, raise_on_error=False)
    print(f"Indexed {success} documents, failed {failed}")
    return success


def autocomplete_search(query: str, size: int = 10) -> list[str]:
    """Return matching movie titles using match_phrase_prefix (cf. Lab 6)."""
    try:
        client = get_es_client()
        resp = client.search(
            index=INDEX_NAME,
            body={
                "query": {
                    "match_phrase_prefix": {
                        "title": {
                            "query": query,
                            "max_expansions": 10,
                        }
                    }
                },
                "size": size,
            },
        )
        return [hit["_source"]["title"] for hit in resp["hits"]["hits"]]
    except Exception as e:
        print(f"Autocomplete error: {e}")
        return []


# ── CLI: re-index from BigQuery ──────────────────────
if __name__ == "__main__":
    from bigquery_utils import get_all_movies

    print("Fetching movies from BigQuery …")
    df = get_all_movies()
    print(f"Got {len(df)} movies. Indexing into Elasticsearch …")
    index_movies(df)
    print("Sample autocomplete for 'toy':", autocomplete_search("toy"))
    print("Done!")
