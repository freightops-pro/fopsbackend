from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class DriverStatus(str, Enum):
    AVAILABLE = "available"
    EN_ROUTE = "en_route"
    AT_PICKUP = "at_pickup"
    LOADING = "loading"
    LOADED = "loaded"
    IN_TRANSIT = "in_transit"
    AT_DELIVERY = "at_delivery"
    UNLOADING = "unloading"
    COMPLETED = "completed"
    OFF_DUTY = "off_duty"
    ON_BREAK = "on_break"


class MessageType(str, Enum):
    # Driver → Webapp
    LOCATION_UPDATE = "location_update"
    STATUS_UPDATE = "status_update"
    ETA_UPDATE = "eta_update"
    LOAD_ACCEPTED = "load_accepted"
    LOAD_COMPLETED = "load_completed"
    DOCUMENT_UPLOADED = "document_uploaded"
    DELAY_NOTIFICATION = "delay_notification"
    EMERGENCY_ALERT = "emergency_alert"
    GEOFENCE_EVENT = "geofence_event"
    
    # Webapp → Driver
    LOAD_ASSIGNMENT = "load_assignment"
    LOAD_UPDATED = "load_updated"
    DISPATCH_MESSAGE = "dispatch_message"
    ELD_ALERT = "eld_alert"
    ROUTE_UPDATE = "route_update"
    LOAD_CANCELLED = "load_cancelled"
    
    # Bidirectional
    PING = "ping"
    PONG = "pong"
    CONNECTION_ACK = "connection_ack"


class DriverLocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: float = Field(..., ge=0)  # Meters
    speed: Optional[float] = Field(None, ge=0)  # MPH
    heading: Optional[float] = Field(None, ge=0, le=360)  # Degrees
    altitude: Optional[float] = None  # Meters
    is_moving: bool = False
    is_on_duty: bool = True
    load_id: Optional[int] = None
    timestamp: datetime


class DriverStatusUpdate(BaseModel):
    status: DriverStatus
    load_id: Optional[int] = None
    eta: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=500)
    location: Optional[DriverLocationUpdate] = None


class LoadAssignmentNotification(BaseModel):
    load_id: int
    load_number: str
    customer_name: str
    pickup_location: str
    pickup_address: str
    pickup_date: datetime
    pickup_coordinates: Optional[Dict[str, float]] = None
    delivery_location: str
    delivery_address: str
    delivery_date: datetime
    delivery_coordinates: Optional[Dict[str, float]] = None
    rate: int  # In cents
    miles: Optional[float] = None
    notes: Optional[str] = None
    special_instructions: Optional[str] = None
    equipment_type: Optional[str] = None
    assigned_truck: Optional[str] = None
    assigned_trailer: Optional[str] = None


class LoadUpdatedNotification(BaseModel):
    load_id: int
    load_number: str
    updated_fields: Dict[str, Any]
    update_reason: Optional[str] = None
    updated_by: str
    updated_at: datetime


class DispatchMessage(BaseModel):
    message_id: str
    message_type: str  # direct, broadcast, alert, instruction
    content: str = Field(..., min_length=1, max_length=1000)
    priority: str = Field(default="normal")  # low, normal, high, urgent
    sender_name: str
    sender_role: str
    sent_at: datetime
    requires_acknowledgment: bool = False
    attachments: Optional[List[Dict[str, str]]] = None


class ELDAlert(BaseModel):
    alert_id: str
    violation_type: str  # hos_limit, driving_limit, on_duty_limit, rest_break
    severity: str  # warning, critical, violation
    hours_remaining: float
    time_until_violation: Optional[int] = None  # Minutes
    message: str
    recommended_action: str
    created_at: datetime


class GeofenceNotification(BaseModel):
    event_id: str
    zone_type: str  # pickup, delivery, terminal, customer, rest_area
    location_name: str
    location_address: str
    action: str  # entered, exited
    load_id: Optional[int] = None
    triggered_at: datetime
    is_automatic: bool = True  # Auto-detected vs manual


class ETAUpdate(BaseModel):
    load_id: int
    new_eta: datetime
    delay_minutes: Optional[int] = None
    delay_reason: Optional[str] = None
    current_location: Optional[DriverLocationUpdate] = None


class LoadAcceptance(BaseModel):
    load_id: int
    accepted: bool
    acceptance_notes: Optional[str] = None
    estimated_pickup_time: Optional[datetime] = None


class LoadCompletion(BaseModel):
    load_id: int
    completed_at: datetime
    delivery_location: DriverLocationUpdate
    pod_uploaded: bool = False
    bol_uploaded: bool = False
    notes: Optional[str] = None
    customer_signature: Optional[str] = None  # Base64 encoded signature


class DocumentUpload(BaseModel):
    document_id: str
    document_type: str  # pod, bol, inspection, receipt
    load_id: int
    file_name: str
    file_size: int  # Bytes
    uploaded_at: datetime
    notes: Optional[str] = None


class DelayNotification(BaseModel):
    load_id: int
    delay_type: str  # traffic, weather, breakdown, customer, loading, other
    estimated_delay_minutes: int
    current_location: Optional[DriverLocationUpdate] = None
    reason: str
    reported_at: datetime
    eta_update: Optional[datetime] = None


class EmergencyAlert(BaseModel):
    alert_id: str
    emergency_type: str  # breakdown, accident, medical, security, other
    severity: str  # low, medium, high, critical
    description: str
    current_location: DriverLocationUpdate
    load_id: Optional[int] = None
    requires_immediate_response: bool = True
    reported_at: datetime
    contact_number: Optional[str] = None


class RouteUpdate(BaseModel):
    load_id: int
    waypoints: List[Dict[str, Any]]
    total_distance: float  # Miles
    estimated_duration: int  # Minutes
    optimized_route: bool = True
    traffic_alerts: Optional[List[str]] = None
    weather_alerts: Optional[List[str]] = None


class LoadCancellation(BaseModel):
    load_id: int
    load_number: str
    cancellation_reason: str
    cancelled_by: str
    cancelled_at: datetime
    compensation: Optional[int] = None  # Cents, if applicable


class WebSocketMessage(BaseModel):
    type: MessageType
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message_id: Optional[str] = None


class ConnectionStatus(BaseModel):
    driver_id: int
    is_connected: bool
    connected_at: Optional[datetime] = None
    last_ping: Optional[datetime] = None
    active_load_id: Optional[int] = None
    last_location: Optional[DriverLocationUpdate] = None
    connection_quality: str = "good"  # good, fair, poor


class DriverConnectionInfo(BaseModel):
    driver_id: int
    company_id: int
    is_connected: bool
    connected_at: Optional[datetime] = None
    last_ping: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    active_load_id: Optional[int] = None
    last_status: Optional[str] = None
    connection_count: int = 0
    location: Optional[Dict[str, Any]] = None


class BroadcastLocationRequest(BaseModel):
    driver_id: int
    location: DriverLocationUpdate


class BroadcastStatusRequest(BaseModel):
    driver_id: int
    status: DriverStatus
    load_id: Optional[int] = None
    eta: Optional[datetime] = None
    notes: Optional[str] = None


class LocationVerificationRequest(BaseModel):
    driver_id: int
    load_id: str
    location: DriverLocationUpdate
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    pod_signature: Optional[str] = None  # Base64 encoded signature for delivery
    delivery_notes: Optional[str] = None
