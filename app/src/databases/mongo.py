from pymongo import MongoClient
from pymongo.collection import Collection
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_client = None
_db = None


def get_db():
    global _client, _db
    if _client is None:
        _client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=10000)
        _db = _client[settings.mongo_db]
    return _db


def connect():
    db = get_db()
    db.command("ping")
    logger.info("MongoDB connection verified")


def get_collection(name: str) -> Collection:
    return get_db()[name]


def close():
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed")
