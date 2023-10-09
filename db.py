from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from bson import ObjectId

class Item(BaseModel):
    name: str
    description: str

client = AsyncIOMotorClient("mongodb://localhost:27017/")
db = client["mydatabase"]
collection = db["items"]