from pydantic import BaseModel, EmailStr, Field, Extra
from typing import List, Optional
from datetime import datetime

class MongoEmail(BaseModel):
    id: Optional[str] # ID of the email(from Message-ID header)
    subject: Optional[str] # Subject of the email
    sender: Optional[EmailStr] # Email address of the sender
    recipients: Optional[str] # List of email addresses of the recipients
    date_received: Optional[str] # Timestamp of when the email was received
    body: Optional[str] # Content of the email

    timestamp_processed: Optional[datetime] # Timestamp of when the email was processed

class MongoShip(BaseModel):
    # Fields to extract from email
    name: Optional[str] # Name of the ship
    status: Optional[str] # Status of the ship (e.g., open, on subs, fixed, spot, etc.)
    port: Optional[str] # Port where the ship is currently located
    sea: Optional[str] # Sea where the ship is currently located
    month: Optional[str] # Month when the ship is available for cargoes
    capacity: Optional[str] # Capacity of the ship

    # Fields to fill on creation
    email: MongoEmail # Email object
    timestamp_created: Optional[datetime] = datetime.now() # Timestamp of when the ship was created

    # Extra fields
    pairs_with: Optional[List[str]] = [] # List of cargo IDs that this ship is paired with

    class Config:
        extra = Extra.allow

class MongoCargo(BaseModel):
    # Fields to extract from email
    name: Optional[str] # Name of the cargo
    quantity: Optional[str] # Quantity of the cargo
    port_from: Optional[str] # Port of loading
    port_to: Optional[str] # Port of discharge
    sea_from: Optional[str] # Sea of loading
    sea_to: Optional[str] # Sea of discharge
    month: Optional[str] # Month of shipment
    commission: Optional[str] # Commission percentage (e.g., 2.5%)

    # Fields to fill on creation
    email: MongoEmail # Email object
    timestamp_created: Optional[datetime] = datetime.now() # Timestamp of when the cargo was created

    # Extra fields
    pairs_with: Optional[List[str]] = [] # List of ship IDs that this cargo is paired with

    class Config:
        extra = Extra.allow

class MongoCargoShipPair(BaseModel):
    cargo_id: str # ID of the Cargo object
    ship_id: str # ID of the Ship object

    datetime_created: Optional[datetime] = datetime.now() # Timestamp of when the pair was created
    score: Optional[float] # Score of the pair

# Setup 1
#1. Go over all ships with no cargo pairs, i.e find all ships with ship_id not in any CargoShipPair.ship_id
#2. For each ship, find all cargoes that match the ship's criteria
#3. Score each pair of ship and cargo
#4. Sort all pairs by score

# Setup 2
#1. for Ship object, store a list of matched_cargo_ids
#2. for Cargo object, store a list of matched_ship_ids

# so, we will go over all ship objects, and find all cargoes that match the ship's criteria-