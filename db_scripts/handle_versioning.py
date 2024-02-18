

# Go over all entities (ships and cargos) and check if there are any duplicates. If there are, handle the versioning or something.


#entity.versions = []

# types of versions: exact, similar (i.e different location)

#exact match means
# entity fetched from the same email: sender.
#  name
# - status
# - month
# - capacity
# - location? -> can change since ships can move ? prioritize more recent? ENSURE is the same object, type shit ?
# - capacity_int
# - month_int (can change?)


# case 1 - all fields identical + same sender
# case 2 - all fields identical + different sender (i guess still should merge as the same object ?)


# function to reversion the object, i.e look at all versions and bubble up the main object (i.e based on recency + comission ?)

from setup import db_client
import asyncio

async def handle_versioning():
    # Fetch all documents from the collection
    cargo_collection = db_client["cargos"]
    cursor = cargo_collection.find({})

    # Iterate through the documents
    async for cargo in cursor:

        result = await cargo_collection.replace_one({"_id": cargo["_id"]}, cargo)

        # Check the result of the update operation if needed
        if result.modified_count > 0:
            print("Cargo entry updated successfully")
        else:
            print("No cargo entry updated")
    
    ship_collection = db_client["ships"]
    cursor = ship_collection.find({})

    async for ship in cursor:
        
        result = await ship_collection.replace_one({"_id": ship["_id"]}, ship)

        # Check the result of the update operation if needed
        if result.modified_count > 0:
            print("Ship entry updated successfully")
        else:
            print("No ship entry updated")

if __name__ == "__main__":
    asyncio.run(handle_versioning())