from geopy.geocoders import Nominatim, GoogleV3
from geopy import distance
from geopy.adapters import AioHTTPAdapter
from setup import config, db_client
import asyncio

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

async def geocode_location(location: str) -> tuple | None:
    """Converts a location string to a tuple of latitude and longitude"""

    result = None

    # Check if location is already in the database
    known_location = await known_locations.find_one({"location": location})

    if known_location:
        print("Location found in database")
        return known_location["latitude"], known_location["longitude"]
    else:
        print("Location not found in database")


    # Fallback to geocoding using the Google Maps API
    async with init_async_geolocator_google() as geolocator_google:
        result = await geolocator_google.geocode(query = location) # type: ignore
        if result:
            print("Location found using Google Maps API")
            # Save location to database
            await known_locations.insert_one({
                "location": location,
                "latitude": result.latitude,
                "longitude": result.longitude
            })
            print(result.raw)
            return result.latitude, result.longitude
    
    return result

async def main():
    loc1 = await geocode_location("Venezuela serpent edge")
    loc2 = await geocode_location("ravenna")

    # get distance in km between Odessa and Nemrut
    dist = distance.distance(loc1, loc2).km
    print(dist)

if __name__ == "__main__":
    asyncio.run(main())