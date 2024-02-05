from setup import db_client
from db import update_cargo_entry_with_calculated_fields, update_ship_entry_with_calculated_fields
import asyncio

async def add_or_update_embeddings():
    # Fetch all documents from the collection
    cargo_collection = db_client["cargos"]
    cursor = cargo_collection.find({})

    # Iterate through the documents
    async for cargo in cursor:
        update_cargo_entry_with_calculated_fields(cargo)
        # Replace the existing cargo entry in the database
        result = await cargo_collection.replace_one({"_id": cargo["_id"]}, cargo)

        # Check the result of the update operation if needed
        if result.modified_count > 0:
            print("Cargo entry updated successfully")
        else:
            print("No cargo entry updated")
    
    ship_collection = db_client["ships"]
    cursor = ship_collection.find({})

    async for ship in cursor:
        update_ship_entry_with_calculated_fields(ship)
        # Replace the existing ship entry in the database
        result = await ship_collection.replace_one({"_id": ship["_id"]}, ship)

        # Check the result of the update operation if needed
        if result.modified_count > 0:
            print("Ship entry updated successfully")
        else:
            print("No ship entry updated")

if __name__ == "__main__":
    asyncio.run(add_or_update_embeddings())