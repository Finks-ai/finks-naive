import pymongo
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from typing import Optional
from loguru import logger
from .config import get_settings

class DatabaseService:
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None
    
    def get_client(self) -> MongoClient:
        """Get MongoDB client connection."""
        if self._client is None or not self._is_client_valid():
            try:
                # Close any existing invalid connection
                if self._client:
                    try:
                        self._client.close()
                    except:
                        pass
                
                # Create new connection
                self._client = MongoClient(self.settings.MONGODB_URL)
                # Test connection
                self._client.admin.command('ping')
                logger.info("Successfully connected to MongoDB")
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                raise
        return self._client
    
    def _is_client_valid(self) -> bool:
        """Check if the current client connection is valid."""
        if not self._client:
            return False
        try:
            # Try to ping the database
            self._client.admin.command('ping')
            return True
        except:
            return False
    
    def get_database(self) -> Database:
        """Get MongoDB database."""
        if self._db is None:
            client = self.get_client()
            self._db = client[self.settings.MONGODB_DB_NAME]
        return self._db
    
    def get_collection(self, collection_name: str) -> Collection:
        """Get MongoDB collection."""
        db = self.get_database()
        return db[collection_name]
    
    def get_master_search_collection(self) -> Collection:
        """Get the master_search collection specifically."""
        return self.get_collection("master_search")
    
    def close(self):
        """Close database connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            logger.info("Database connection closed")

# Global database service instance
_db_service: Optional[DatabaseService] = None

def get_db_service() -> DatabaseService:
    """Get global database service instance."""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service