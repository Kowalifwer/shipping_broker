# from shipping_broker.setup import db_client
from setup import db_client
import asyncio

async def gather_extracted_entities():
    # Fetch all documents from the collection
    email_collection = db_client["emails"]
    cargo_collection = db_client["cargos"]
    ship_collection = db_client["ships"]

    extractions_collection = db_client["extractions"]

    # go over all emails:
    # Check if the email_id existings in extractions already (has been matched before). If so - skip

    # For each email, query all cargos where email_id = email["_id"] and all ships where email_id = email["_id"]
    # Add the results to a new document in the extractions collection
    cursor = email_collection.find({})
    n_skipped = 0
    n_added = 0

    async for email in cursor:
        # Query extrction_collection to see if there is an email_id match
        # If there is a match, skip this email

        if await extractions_collection.find_one({"email.id": email["id"]}):
            n_skipped += 1
            continue

        cargo_cursor = cargo_collection.find({"email.id": email["id"]})
        ship_cursor = ship_collection.find({"email.id": email["id"]})

        cargos_and_ships = []

        async for cargo in cargo_cursor:
            cargo["type"] = "cargo"
            cargos_and_ships.append(cargo)
        
        async for ship in ship_cursor:
            ship["type"] = "ship"
            cargos_and_ships.append(ship)
        
        # Add the results to a new document in the extractions collection
        await extractions_collection.insert_one({"email": email, "entities": cargos_and_ships})
        n_added += 1
    
    print(f"Added {n_added} new extractions, skipped {n_skipped} emails that were already extracted")

if __name__ == "__main__":
    asyncio.run(gather_extracted_entities())