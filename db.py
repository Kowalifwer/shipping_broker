from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import re
from embeddings.models import geoloc_model, general_model
import numpy as np

#re.compile(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*mts?\b", re.IGNORECASE) # for matching numbers with commas and decimals, followed by "mt" or "mts"

def extract_number(s: str) -> Optional[int]:
    # Remove commas from the text
    text = s.replace(',', '')

    # Define a regular expression pattern to find integer values
    pattern = r'\b(\d+)\b'

    # Find the first match in the text
    match = re.search(pattern, text)

    # Extract the integer value
    if match:
        value = int(match.group(1))
    else:
        # Handle the case where no match is found (optional)
        value = None

    return value

def extract_weights(s: str) -> Optional[Tuple[int, int]]:
    # Define a regular expression pattern to find integer values with various separators
    text = s.replace(",","")
    pattern = r'\b(\d+)'

    # Find all matches in the text
    matches = re.findall(pattern, text)

    # Extract the integer values
    if not matches:
        return None

    if len(matches) == 1: # Will return the same value for both upper and lower
        return (int(matches[0]), int(matches[0]))
    
    if len(matches) > 1:
        return (int(matches[0]), int(matches[1]))
    
    return None

months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]

def extract_month(s: str) -> Optional[int]:
    for i, month in enumerate(months, start=1):
        if month.lower() in s.lower():
            return i

    return None

class MongoEmail(BaseModel):
    id: Optional[str] # ID of the email(from Message-ID header)
    subject: Optional[str] # Subject of the email
    sender: Optional[str] # Email address of the sender
    recipients: Optional[str] # List of email addresses of the recipients
    date_received: Optional[str] # Timestamp of when the email was received
    body: Optional[str] # Content of the email

    timestamp_added_to_db: Optional[datetime] = None # Timestamp of when the email read from the inbox and ADDED to the database.

    timestamp_entities_extracted: Optional[datetime] = None # Timestamp of when the entities were extracted from the email

    # Extra fields to be populated by the email processing pipeline
    extracted_ship_ids: Optional[List[str]] = Field(default_factory=list) # List of ship IDs extracted from the email
    extracted_cargo_ids: Optional[List[str]] = Field(default_factory=list) # List of cargo IDs extracted from the email

def update_ship_entry_with_calculated_fields(existing_values: Dict):
    """Modifies existing ship object in place, adding calculated fields and embeddings."""
    capacity = extract_number(existing_values.get("capacity", ""))
    # check if capacity is less than 3 digits, then multiply by 1000
    if capacity and capacity < 1000:
        capacity = capacity * 1000

    # If capacity is not specified, pass an empty string to extract_number, which will return None
    existing_values["capacity_int"] = capacity
    existing_values["month_int"] = extract_month(existing_values.get("month", ""))

    create_embeddings_for_ship(existing_values)

def create_embeddings_for_ship(existing_values: Dict):
    """Modifies existing ship object in place, adding embeddings for sea, port, and general information."""

    # Handle sea embedding
    sea = existing_values.get("sea", "")
    sea_embeddings = np.random.rand(384)

    if sea:
        sea_embeddings = geoloc_model.encode([sea], convert_to_numpy=True)[0]
    
    existing_values["sea_embedding"] = sea_embeddings.tolist()

    # Handle port embedding
    port = existing_values.get("port", "")
    port_embeddings = np.random.rand(384)

    if port:
        port_embeddings = geoloc_model.encode([port], convert_to_numpy=True)[0]
    
    existing_values["port_embedding"] = port_embeddings.tolist()

    # Handle general embedding
    general = existing_values.get("keyword_data", "")
    if general:
        existing_values["general_embedding"] = general_model.encode([general], convert_to_numpy=True)[0].tolist()
    else:
        existing_values["general_embedding"] = np.random.rand(384).tolist()

class MongoShip(BaseModel):
    # Fields to extract from email
    id: Optional[Any] = Field(alias="_id", default=None) # ID of the ship generated by MongoDB

    name: Optional[str] # Name of the ship
    status: Optional[str] # Status of the ship (e.g., open, on subs, fixed, spot, etc.)
    port: Optional[str] # Port where the ship is currently located
    sea: Optional[str] # Sea where the ship is currently located
    month: Optional[str] # Month when the ship is available for cargoes
    capacity: Optional[str] # Capacity of the ship
    keyword_data: Optional[str] = "" # All important keywords across all the fields, to be tokenized and embedded for similarity matching

    # Fields to fill on creation
    email: MongoEmail # Email object
    timestamp_created: datetime = Field(default_factory=datetime.now) # Timestamp of when the ship was created

    # Fields to calculate on creation (to be used for simple queries)
    capacity_int: Optional[int] # Capacity of the ship in integer form
    month_int: Optional[int] # Month when the ship is available for cargoes in integer form

    # Embeddings to calculate on creation (to be used for similarity queries)
    sea_embedding: Optional[List[float]] # Embedding of the sea where the ship is currently located
    port_embedding: Optional[List[float]] # Embedding of the port where the ship is currently located

    general_embedding: Optional[List[float]] # Embedding of the ship's general information

    # Extra fields
    pairs_with: Optional[List[str]] = [] # List of cargo IDs that this ship is paired with
    timestamp_pairs_updated: Optional[datetime] = None # Timestamp of when the pairs_with field was last updated

    class Config:
        extra = 'allow'

def update_cargo_entry_with_calculated_fields(existing_values: Dict):
    """Modifies existing cargo object in place, adding calculated fields and vector embeddings."""

    min_max_weights = extract_weights(existing_values.get("quantity", ""))
    if min_max_weights:
        existing_values["quantity_min_int"] = min_max_weights[0] if min_max_weights[0] >= 1000 else min_max_weights[0] * 1000
        existing_values["quantity_max_int"] = min_max_weights[1] if min_max_weights[1] >= 1000 else min_max_weights[1] * 1000
    else:
        existing_values["quantity_min_int"] = None
        existing_values["quantity_max_int"] = None

    # If capacity is not specified, pass an empty string to extract_number, which will return None
    existing_values["month_int"] = extract_month(existing_values.get("month", ""))

    # handle commission calculation
    comission = 10.0 # set to high number default
    match = re.search(r'\b(\d+(?:\.\d+)?)\b', existing_values.get("commission", ""))
    if match:
        comission = float(match.group(0))

    existing_values["commission_float"] = comission

    create_embeddings_for_cargo(existing_values)

def create_embeddings_for_cargo(existing_values: Dict):
    """Modifies existing cargo objects in place, adding embeddings for sea, port, and general information."""
    # Handle sea embedding
    sea_from = existing_values.get("sea_from", "")
    sea_to = existing_values.get("sea_to", "")
    sea_from_embeddings = np.random.rand(384)
    sea_to_embeddings = np.random.rand(384)

    if sea_from:
        sea_from_embeddings = geoloc_model.encode([sea_from], convert_to_numpy=True)[0]
    if sea_to:
        sea_to_embeddings = geoloc_model.encode([sea_to], convert_to_numpy=True)[0]

    # Give more weight to the SEA FROM embedding, since that is where the cargo is currently located.
    existing_values["sea_embedding"] = (sea_from_embeddings * 0.67 + sea_to_embeddings * 0.33).tolist()

    # Handle port embedding
    port_from = existing_values.get("port_from", "")
    port_to = existing_values.get("port_to", "")
    port_from_embeddings = np.random.rand(384)
    port_to_embeddings = np.random.rand(384)

    if port_from:
        port_from_embeddings = geoloc_model.encode([port_from], convert_to_numpy=True)[0]
    if port_to:
        port_to_embeddings = geoloc_model.encode([port_to], convert_to_numpy=True)[0]
    
    # Give more weight to the PORT FROM embedding, since that is where the cargo is currently located.
    existing_values["port_embedding"] = (port_from_embeddings * 0.67 + port_to_embeddings * 0.33).tolist()

    # Handle general embedding
    general = existing_values.get("keyword_data", "")
    if general:
        existing_values["general_embedding"] = general_model.encode([general], convert_to_numpy=True)[0].tolist()
    else:
        existing_values["general_embedding"] = np.random.rand(384).tolist()


class MongoCargo(BaseModel):
    id: Optional[Any] = Field(alias="_id", default=None) # ID of the cargo generated by MongoDB

    # Fields to extract from email
    name: Optional[str] # Name of the cargo
    quantity: Optional[str] # Quantity of the cargo
    port_from: Optional[str] # Port of loading
    port_to: Optional[str] # Port of discharge
    sea_from: Optional[str] # Sea of loading
    sea_to: Optional[str] # Sea of discharge
    month: Optional[str] # Month of shipment
    commission: Optional[str] # Commission percentage (e.g., 2.5%)
    keyword_data: Optional[str] = "" # All important keywords across all the fields, to be tokenized and embedded for similarity matching

    # Fields to fill on creation
    email: MongoEmail # Email object
    timestamp_created: datetime = Field(default_factory=datetime.now) # Timestamp of when the cargo was created

    # Fields to calculate on creation (to be used for simple queries)
    quantity_min_int: Optional[int] # Capacity of the cargo lower bound in integer form
    quantity_max_int: Optional[int] # Capacity of the cargo upper bound in integer form

    month_int: Optional[int] # Month when the ship is available for cargoes in integer form
    commission_float: Optional[float] # Commission percentage in float form

    # Embeddings to calculate on creation (to be used for similarity queries)
    sea_embedding: Optional[List[float]] # Embedding of the sea where the cargo is currently located
    port_embedding: Optional[List[float]] # Embedding of the port where the cargo is currently located

    general_embedding: Optional[List[float]] # Embedding of the cargo's general information

    # Extra fields
    pairs_with: Optional[List[Any]] = Field(default_factory=list) # List of ship IDs that this cargo is paired with

    class Config:
        extra = 'allow'

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