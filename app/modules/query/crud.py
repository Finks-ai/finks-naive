from typing import List, Dict, Any, Optional
from pymongo.collection import Collection
from pymongo import ASCENDING, DESCENDING
from loguru import logger
from app.core.database import DatabaseService
from .models import CompanyResult

class QueryCRUD:
    """CRUD operations for querying the master_search collection."""
    
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
        self.collection = db_service.get_master_search_collection()
    
    async def execute_query(
        self, 
        mongo_query: Dict[str, Any], 
        limit: int = 50,
        sort_field: Optional[str] = None,
        sort_direction: int = ASCENDING
    ) -> List[CompanyResult]:
        """
        Execute MongoDB query against master_search collection.
        
        Args:
            mongo_query: MongoDB query dictionary
            limit: Maximum number of results
            sort_field: Field to sort by (optional)
            sort_direction: Sort direction (ASCENDING or DESCENDING)
            
        Returns:
            List of CompanyResult objects
        """
        try:
            logger.info(f"Executing query: {mongo_query}")
            
            # Build query cursor
            cursor = self.collection.find(mongo_query)
            
            # Apply sorting if specified
            if sort_field:
                cursor = cursor.sort(sort_field, sort_direction)
            
            # Apply limit
            cursor = cursor.limit(limit)
            
            # Convert results to CompanyResult objects
            results = []
            for doc in cursor:
                # Remove MongoDB's _id field
                doc.pop('_id', None)
                
                # Extract core fields
                core_fields = {
                    'symbol': doc.get('symbol'),
                    'company_name': doc.get('company_name'),
                    'sector': doc.get('sector'),
                    'market_cap': doc.get('market_cap'),
                    'pe_ratio': doc.get('pe_ratio'),
                    'revenue_growth': doc.get('revenue_growth'),
                }
                
                # Put remaining fields in additional_fields
                additional_fields = {
                    k: v for k, v in doc.items() 
                    if k not in core_fields and k not in ['source_collections', 'last_updated']
                }
                
                result = CompanyResult(
                    **core_fields,
                    additional_fields=additional_fields
                )
                results.append(result)
            
            logger.info(f"Query returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise
    
    async def get_available_fields(self) -> List[str]:
        """
        Get list of available fields in the master_search collection.
        
        Returns:
            List of field names
        """
        try:
            # Get a sample document to see available fields
            sample_doc = self.collection.find_one()
            if sample_doc:
                # Exclude metadata fields
                excluded_fields = {'_id', 'symbol', 'source_collections', 'last_updated'}
                fields = [field for field in sample_doc.keys() if field not in excluded_fields]
                return sorted(fields)
            else:
                logger.warning("No documents found in master_search collection")
                return []
        except Exception as e:
            logger.error(f"Error getting available fields: {e}")
            raise
    
    async def get_field_stats(self, field_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific field.
        
        Args:
            field_name: Name of the field to analyze
            
        Returns:
            Dictionary with field statistics
        """
        try:
            pipeline = [
                {"$match": {field_name: {"$exists": True, "$ne": None}}},
                {"$group": {
                    "_id": None,
                    "count": {"$sum": 1},
                    "min": {"$min": f"${field_name}"},
                    "max": {"$max": f"${field_name}"},
                    "avg": {"$avg": f"${field_name}"}
                }}
            ]
            
            result = list(self.collection.aggregate(pipeline))
            if result:
                stats = result[0]
                stats.pop('_id', None)
                return stats
            else:
                return {"count": 0}
                
        except Exception as e:
            logger.error(f"Error getting field stats for {field_name}: {e}")
            return {"count": 0, "error": str(e)}
    
    async def count_documents(self, mongo_query: Dict[str, Any]) -> int:
        """
        Count documents matching the query.
        
        Args:
            mongo_query: MongoDB query dictionary
            
        Returns:
            Number of matching documents
        """
        try:
            count = self.collection.count_documents(mongo_query)
            logger.info(f"Query matches {count} documents")
            return count
        except Exception as e:
            logger.error(f"Error counting documents: {e}")
            raise