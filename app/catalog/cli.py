"""Catalog CLI — seed the food catalog from external sources.

Usage:
    python -m app.catalog.cli seed [--source usda|openfoodfacts|ecuador|all]

Examples:
    python -m app.catalog.cli seed
    python -m app.catalog.cli seed --source ecuador
    python -m app.catalog.cli seed --source all
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger("nutricia.catalog.cli")


async def _run_seed(source_name: str) -> None:
    """Wire up dependencies and run the seed."""
    from app.catalog.application.seed_use_case import SeedRunner, SeedSource
    from app.catalog.infrastructure.repository import FoodCatalogRepositoryImpl
    from app.config import settings
    from app.shared.infrastructure import async_session
    from app.shared.infrastructure.embeddings import (
        DualEmbeddingsProvider,
        GeminiEmbeddingsProvider,
        OpenAIEmbeddingsProvider,
    )
    from app.shared.infrastructure.vector_store import (
        InMemoryVectorStoreAdapter,
        PgVectorAdapter,
    )

    # Build embeddings provider
    if settings.google_api_key and settings.openai_api_key:
        embeddings_provider = DualEmbeddingsProvider(
            primary=GeminiEmbeddingsProvider(settings.google_api_key),
            fallback=OpenAIEmbeddingsProvider(settings.openai_api_key),
        )
    elif settings.google_api_key:
        embeddings_provider = GeminiEmbeddingsProvider(settings.google_api_key)  # type: ignore[assignment]
    elif settings.openai_api_key:
        embeddings_provider = OpenAIEmbeddingsProvider(settings.openai_api_key)  # type: ignore[assignment]
    else:
        logger.error(
            "No embeddings provider configured. Set GOOGLE_API_KEY or OPENAI_API_KEY."
        )
        sys.exit(1)

    # Build vector store — PgVector if postgres, InMemory otherwise (dev/test)
    db_url: str = settings.database_url
    if db_url.startswith("postgresql"):
        vector_store = PgVectorAdapter(
            session_factory=async_session,
            table_name="food_catalog",
            metadata_columns=["canonical_name", "source"],
        )
    else:
        logger.warning(
            "Non-postgres DB detected — using InMemoryVectorStoreAdapter (test mode)"
        )
        vector_store = InMemoryVectorStoreAdapter()  # type: ignore[assignment]

    # Resolve source
    source: SeedSource | None = None
    if source_name and source_name != "all":
        try:
            source = SeedSource(source_name)
        except ValueError:
            logger.error(
                "Unknown source '%s'. Use: usda, openfoodfacts, ecuador, all",
                source_name,
            )
            sys.exit(1)

    # Wire repository + runner and run within a DB session
    async with async_session() as session:
        repo = FoodCatalogRepositoryImpl(session=session, vector_store=vector_store)
        runner = SeedRunner(repo=repo, embeddings_provider=embeddings_provider)
        logger.info("Starting catalog seed — source: %s", source_name or "all")
        await runner.run(source=source)
        await session.commit()

    logger.info("Catalog seed complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="NutricIA catalog CLI")
    subparsers = parser.add_subparsers(dest="command")

    seed_parser = subparsers.add_parser("seed", help="Seed the food catalog")
    seed_parser.add_argument(
        "--source",
        choices=["usda", "openfoodfacts", "ecuador", "all"],
        default="all",
        help="Data source to seed from (default: all)",
    )

    args = parser.parse_args()

    if args.command == "seed":
        asyncio.run(_run_seed(args.source))
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
