"""Conexión centralizada a MongoDB."""
import os
from motor.motor_asyncio import AsyncIOMotorClient

client: AsyncIOMotorClient = None
db = None


def get_db():
    return db


def init_db():
    global client, db
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    return db


def close_db():
    if client:
        client.close()
