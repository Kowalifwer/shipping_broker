from pydantic import BaseModel, EmailStr, Field
from typing import List
from datetime import datetime

class MongoEmail(BaseModel):
    id:str = Field(..., description="ID of the email(from Message-ID header)")
    subject: str = Field(..., description="Subject of the email")
    sender: EmailStr = Field(..., description="Email address of the sender")
    recipients: str = Field(..., description="List of email addresses of the recipients")
    date_received: str = Field(..., description="Timestamp of when the email was received")
    timestamp_processed: datetime = Field(..., description="Timestamp of when the email was processed")
    body: str = Field(..., description="Content of the email")

class MongoShip(BaseModel):
    name: str = Field(..., description="Name of the ship")
    capacity: str = Field(..., description="Capacity of the ship")
    email: MongoEmail = Field(..., description="Email object")
    timestamp_created: datetime = Field(..., description="Timestamp of when the ship was created")

class MongoCargo(BaseModel):
    name: str = Field(..., description="Name of the cargo")
    quantity: str = Field(..., description="Quantity of the cargo")
    commission: str = Field(..., description="Commission percentage (e.g., 2.5%)")
    email: MongoEmail = Field(..., description="Email object")
    timestamp_created: datetime = Field(..., description="Timestamp of when the cargo was created")