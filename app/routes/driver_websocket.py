from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
import json
import logging

from app.config.db import get_db
from app.routes.user import get_current_user
from app.models.userModels import Users
from app.models.userModels import Driver
from app.schema.driver_websocket import (
    BroadcastLocationRequest,
    BroadcastStatusRequest,
    DriverConnectionInfo,
    WebSocketMessage,
    MessageType,
    LocationVerificationRequest
)
from app.websocket.driver_connection_manager import driver_manager
from app.services.driver_service import DriverService
import jwt
from app.config.settings import settings

router = APIRouter(prefix="/api/driver", tags=["driver-websocket"])
logger = logging.getLogger(__name__)


def verify_driver_token(token: str, db: Session) -> tuple[int, int]:
    """Verify driver JWT token and return driver_id and company_id"""
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        driver_id = payload.get("driverId")
        
        if not driver_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid driver token"
            )
        
        # Get driver from database to verify and get company_id
        driver = db.query(Driver).filter(Driver.id == driver_id).first()
        
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver not found"
            )
        
        if not driver.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Driver account is inactive"
            )
        
        return int(driver_id), driver.company_id
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


@router.websocket("/ws")
async def driver_websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    active_load_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Main WebSocket endpoint for driver mobile app.
    
    Connection only established when driver has active load (battery-optimized).
    Handles bidirectional real-time updates.
    """
    
    driver_id = None
    company_id = None
    
    try:
        # Verify driver authentication
        driver_id, company_id = verify_driver_token(token, db)
        
        # Set database session for driver manager
        driver_manager.db = db
        
        # Connect driver to WebSocket
        await driver_manager.connect_driver(
            websocket=websocket,
            driver_id=driver_id,
            company_id=company_id,
            active_load_id=active_load_id
        )
        
        # Send connection acknowledgment
        await websocket.send_text(json.dumps({
            "type": "connection_ack",
            "data": {
                "driver_id": driver_id,
                "company_id": company_id,
                "active_load_id": active_load_id,
                "connected_at": driver_manager.driver_metadata[driver_id]["connected_at"].isoformat()
            }
        }))
        
        # Message handling loop
        while True:
            # Receive message from driver
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            message_type = message_data.get("type")
            payload = message_data.get("data", {})
            
            # Handle different message types
            if message_type == "ping":
                # Respond with pong
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": driver_manager.driver_metadata[driver_id]["last_ping"].isoformat()
                }))
            
            elif message_type == "location_update":
                # Update driver location and broadcast to dispatchers
                await driver_manager.update_driver_location(
                    driver_id=driver_id,
                    location_data=payload
                )
            
            elif message_type == "status_update":
                # Update driver status and broadcast
                await driver_manager.update_driver_status(
                    driver_id=driver_id,
                    status=payload.get("status"),
                    load_id=payload.get("load_id"),
                    eta=payload.get("eta"),
                    notes=payload.get("notes")
                )
            
            elif message_type == "load_accepted":
                # Driver accepted load assignment
                service = DriverService(db)
                await service.handle_load_acceptance(
                    driver_id=driver_id,
                    load_id=payload.get("load_id"),
                    acceptance_data=payload
                )
                
                # Broadcast to dispatchers
                await driver_manager.broadcast_to_company_dispatchers(
                    company_id=company_id,
                    message={
                        "type": "load_accepted",
                        "data": {
                            "driver_id": driver_id,
                            "load_id": payload.get("load_id"),
                            "accepted_at": payload.get("accepted_at")
                        }
                    }
                )
            
            elif message_type == "load_completed":
                # Driver completed load
                service = DriverService(db)
                await service.handle_load_completion(
                    driver_id=driver_id,
                    load_id=payload.get("load_id"),
                    completion_data=payload
                )
                
                # Broadcast to dispatchers
                await driver_manager.broadcast_to_company_dispatchers(
                    company_id=company_id,
                    message={
                        "type": "load_completed",
                        "data": {
                            "driver_id": driver_id,
                            "load_id": payload.get("load_id"),
                            "completed_at": payload.get("completed_at")
                        }
                    }
                )
            
            elif message_type == "eta_update":
                # Driver updated ETA
                await driver_manager.broadcast_to_company_dispatchers(
                    company_id=company_id,
                    message={
                        "type": "eta_update",
                        "data": {
                            "driver_id": driver_id,
                            "load_id": payload.get("load_id"),
                            "new_eta": payload.get("new_eta"),
                            "delay_minutes": payload.get("delay_minutes")
                        }
                    }
                )
            
            elif message_type == "delay_notification":
                # Driver reporting delay
                await driver_manager.broadcast_to_company_dispatchers(
                    company_id=company_id,
                    message={
                        "type": "delay_notification",
                        "data": {
                            "driver_id": driver_id,
                            **payload
                        }
                    }
                )
            
            elif message_type == "emergency_alert":
                # Emergency alert from driver
                logger.critical(f"Emergency alert from driver {driver_id}: {payload}")
                
                await driver_manager.broadcast_to_company_dispatchers(
                    company_id=company_id,
                    message={
                        "type": "emergency_alert",
                        "data": {
                            "driver_id": driver_id,
                            **payload
                        }
                    }
                )
            
            elif message_type == "document_uploaded":
                # Driver uploaded document
                await driver_manager.broadcast_to_company_dispatchers(
                    company_id=company_id,
                    message={
                        "type": "document_uploaded",
                        "data": {
                            "driver_id": driver_id,
                            **payload
                        }
                    }
                )
            
            elif message_type == "geofence_event":
                # Geofence triggered
                await driver_manager.broadcast_to_company_dispatchers(
                    company_id=company_id,
                    message={
                        "type": "geofence_event",
                        "data": {
                            "driver_id": driver_id,
                            **payload
                        }
                    }
                )
            
            else:
                logger.warning(f"Unknown message type from driver {driver_id}: {message_type}")
    
    except WebSocketDisconnect:
        logger.info(f"Driver {driver_id} disconnected normally")
        if driver_id:
            await driver_manager.disconnect_driver(driver_id)
    
    except Exception as e:
        logger.error(f"WebSocket error for driver {driver_id}: {e}", exc_info=True)
        if driver_id:
            await driver_manager.disconnect_driver(driver_id)


@router.post("/location/broadcast")
async def broadcast_location(
    request: BroadcastLocationRequest,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Broadcast driver location update to dispatchers.
    Alternative REST endpoint if WebSocket is unavailable.
    """
    
    # Verify user has permission to broadcast for this driver
    driver = db.query(Driver).filter(
        Driver.id == request.driver_id,
        Driver.company_id == current_user.company_id
    ).first()
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    # Broadcast location
    await driver_manager.update_driver_location(
        driver_id=request.driver_id,
        location_data=request.location.dict()
    )
    
    return {"message": "Location broadcast successfully"}


@router.post("/status/update")
async def update_driver_status(
    request: BroadcastStatusRequest,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update and broadcast driver status.
    Alternative REST endpoint if WebSocket is unavailable.
    """
    
    # Verify user has permission
    driver = db.query(Driver).filter(
        Driver.id == request.driver_id,
        Driver.company_id == current_user.company_id
    ).first()
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    # Update status
    await driver_manager.update_driver_status(
        driver_id=request.driver_id,
        status=request.status,
        load_id=request.load_id,
        eta=request.eta.isoformat() if request.eta else None,
        notes=request.notes
    )
    
    return {"message": "Status updated successfully"}


@router.get("/connection/status/{driver_id}", response_model=DriverConnectionInfo)
async def get_driver_connection_status(
    driver_id: int,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get connection status for a specific driver"""
    
    # Verify user has permission
    driver = db.query(Driver).filter(
        Driver.id == driver_id,
        Driver.company_id == current_user.company_id
    ).first()
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    # Get connection info
    connection_info = driver_manager.get_driver_connection_info(driver_id)
    
    if not connection_info:
        # Driver not connected
        return DriverConnectionInfo(
            driver_id=driver_id,
            company_id=driver.company_id,
            is_connected=False
        )
    
    return connection_info


@router.get("/connections/active")
async def get_active_driver_connections(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all active driver connections for the company"""
    
    active_drivers = driver_manager.get_active_driver_connections(
        company_id=current_user.company_id
    )
    
    return {
        "company_id": current_user.company_id,
        "total_active": len(active_drivers),
        "drivers": active_drivers
    }


@router.post("/send-message/{driver_id}")
async def send_message_to_driver(
    driver_id: int,
    message: WebSocketMessage,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send message to a specific driver (dispatcher to driver)"""
    
    # Verify user has permission
    driver = db.query(Driver).filter(
        Driver.id == driver_id,
        Driver.company_id == current_user.company_id
    ).first()
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    # Send message
    success = await driver_manager.broadcast_to_driver(
        driver_id=driver_id,
        message=message.dict()
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Driver is not connected"
        )
    
    return {"message": "Message sent successfully"}


@router.get("/connection/stats")
async def get_connection_stats(
    current_user: Users = Depends(get_current_user)
):
    """Get overall connection statistics (admin only)"""
    
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    stats = driver_manager.get_connection_stats()
    
    return stats


@router.post("/verify-pickup")
async def verify_pickup_location(
    request: LocationVerificationRequest,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify driver is at pickup location and timestamp it.
    Provides proof of pickup location for customer audit trail.
    """
    
    # Verify user has permission
    driver = db.query(Driver).filter(
        Driver.id == request.driver_id,
        Driver.company_id == current_user.company_id
    ).first()
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    # Verify pickup location
    service = DriverService(db)
    load = await service.verify_pickup_location(
        driver_id=request.driver_id,
        load_id=request.load_id,
        location=request.location.dict()
    )
    
    return {
        "message": "Pickup location verified successfully",
        "load_id": request.load_id,
        "verified_at": load.actual_pickup_time.isoformat(),
        "location": {
            "latitude": load.actual_pickup_latitude,
            "longitude": load.actual_pickup_longitude
        }
    }


@router.post("/verify-delivery")
async def verify_delivery_location(
    request: LocationVerificationRequest,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify driver is at delivery location and timestamp it.
    Provides proof of delivery (POD) with GPS coordinates for customer audit trail.
    """
    
    # Verify user has permission
    driver = db.query(Driver).filter(
        Driver.id == request.driver_id,
        Driver.company_id == current_user.company_id
    ).first()
    
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    # Verify delivery location
    service = DriverService(db)
    load = await service.verify_delivery_location(
        driver_id=request.driver_id,
        load_id=request.load_id,
        location=request.location.dict()
    )
    
    return {
        "message": "Delivery location verified successfully (POD)",
        "load_id": request.load_id,
        "verified_at": load.actual_delivery_time.isoformat(),
        "location": {
            "latitude": load.actual_delivery_latitude,
            "longitude": load.actual_delivery_longitude
        }
    }
