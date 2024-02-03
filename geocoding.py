from geopy.geocoders import Nominatim, GoogleV3
from geopy import distance
from geopy.adapters import AioHTTPAdapter
from setup import config, db_client
import asyncio
from db import GeocodedLocation, GeoJsonLocation, LocationForGeocoding
import copy

geolocator = Nominatim(user_agent="shipping_broker")

known_locations = db_client["known_locations"]

def init_async_geolocator_google():
    """
    Initializes an async geolocator using the Google Maps API.
    
    Example use: async with init_async_geolocator_google() as geolocator_google:
    """
    return GoogleV3(
        api_key=config['google']['api_key'],
        adapter_factory=AioHTTPAdapter
    )

async def geocode_location_with_retry(location: LocationForGeocoding) -> GeocodedLocation | None:
    # 1. Try geocode the PORT first. If it fails, try the SEA. If that fails, try the OCEAN.
    # 2. If all fails, return None.
    result = None

    if location.port:
        result = await geocode_location(location.port)
        if result:
            print("Location found using port.")
            return result
        else:
            print("Location NOT found using port.")
    
    if location.sea:
        result = await geocode_location(location.sea)
        if result:
            print("Location found using sea.")

            # Idea is, if port exists but cannot be geocoded - we should still cache this location to the database, pointing to the same location as the sea.
            if location.port:
                print("Cache update for PORT, to point at the same location as SEA.")
                # make copy of result and update the name to the port
                dummy_location = copy.deepcopy(result)
                dummy_location.name = location.port

                await add_location_to_db(dummy_location)

            
            return result
    
    if location.ocean:
        result = await geocode_location(location.ocean)
        if result:
            print("Location found using ocean.")
            return result
    
    return result

async def add_location_to_db(location: GeocodedLocation):
    await known_locations.insert_one(location.model_dump())

async def geocode_location(location: str) -> GeocodedLocation | None:
    """Converts a location string to a tuple of latitude and longitude"""

    result = None

    # Check if location is already in the database
    known_location = await known_locations.find_one({"name": location})

    if known_location:
        print("Location found in database")
        return GeocodedLocation(**known_location)
    else:
        print("Location not found in database")

    # Fallback to geocoding using the Google Maps API
    async with init_async_geolocator_google() as geolocator_google:
        response = await geolocator_google.geocode(query = location) # type: ignore
        if response:
            print("Location found using Google Maps API")
            result = GeocodedLocation(
                name=location,
                location=GeoJsonLocation(
                    type="Point",
                    coordinates=[response.longitude, response.latitude]
                ),
                address=response.address,
                raw=response.raw
            )

            await add_location_to_db(result)

            return result

    return result

async def main():
    loc1 = await geocode_location_with_retry(LocationForGeocoding(
        port="ECSA",
        sea="East Coast South America",
        ocean=""
    ))

if __name__ == "__main__":
    asyncio.run(main())