import os
import logging
from typing import List, Dict, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)

async def autocomplete_address(query: str) -> List[Dict]:
    """
    Return address suggestions using Google Places API
    """
    try:
        import googlemaps
        
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Google Maps API key not configured")
        
        gmaps = googlemaps.Client(key=api_key)
        
        # Use Places API autocomplete
        places_result = gmaps.places_autocomplete(
            input_text=query,
            types='establishment|geocode',
            language='en'
        )
        
        suggestions = []
        for place in places_result[:5]:  # Limit to 5 suggestions
            suggestions.append({
                "place_id": place.get("place_id"),
                "description": place.get("description"),
                "formatted_address": place.get("description"),
                "types": place.get("types", [])
            })
        
        return suggestions
        
    except ImportError:
        logger.warning("Google Maps client not installed")
        raise HTTPException(status_code=500, detail="Google Maps service not configured")
    except Exception as e:
        logger.error(f"Address autocomplete failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Address autocomplete failed: {str(e)}")

async def calculate_distance(origin: str, destination: str) -> float:
    """
    Calculate miles between two addresses
    Returns distance in miles
    """
    try:
        import googlemaps
        
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Google Maps API key not configured")
        
        gmaps = googlemaps.Client(key=api_key)
        
        # Calculate distance using Distance Matrix API
        distance_result = gmaps.distance_matrix(
            origins=[origin],
            destinations=[destination],
            units='imperial',  # Get results in miles
            mode='driving'
        )
        
        if distance_result['rows'][0]['elements'][0]['status'] != 'OK':
            raise HTTPException(status_code=400, detail="Could not calculate distance between addresses")
        
        distance_text = distance_result['rows'][0]['elements'][0]['distance']['text']
        distance_value = distance_result['rows'][0]['elements'][0]['distance']['value']
        
        # Convert meters to miles
        miles = distance_value * 0.000621371
        
        return round(miles, 2)
        
    except ImportError:
        logger.warning("Google Maps client not installed")
        raise HTTPException(status_code=500, detail="Google Maps service not configured")
    except Exception as e:
        logger.error(f"Distance calculation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Distance calculation failed: {str(e)}")

async def geocode_address(address: str) -> Dict:
    """
    Get lat/long coordinates for an address
    """
    try:
        import googlemaps
        
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Google Maps API key not configured")
        
        gmaps = googlemaps.Client(key=api_key)
        
        # Geocode the address
        geocode_result = gmaps.geocode(address)
        
        if not geocode_result:
            raise HTTPException(status_code=400, detail="Could not geocode address")
        
        location = geocode_result[0]['geometry']['location']
        
        return {
            "latitude": location['lat'],
            "longitude": location['lng'],
            "formatted_address": geocode_result[0]['formatted_address']
        }
        
    except ImportError:
        logger.warning("Google Maps client not installed")
        raise HTTPException(status_code=500, detail="Google Maps service not configured")
    except Exception as e:
        logger.error(f"Geocoding failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Geocoding failed: {str(e)}")

async def get_place_details(place_id: str) -> Dict:
    """
    Get detailed information about a place using place_id
    """
    try:
        import googlemaps
        
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="Google Maps API key not configured")
        
        gmaps = googlemaps.Client(key=api_key)
        
        # Get place details
        place_details = gmaps.place(
            place_id=place_id,
            fields=['name', 'formatted_address', 'geometry', 'formatted_phone_number', 'website']
        )
        
        result = place_details['result']
        location = result.get('geometry', {}).get('location', {})
        
        return {
            "name": result.get('name', ''),
            "formatted_address": result.get('formatted_address', ''),
            "latitude": location.get('lat'),
            "longitude": location.get('lng'),
            "phone": result.get('formatted_phone_number', ''),
            "website": result.get('website', '')
        }
        
    except ImportError:
        logger.warning("Google Maps client not installed")
        raise HTTPException(status_code=500, detail="Google Maps service not configured")
    except Exception as e:
        logger.error(f"Place details lookup failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Place details lookup failed: {str(e)}")

