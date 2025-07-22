#!/usr/bin/env python3
"""
Normalize all fields from different collections into a single master_search collection.
This script aggregates all fields for each symbol into one document for efficient querying.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import os
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CollectionNormalizer:
    def __init__(self):
        self.client = MongoClient(os.getenv("MONGODB_URL"))
        self.db = self.client[os.getenv("MONGODB_DB_NAME")]
        self.master_search = self.db["master_search"]
        
    def get_field_to_collection_mapping(self) -> Dict[str, str]:
        """
        Load field to collection mapping from configuration file.
        """
        import yaml
        
        try:
            config_path = os.path.join(os.path.dirname(__file__), "..", "config", "field_mappings.yaml")
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config["field_mappings"]
        except FileNotFoundError:
            logger.error("Field mappings configuration file not found!")
            # Fallback to basic mappings
            return {
                "company_name": "master_profiles",
                "sector": "master_profiles", 
                "market_cap": "master_profiles",
                "pe_ratio": "ratios",
                "revenue_growth": "financials",
            }
    
    async def get_all_symbols(self) -> List[str]:
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
    
    async def normalize_batch_data(self, symbols: List[str]) -> List[Dict[str, Any]]:
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
                # Bulk query: get all documents for all symbols at once
                cursor = collection.find({"symbol": {"$in": symbols}})
                collection_data[collection_name] = {doc["symbol"]: doc for doc in cursor}
            
            # Build normalized documents
            normalized_docs = []
            for symbol in symbols:
                normalized_doc = {
                    "symbol": symbol,
                    "last_updated": None,
                    "source_collections": []
                }
                
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
                        if "updated_at" in doc:
                            if not normalized_doc["last_updated"] or doc["updated_at"] > normalized_doc["last_updated"]:
                                normalized_doc["last_updated"] = doc["updated_at"]
                
                if len(normalized_doc["source_collections"]) > 0:
                    normalized_docs.append(normalized_doc)
            
            return normalized_docs
            
        except Exception as e:
            logger.error(f"Error normalizing batch data: {e}")
            return []
    
    async def normalize_all_collections(self, batch_size: int = 1000):
        """Normalize all collections into master_search."""
        logger.info("Starting collection normalization...")
        
        # Clear existing master_search collection
        logger.info("Clearing existing master_search collection...")
        self.master_search.delete_many({})
        
        # Get all symbols
        symbols = await self.get_all_symbols()
        
        # Process symbols in batches with progress bar
        total_processed = 0
        total_inserted = 0
        
        with tqdm(total=len(symbols), desc="Processing symbols", unit="symbol") as pbar:
            for i in range(0, len(symbols), batch_size):
                batch_symbols = symbols[i:i + batch_size]
                
                # Process entire batch at once with bulk queries
                batch_docs = await self.normalize_batch_data(batch_symbols)
                total_processed += len(batch_symbols)
                pbar.update(len(batch_symbols))
                
                # Insert batch
                if batch_docs:
                    try:
                        self.master_search.insert_many(batch_docs)
                        total_inserted += len(batch_docs)
                        pbar.set_postfix(inserted=total_inserted, batch=i//batch_size + 1)
                    except PyMongoError as e:
                        logger.error(f"Error inserting batch: {e}")
                        pbar.set_postfix(error=f"Batch {i//batch_size + 1} failed")
                else:
                    pbar.set_postfix(inserted=total_inserted, batch=i//batch_size + 1, no_data=True)
        
        logger.info(f"Normalization complete! Processed {total_processed} symbols, inserted {total_inserted} documents")
        
        # Create index on symbol field
        logger.info("Creating index on symbol field...")
        self.master_search.create_index("symbol", unique=True)
        
        return total_inserted
    
    async def verify_normalization(self) -> Dict[str, Any]:
        """Verify the normalization results."""
        logger.info("Verifying normalization results...")
        
        stats = {
            "total_documents": self.master_search.count_documents({}),
            "sample_document": self.master_search.find_one(),
            "collections_represented": self.master_search.distinct("source_collections"),
            "field_coverage": {}
        }
        
        # Check field coverage
        field_mapping = self.get_field_to_collection_mapping()
        for field in field_mapping.keys():
            count = self.master_search.count_documents({field: {"$exists": True}})
            stats["field_coverage"][field] = count
        
        logger.info(f"Verification complete: {stats['total_documents']} documents in master_search")
        return stats
    
    def close(self):
        """Close database connection."""
        self.client.close()

async def main():
    """Main function to run the normalization process."""
    normalizer = CollectionNormalizer()
    
    try:
        # Run normalization with optimized batch size for better performance
        total_inserted = await normalizer.normalize_all_collections(batch_size=10000)
        
        # Verify results
        stats = await normalizer.verify_normalization()
        
        print(f"\n{'='*50}")
        print("NORMALIZATION SUMMARY")
        print(f"{'='*50}")
        print(f"Total documents created: {stats['total_documents']}")
        print(f"Collections represented: {stats['collections_represented']}")
        print(f"\nField coverage:")
        for field, count in stats["field_coverage"].items():
            print(f"  {field}: {count} documents")
        
        print(f"\nSample document structure:")
        if stats["sample_document"]:
            for key in stats["sample_document"].keys():
                print(f"  {key}: {type(stats['sample_document'][key]).__name__}")
        
    except Exception as e:
        logger.error(f"Normalization failed: {e}")
        raise
    finally:
        normalizer.close()

if __name__ == "__main__":
    asyncio.run(main())