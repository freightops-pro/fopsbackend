from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class LegData(BaseModel):
    id: str
    pickup_location: str
    delivery_location: str
    pickup_coordinates: Optional[Dict[str, float]] = None
    delivery_coordinates: Optional[Dict[str, float]] = None
    distance_miles: Optional[float] = None
    estimated_duration_hours: Optional[float] = None

class RouteCalculationRequest(BaseModel):
    legs: List[LegData]
    optimization_type: str = Field(default="distance")  # distance, time, cost
    avoid_tolls: bool = Field(default=False)
    avoid_highways: bool = Field(default=False)

class RouteCalculationResponse(BaseModel):
    total_miles: float
    estimated_duration_hours: float
    fuel_cost_estimate: float
    legs: int
    optimization_score: Optional[float] = None
