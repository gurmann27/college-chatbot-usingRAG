"""CLI script to create or update the Azure AI Search index schema (hybrid + optional semantic)."""
from __future__ import annotations

import argparse
import asyncio

import httpx

from app.config import get_settings


def build_index_schema(index_name: str, dimensions: int, semantic_config: str, enable_semantic: bool) -> dict:
    schema: dict = {
        "name": index_name,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
            {"name": "document_id", "type": "Edm.String", "filterable": True, "facetable": True},
            {"name": "document_name", "type": "Edm.String", "searchable": True, "filterable": True},
            {"name": "page", "type": "Edm.Int32", "filterable": True, "sortable": True},
            {"name": "content", "type": "Edm.String", "searchable": True, "analyzer": "standard.lucene"},
            {"name": "section_title", "type": "Edm.String", "searchable": True},
            {
                "name": "content_vector",
                "type": "Collection(Edm.Single)",
                "searchable": True,
                "dimensions": dimensions,
                "vectorSearchProfile": "hnsw-cosine",
            },
            {"name": "category", "type": "Edm.String", "filterable": True, "facetable": True},
            {"name": "effective_date", "type": "Edm.String", "filterable": True, "sortable": True},
            {"name": "version", "type": "Edm.String", "filterable": True},
            {"name": "language", "type": "Edm.String", "filterable": True},
            {"name": "content_hash", "type": "Edm.String", "filterable": True},
            {"name": "blob_name", "type": "Edm.String", "filterable": True},
        ],
        "vectorSearch": {
            "algorithms": [{"name": "hnsw-alg", "kind": "hnsw", "hnswParameters": {"metric": "cosine"}}],
            "profiles": [{"name": "hnsw-cosine", "algorithm": "hnsw-alg"}],
        },
    }
    if enable_semantic:
        schema["semantic"] = {
            "configurations": [
                {
                    "name": semantic_config,
                    "prioritizedFields": {
                        "titleField": {"fieldName": "section_title"},
                        "prioritizedContentFields": [{"fieldName": "content"}],
                        "prioritizedKeywordsFields": [{"fieldName": "category"}],
                    },
                }
            ]
        }
    return schema


async def create_or_update_index(*, enable_semantic: bool = False) -> None:
    s = get_settings()
    schema = build_index_schema(s.azure_search_index, s.embedding_dimensions, s.semantic_config_name, enable_semantic)
    if s.mock_azure:
        print(f"[MOCK_AZURE=true] Validated index schema for '{s.azure_search_index}' ({len(schema['fields'])} fields).")
        return
    url = f"{s.azure_search_endpoint.rstrip('/')}/indexes/{s.azure_search_index}?api-version={s.azure_search_api_version}"
    headers = {"api-key": s.azure_search_api_key.get_secret_value(), "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(url, headers=headers, json=schema)
        resp.raise_for_status()
        print(f"Index '{s.azure_search_index}' created/updated (HTTP {resp.status_code}).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or update Azure AI Search index.")
    parser.add_argument("--semantic", action="store_true", help="Include semantic configuration (Basic+ tier)")
    args = parser.parse_args()
    asyncio.run(create_or_update_index(enable_semantic=args.semantic))


if __name__ == "__main__":
    main()

