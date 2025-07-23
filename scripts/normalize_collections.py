#!/usr/bin/env python3
"""
Normalize all fields from different collections into a single master_search collection.
This script aggregates all fields for each symbol into one document for efficient querying.
"""

import asyncio
import logging
import math
import os
from datetime import UTC, datetime
from typing import Any

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from tqdm import tqdm

# Setup logging BEFORE using it
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable all pymongo debug logs
logging.getLogger("pymongo").setLevel(logging.WARNING)
logging.getLogger("pymongo.topology").setLevel(logging.WARNING)
logging.getLogger("pymongo.connection").setLevel(logging.WARNING)
logging.getLogger("pymongo.command").setLevel(logging.WARNING)
logging.getLogger("pymongo.serverSelection").setLevel(logging.WARNING)

# Load environment variables
load_dotenv()


class CollectionNormalizer:
    def __init__(self):
        # Use connection pooling for better performance
        self.client = MongoClient(os.getenv("MONGODB_URL"), maxPoolSize=50, minPoolSize=10, maxIdleTimeMS=30000)
        self.db = self.client[os.getenv("MONGODB_DB_NAME")]
        self.master_search = self.db["master_search"]
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Ensure optimal indexes exist for performance."""
        logger.info("Ensuring database indexes...")

        # Index for income statements - critical for growth metrics performance
        income_collection = self.db["master_income_statement"]

        # Create compound index for efficient lookups
        try:
            income_collection.create_index(
                [("symbol", 1), ("fiscal_year", -1), ("fiscal_period", 1)], name="symbol_year_period"
            )
            logger.info("Created compound index on master_income_statement")
        except Exception as e:
            logger.debug(f"Index may already exist: {e}")

        # Ensure symbol index exists
        try:
            income_collection.create_index("symbol", name="symbol_1")
        except Exception as e:
            logger.debug(f"Symbol index may already exist: {e}")

        # Create indexes for other collections used in normalization
        for collection_name in ["master_profiles", "master_ttm_key_metrics_ratios", "master_analyst_ratings_consensus"]:
            try:
                self.db[collection_name].create_index("symbol")
                logger.info(f"Created index on {collection_name}")
            except Exception as e:
                logger.debug(f"Index on {collection_name} may already exist: {e}")

    def get_field_to_collection_mapping(self) -> dict[str, str]:
        """
        Load field to collection mapping from configuration file.
        """
        import yaml

        try:
            config_path = os.path.join(os.path.dirname(__file__), "..", "settings", "field_mappings.yaml")
            with open(config_path) as f:
                config = yaml.safe_load(f)
            return config["field_mappings"]
        except FileNotFoundError:
            logger.error("Field mappings configuration file not found!")
            # Fallback to basic mappings
            return {
                "company_name": "master_profiles",
                "sector": "master_profiles",
                "market_capitalization": "master_profiles",
                "pe_ratio": "ratios",
                "revenue_growth": "financials",
            }

    async def get_all_symbols(self) -> list[str]:
        """Get all unique symbols from collections defined in field mappings."""
        logger.info("Fetching all unique symbols from mapped collections...")

        # Get field mappings to determine which collections to query
        field_mapping = self.get_field_to_collection_mapping()
        target_collections = set(field_mapping.values())

        logger.info(f"Target collections: {target_collections}")

        # Aggregate all unique symbols from only the target collections
        all_symbols = set()
        for collection_name in target_collections:
            try:
                collection = self.db[collection_name]
                # Check if collection exists and has documents with symbol field
                if collection.count_documents({"symbol": {"$exists": True}}) > 0:
                    symbols = collection.distinct("symbol")
                    all_symbols.update(symbols)
                    logger.info(f"Found {len(symbols)} symbols in {collection_name}")
                else:
                    logger.warning(f"Collection {collection_name} has no documents with symbol field")
            except Exception as e:
                logger.error(f"Error accessing collection {collection_name}: {e}")

        logger.info(f"Total unique symbols: {len(all_symbols)}")
        return list(all_symbols)

    async def normalize_batch_data(self, symbols: list[str]) -> list[dict[str, Any]]:
        """Normalize data for a batch of symbols using bulk queries."""
        try:
            field_mapping = self.get_field_to_collection_mapping()

            # Group fields by collection for efficient querying
            collection_fields = {}
            for field, collection_name in field_mapping.items():
                if collection_name not in collection_fields:
                    collection_fields[collection_name] = []
                collection_fields[collection_name].append(field)

            # Pre-fetch all data for all symbols from all collections
            collection_data = {}
            for collection_name, fields in collection_fields.items():
                collection = self.db[collection_name]

                # Build projection to only fetch needed fields
                projection = {"symbol": 1, "_id": 0, "updated_at": 1}
                for field in fields:
                    projection[field] = 1

                # Bulk query with projection: get only needed fields
                cursor = collection.find({"symbol": {"$in": symbols}}, projection).hint(
                    "symbol_1"
                )  # Use index hint for performance

                collection_data[collection_name] = {doc["symbol"]: doc for doc in cursor}

            # Build normalized documents
            normalized_docs = []
            for symbol in symbols:
                normalized_doc = {"symbol": symbol, "last_updated": None, "source_collections": []}

                # Extract data from each collection
                for collection_name, fields in collection_fields.items():
                    if symbol in collection_data[collection_name]:
                        doc = collection_data[collection_name][symbol]
                        normalized_doc["source_collections"].append(collection_name)

                        # Extract specified fields
                        for field in fields:
                            if field in doc:
                                normalized_doc[field] = doc[field]

                        # Update last_updated timestamp if available
                        if "updated_at" in doc and (
                            not normalized_doc["last_updated"] or doc["updated_at"] > normalized_doc["last_updated"]
                        ):
                            normalized_doc["last_updated"] = doc["updated_at"]

                if len(normalized_doc["source_collections"]) > 0:
                    normalized_docs.append(normalized_doc)

            # Calculate growth metrics for all symbols in this batch
            try:
                self._add_growth_metrics_to_batch(normalized_docs)
            except Exception as e:
                logger.warning(f"Error adding growth metrics: {e}")
                # Continue without growth metrics rather than failing

            return normalized_docs

        except Exception as e:
            logger.error(f"Error normalizing batch data: {e}")
            return []

    async def normalize_all_collections(self, batch_size: int = 500, max_symbols: int | None = None):
        """Normalize all collections into master_search."""
        logger.info("Starting collection normalization...")

        # Clear existing master_search collection
        logger.info("Clearing existing master_search collection...")
        self.master_search.delete_many({})

        # Get all symbols
        symbols = await self.get_all_symbols()

        # Limit symbols for testing if specified
        if max_symbols:
            symbols = symbols[:max_symbols]
            logger.info(f"Limited to {len(symbols)} symbols for testing")

        # Process symbols in batches with progress bar
        total_processed = 0
        total_inserted = 0

        with tqdm(total=len(symbols), desc="Processing symbols", unit="symbol") as pbar:
            for i in range(0, len(symbols), batch_size):
                batch_symbols = symbols[i : i + batch_size]

                # Process entire batch at once with bulk queries
                batch_docs = await self.normalize_batch_data(batch_symbols)
                total_processed += len(batch_symbols)
                pbar.update(len(batch_symbols))

                # Insert batch with optimizations
                if batch_docs:
                    try:
                        # Use ordered=False for better performance (allows parallel inserts)
                        self.master_search.insert_many(batch_docs, ordered=False)
                        total_inserted += len(batch_docs)
                        pbar.set_postfix(
                            inserted=total_inserted,
                            batch=i // batch_size + 1,
                            pct=f"{(total_inserted / total_processed) * 100:.1f}%",
                        )
                    except PyMongoError as e:
                        logger.error(f"Error inserting batch: {e}")
                        pbar.set_postfix(error=f"Batch {i // batch_size + 1} failed")
                else:
                    pbar.set_postfix(inserted=total_inserted, batch=i // batch_size + 1, no_data=True)

        logger.info(f"Normalization complete! Processed {total_processed} symbols, inserted {total_inserted} documents")

        # Create index on symbol field
        logger.info("Creating index on symbol field...")
        self.master_search.create_index("symbol", unique=True)

        return total_inserted

    async def verify_normalization(self) -> dict[str, Any]:
        """Verify the normalization results."""
        logger.info("Verifying normalization results...")

        stats = {
            "total_documents": self.master_search.count_documents({}),
            "sample_document": self.master_search.find_one(),
            "collections_represented": self.master_search.distinct("source_collections"),
            "field_coverage": {},
        }

        # Check field coverage
        field_mapping = self.get_field_to_collection_mapping()
        for field in field_mapping:
            count = self.master_search.count_documents({field: {"$exists": True}})
            stats["field_coverage"][field] = count

        logger.info(f"Verification complete: {stats['total_documents']} documents in master_search")
        return stats

    def _calculate_growth_rate(self, old_value: float, new_value: float) -> float | None:
        """Calculate percentage growth rate between two values."""
        if old_value == 0 or old_value is None or new_value is None:
            return None
        return ((new_value - old_value) / old_value) * 100

    def _calculate_cagr(self, beginning_value: float, ending_value: float, years: int) -> float | None:
        """Calculate Compound Annual Growth Rate (CAGR)."""
        if beginning_value <= 0 or ending_value <= 0 or years <= 0:
            return None
        return (math.pow(ending_value / beginning_value, 1 / years) - 1) * 100

    def _add_growth_metrics_to_batch(self, normalized_docs: list[dict[str, Any]]):
        """Add growth metrics to a batch of normalized documents."""
        # Get all symbols in this batch
        symbols = [doc["symbol"] for doc in normalized_docs]

        # Fetch all income statements for these symbols at once
        income_collection = self.db["master_income_statement"]

        # Bulk fetch with optimized query - only fetch needed fields
        cursor = income_collection.find(
            {"symbol": {"$in": symbols}},
            {
                "symbol": 1,
                "fiscal_year": 1,
                "fiscal_period": 1,
                "total_revenue": 1,
                "earnings_per_share_diluted": 1,
                "earnings_per_share_basic": 1,
            },
        ).hint("symbol_1")  # Use symbol index for faster lookup

        # Build optimized lookup structures
        income_data = {}
        for doc in cursor:
            symbol = doc["symbol"]
            if symbol not in income_data:
                income_data[symbol] = {
                    "quarterly": {},  # (year, period) -> doc
                    "annual": {},  # year -> doc
                    "latest_quarterly": None,
                    "latest_annual": None,
                }

            period = doc.get("fiscal_period", "")
            year = doc.get("fiscal_year", 0)

            if period in ["Q1", "Q2", "Q3", "Q4"]:
                # Store quarterly data
                income_data[symbol]["quarterly"][(year, period)] = doc

                # Track latest quarterly
                if not income_data[symbol]["latest_quarterly"] or year > income_data[symbol]["latest_quarterly"].get(
                    "fiscal_year", 0
                ):
                    income_data[symbol]["latest_quarterly"] = doc

            elif period == "FY":
                # Store annual data
                income_data[symbol]["annual"][year] = doc

                # Track latest annual
                if not income_data[symbol]["latest_annual"] or year > income_data[symbol]["latest_annual"].get(
                    "fiscal_year", 0
                ):
                    income_data[symbol]["latest_annual"] = doc

        # Calculate growth metrics for each document
        for normalized_doc in normalized_docs:
            symbol = normalized_doc["symbol"]
            symbol_data = income_data.get(symbol)

            # Initialize metadata
            normalized_doc["growth_metrics_updated_at"] = datetime.now(UTC)
            normalized_doc["latest_quarter_available"] = None
            normalized_doc["latest_annual_available"] = None
            normalized_doc["has_5year_growth_data"] = False

            if not symbol_data:
                continue

            # Process quarterly metrics using optimized lookups
            latest_quarterly = symbol_data["latest_quarterly"]
            if latest_quarterly:
                current_quarter = latest_quarterly["fiscal_period"]
                current_year = latest_quarterly["fiscal_year"]
                normalized_doc["latest_quarter_available"] = f"{current_quarter} {current_year}"

                # Direct lookup for same quarter from previous year
                prior_year_quarter = symbol_data["quarterly"].get((current_year - 1, current_quarter))

                if prior_year_quarter:
                    # Revenue growth
                    normalized_doc["year_over_year_quarterly_revenue_growth"] = self._calculate_growth_rate(
                        prior_year_quarter.get("total_revenue"), latest_quarterly.get("total_revenue")
                    )

                    # EPS growth
                    current_eps = latest_quarterly.get("earnings_per_share_diluted") or latest_quarterly.get(
                        "earnings_per_share_basic"
                    )
                    prior_eps = prior_year_quarter.get("earnings_per_share_diluted") or prior_year_quarter.get(
                        "earnings_per_share_basic"
                    )
                    normalized_doc["year_over_year_quarterly_eps_growth"] = self._calculate_growth_rate(
                        prior_eps, current_eps
                    )

            # Process annual metrics using optimized lookups
            latest_annual = symbol_data["latest_annual"]
            if latest_annual:
                latest_fy_year = latest_annual["fiscal_year"]
                normalized_doc["latest_annual_available"] = f"FY {latest_fy_year}"

                # Direct lookup for prior year annual
                prior_annual = symbol_data["annual"].get(latest_fy_year - 1)

                if prior_annual:
                    # 1-year revenue growth
                    normalized_doc["1year_annual_revenue_growth"] = self._calculate_growth_rate(
                        prior_annual.get("total_revenue"), latest_annual.get("total_revenue")
                    )

                    # 1-year EPS growth
                    current_eps = latest_annual.get("earnings_per_share_diluted") or latest_annual.get(
                        "earnings_per_share_basic"
                    )
                    prior_eps = prior_annual.get("earnings_per_share_diluted") or prior_annual.get(
                        "earnings_per_share_basic"
                    )
                    normalized_doc["1year_annual_EPS_growth"] = self._calculate_growth_rate(prior_eps, current_eps)

                # Direct lookup for 5-year prior annual
                five_year_prior = symbol_data["annual"].get(latest_fy_year - 5)

                if five_year_prior:
                    # 5-year revenue CAGR
                    normalized_doc["5year_annual_total_revenue_growth"] = self._calculate_cagr(
                        five_year_prior.get("total_revenue"), latest_annual.get("total_revenue"), 5
                    )

                    # 5-year EPS CAGR
                    beginning_eps = five_year_prior.get("earnings_per_share_diluted") or five_year_prior.get(
                        "earnings_per_share_basic"
                    )
                    ending_eps = latest_annual.get("earnings_per_share_diluted") or latest_annual.get(
                        "earnings_per_share_basic"
                    )
                    normalized_doc["5year_annual_total_EPS_growth"] = self._calculate_cagr(beginning_eps, ending_eps, 5)

                normalized_doc["has_5year_growth_data"] = five_year_prior is not None

    def close(self):
        """Close database connection."""
        self.client.close()


async def main():
    """Main function to run the normalization process."""
    import sys

    # Check for test flag
    test_mode = "--test" in sys.argv
    max_symbols = 1000 if test_mode else None

    normalizer = CollectionNormalizer()

    try:
        if test_mode:
            logger.info(f"TEST MODE: Processing only first {max_symbols} symbols")
        else:
            logger.info("FULL RUN: Processing entire database")

        # Run normalization with optimized batch size
        batch_size = 500 if not test_mode else 100
        await normalizer.normalize_all_collections(batch_size=batch_size, max_symbols=max_symbols)

        # Verify results
        stats = await normalizer.verify_normalization()

        print(f"\n{'=' * 50}")
        print("NORMALIZATION SUMMARY")
        print(f"{'=' * 50}")
        print(f"Total documents created: {stats['total_documents']}")
        print(f"Collections represented: {stats['collections_represented']}")
        print("\nField coverage:")
        for field, count in stats["field_coverage"].items():
            print(f"  {field}: {count} documents")

        print("\nSample document structure:")
        if stats["sample_document"]:
            for key in stats["sample_document"]:
                print(f"  {key}: {type(stats['sample_document'][key]).__name__}")

    except Exception as e:
        logger.error(f"Normalization failed: {e}")
        raise
    finally:
        normalizer.close()


if __name__ == "__main__":
    asyncio.run(main())
