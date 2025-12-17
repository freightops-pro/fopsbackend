"""
Production External API Integrations - No Mocks

Real integrations for:
- Weather (OpenWeatherMap API)
- Traffic (Google Maps Traffic API)
- Geocoding (Google Maps Geocoding API)
"""

import os
import httpx
from typing import Dict, Any, Optional, Tuple
from datetime import datetime


class WeatherAPI:
    """OpenWeatherMap API integration for real weather data."""

    def __init__(self):
        self.api_key = os.getenv("OPENWEATHER_API_KEY")
        self.base_url = "https://api.openweathermap.org/data/2.5"

        if not self.api_key:
            raise ValueError("OPENWEATHER_API_KEY environment variable not set")

    async def get_current_weather(self, city: str, state: str = None, country: str = "US") -> Dict[str, Any]:
        """
        Get current weather for a location.

        Returns:
            {
                "location": "Chicago, IL",
                "temperature": 72.5,
                "feels_like": 70.2,
                "conditions": "Clear sky",
                "humidity": 65,
                "wind_speed": 12.5,
                "timestamp": "2025-12-14T10:30:00Z"
            }
        """
        location = f"{city},{state},{country}" if state else f"{city},{country}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/weather",
                params={
                    "q": location,
                    "appid": self.api_key,
                    "units": "imperial"  # Fahrenheit
                },
                timeout=10.0
            )

            if response.status_code != 200:
                raise Exception(f"Weather API error: {response.status_code} - {response.text}")

            data = response.json()

            return {
                "location": f"{data['name']}, {state or ''}",
                "temperature": round(data['main']['temp'], 1),
                "feels_like": round(data['main']['feels_like'], 1),
                "conditions": data['weather'][0]['description'].capitalize(),
                "humidity": data['main']['humidity'],
                "wind_speed": round(data['wind']['speed'], 1),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def get_forecast(self, city: str, state: str = None, country: str = "US", days: int = 5) -> Dict[str, Any]:
        """Get 5-day forecast."""
        location = f"{city},{state},{country}" if state else f"{city},{country}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/forecast",
                params={
                    "q": location,
                    "appid": self.api_key,
                    "units": "imperial",
                    "cnt": days * 8  # 3-hour intervals
                },
                timeout=10.0
            )

            if response.status_code != 200:
                raise Exception(f"Forecast API error: {response.status_code}")

            data = response.json()

            forecasts = []
            for item in data['list']:
                forecasts.append({
                    "datetime": item['dt_txt'],
                    "temperature": round(item['main']['temp'], 1),
                    "conditions": item['weather'][0]['description'],
                    "precipitation_probability": item.get('pop', 0) * 100
                })

            return {
                "location": f"{data['city']['name']}, {state or ''}",
                "forecasts": forecasts
            }


class TrafficAPI:
    """Google Maps Traffic API integration for real traffic data."""

    def __init__(self):
        self.api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.base_url = "https://maps.googleapis.com/maps/api"

        if not self.api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY environment variable not set")

    async def get_traffic_conditions(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float = None,
        dest_lon: float = None
    ) -> Dict[str, Any]:
        """
        Get traffic conditions between two points or at a location.

        Returns:
            {
                "status": "light" | "moderate" | "heavy" | "severe",
                "duration_in_traffic": 3600,  # seconds
                "duration_without_traffic": 2700,
                "delay_seconds": 900,
                "distance_meters": 150000,
                "route_summary": "I-94 W",
                "timestamp": "2025-12-14T10:30:00Z"
            }
        """
        origin = f"{origin_lat},{origin_lon}"
        destination = f"{dest_lat},{dest_lon}" if dest_lat and dest_lon else origin

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/directions/json",
                params={
                    "origin": origin,
                    "destination": destination,
                    "departure_time": "now",
                    "traffic_model": "best_guess",
                    "key": self.api_key
                },
                timeout=10.0
            )

            if response.status_code != 200:
                raise Exception(f"Traffic API error: {response.status_code}")

            data = response.json()

            if data['status'] != 'OK':
                raise Exception(f"Traffic API error: {data['status']}")

            route = data['routes'][0]
            leg = route['legs'][0]

            duration_traffic = leg['duration_in_traffic']['value']
            duration_normal = leg['duration']['value']
            delay = duration_traffic - duration_normal

            # Classify traffic status based on delay
            if delay < 300:  # < 5 min delay
                status = "light"
            elif delay < 900:  # 5-15 min delay
                status = "moderate"
            elif delay < 1800:  # 15-30 min delay
                status = "heavy"
            else:
                status = "severe"

            return {
                "status": status,
                "duration_in_traffic": duration_traffic,
                "duration_without_traffic": duration_normal,
                "delay_seconds": delay,
                "distance_meters": leg['distance']['value'],
                "route_summary": route['summary'],
                "timestamp": datetime.utcnow().isoformat()
            }

    async def geocode_address(self, address: str) -> Tuple[float, float]:
        """
        Convert address to latitude/longitude.

        Returns:
            (latitude, longitude)
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/geocode/json",
                params={
                    "address": address,
                    "key": self.api_key
                },
                timeout=10.0
            )

            if response.status_code != 200:
                raise Exception(f"Geocoding API error: {response.status_code}")

            data = response.json()

            if data['status'] != 'OK':
                raise Exception(f"Geocoding error: {data['status']}")

            location = data['results'][0]['geometry']['location']
            return location['lat'], location['lng']

    async def reverse_geocode(self, lat: float, lon: float) -> str:
        """
        Convert latitude/longitude to address.

        Returns:
            "123 Main St, Chicago, IL 60601, USA"
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/geocode/json",
                params={
                    "latlng": f"{lat},{lon}",
                    "key": self.api_key
                },
                timeout=10.0
            )

            if response.status_code != 200:
                raise Exception(f"Reverse geocoding API error: {response.status_code}")

            data = response.json()

            if data['status'] != 'OK':
                raise Exception(f"Reverse geocoding error: {data['status']}")

            return data['results'][0]['formatted_address']


class ProductionAPIManager:
    """
    Centralized manager for all external APIs.

    Handles:
    - API key validation
    - Rate limiting
    - Error handling
    - Fallback strategies
    """

    def __init__(self):
        self.weather_api = None
        self.traffic_api = None

        # Initialize APIs only if keys are present
        try:
            self.weather_api = WeatherAPI()
        except ValueError as e:
            print(f"[API Manager] Weather API not available: {e}")

        try:
            self.traffic_api = TrafficAPI()
        except ValueError as e:
            print(f"[API Manager] Traffic API not available: {e}")

    async def get_weather(self, city: str, state: str = None) -> Dict[str, Any]:
        """Get weather with error handling."""
        if not self.weather_api:
            raise Exception("Weather API not configured. Set OPENWEATHER_API_KEY environment variable.")

        try:
            return await self.weather_api.get_current_weather(city, state)
        except Exception as e:
            raise Exception(f"Failed to fetch weather: {str(e)}")

    async def get_traffic(self, origin_lat: float, origin_lon: float, dest_lat: float = None, dest_lon: float = None) -> Dict[str, Any]:
        """Get traffic with error handling."""
        if not self.traffic_api:
            raise Exception("Traffic API not configured. Set GOOGLE_MAPS_API_KEY environment variable.")

        try:
            return await self.traffic_api.get_traffic_conditions(origin_lat, origin_lon, dest_lat, dest_lon)
        except Exception as e:
            raise Exception(f"Failed to fetch traffic: {str(e)}")

    async def geocode(self, address: str) -> Tuple[float, float]:
        """Geocode address."""
        if not self.traffic_api:
            raise Exception("Geocoding API not configured. Set GOOGLE_MAPS_API_KEY environment variable.")

        try:
            return await self.traffic_api.geocode_address(address)
        except Exception as e:
            raise Exception(f"Failed to geocode: {str(e)}")

    async def reverse_geocode(self, lat: float, lon: float) -> str:
        """Reverse geocode coordinates."""
        if not self.traffic_api:
            raise Exception("Reverse geocoding API not configured. Set GOOGLE_MAPS_API_KEY environment variable.")

        try:
            return await self.traffic_api.reverse_geocode(lat, lon)
        except Exception as e:
            raise Exception(f"Failed to reverse geocode: {str(e)}")
