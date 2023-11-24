from pydantic import BaseModel, EmailStr, Field
from typing import List
from datetime import datetime

class MongoEmail(BaseModel):
    id:str = Field(..., description="ID of the email(from Message-ID header)")
    subject: str = Field(..., description="Subject of the email")
    sender: EmailStr = Field(..., description="Email address of the sender")
    recipients: str = Field(..., description="List of email addresses of the recipients")
    timestamp: str = Field(..., description="Timestamp of when the email was sent")
    body: str = Field(..., description="Content of the email")

class MongoShip(BaseModel):
    name: str = Field(..., description="Name of the ship")
    capacity: str = Field(..., description="Capacity of the ship")
    commission: float = Field(..., description="Commission percentage")
    email: MongoEmail = Field(..., description="Email object")

class MongoCargo(BaseModel):
    name: str = Field(..., description="Name of the cargo")
    quantity: str = Field(..., description="Quantity of the cargo")
    commission: float = Field(..., description="Commission percentage")
    email: MongoEmail = Field(..., description="Email object")