from geopy.geocoders import Nominatim
import asyncio

async def location_to_lat_lng(location) -> tuple:
    """Converts a location string to a tuple of latitude and longitude."""

    geolocator = Nominatim(user_agent="shipping-broker")
    location = geolocator.geocode(location)
    return (location.latitude, location.longitude)

async def lat_lng_to_location(lat, lng) -> str:
    """Converts a tuple of latitude and longitude to a location string."""

    geolocator = Nominatim(user_agent="shipping-broker")
    location = geolocator.reverse(f"{lat}, {lng}")
    return location.address

async def main():
    print(await location_to_lat_lng("Odessa"))
    print(await location_to_lat_lng("Nemrut"))

    print(await lat_lng_to_location(46.482526, 30.723309))
    print(await lat_lng_to_location(37.266666, 27.25))

if __name__ == "__main__":
    asyncio.run(main())