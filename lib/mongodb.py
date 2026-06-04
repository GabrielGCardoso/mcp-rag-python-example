from pymongo import MongoClient
from pymongo.collection import Collection

from lib.config import COLLECTION_NAME, DB_NAME, MONGODB_URI

_client: MongoClient | None = None


def get_collection() -> Collection:
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI)
    return _client[DB_NAME][COLLECTION_NAME]
