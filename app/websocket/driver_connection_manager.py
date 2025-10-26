from fastapi import WebSocket
from typing import Dict, Set, Optional, Any
import json
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.simple_load import SimpleLoad

logger = logging.getLogger(__name__)


class DriverConnectionManager:
    """
    Separate WebSocket connection manager for driver mobile app.
    
    Optimized for mobile battery efficiency:
    - Connects only when driver has active load
    - Aggressive timeout (30s vs 5min for webapp)
    - Optimized heartbeat (30s intervals)
    - Automatic cleanup of stale connections
    
    Isolated from collaboration WebSocket for:
    - Different connection lifecycle
    - Different message types/priorities
    - Independent scaling
    - Mobile-specific reconnection strategies
    """
    
    def __init__(self, db: Optional[Session] = None):
        # Active driver connections: {driver_id: websocket}
        self.active_connections: Dict[int, WebSocket] = {}
        
        # Company-to-drivers mapping: {company_id: Set[driver_id]}
        self.company_drivers: Dict[int, Set[int]] = {}
        
        # Driver metadata: {driver_id: {company_id, connected_at, last_ping, active_load_id}}
        self.driver_metadata: Dict[int, Dict[str, Any]] = {}
        
        # Location cache for dispatchers: {driver_id: latest_location}
        self.driver_locations: Dict[int, Dict[str, Any]] = {}
        
        # Database session for saving location data
        self.db = db

    async def connect_driver(
        self, 
        websocket: WebSocket, 
        driver_id: int, 
        company_id: int,
        active_load_id: Optional[int] = None
    ):
        """Connect a driver to WebSocket (only when they have active load)"""
        
        await websocket.accept()
        
        # Store connection
        self.active_connections[driver_id] = websocket
        
        # Add to company mapping
        if company_id not in self.company_drivers:
            self.company_drivers[company_id] = set()
        self.company_drivers[company_id].add(driver_id)
        
        # Store metadata
        self.driver_metadata[driver_id] = {
            "company_id": company_id,
            "connected_at": datetime.now(timezone.utc),
            "last_ping": datetime.now(timezone.utc),
            "active_load_id": active_load_id,
            "connection_count": self.driver_metadata.get(driver_id, {}).get("connection_count", 0) + 1
        }
        
        logger.info(f"Driver {driver_id} connected to WebSocket (company: {company_id}, load: {active_load_id})")
        
        # Notify dispatchers that driver is online
        await self.broadcast_to_company_dispatchers(
            company_id=company_id,
            message={
                "type": "driver_online",
                "data": {
                    "driver_id": driver_id,
                    "active_load_id": active_load_id,
                    "connected_at": datetime.now(timezone.utc).isoformat()
                }
            },
            exclude_driver=driver_id
        )

    async def disconnect_driver(self, driver_id: int):
        """Disconnect a driver from WebSocket"""
        
        if driver_id not in self.active_connections:
            return
        
        metadata = self.driver_metadata.get(driver_id, {})
        company_id = metadata.get("company_id")
        
        # Remove connection
        del self.active_connections[driver_id]
        
        # Remove from company mapping
        if company_id and company_id in self.company_drivers:
            self.company_drivers[company_id].discard(driver_id)
            if not self.company_drivers[company_id]:
                del self.company_drivers[company_id]
        
        # Calculate session duration
        connected_at = metadata.get("connected_at")
        duration = None
        if connected_at:
            duration = (datetime.now(timezone.utc) - connected_at).total_seconds()
        
        logger.info(f"Driver {driver_id} disconnected (session duration: {duration}s)")
        
        # Notify dispatchers that driver is offline
        if company_id:
            await self.broadcast_to_company_dispatchers(
                company_id=company_id,
                message={
                    "type": "driver_offline",
                    "data": {
                        "driver_id": driver_id,
                        "disconnected_at": datetime.now(timezone.utc).isoformat(),
                        "session_duration": duration
                    }
                },
                exclude_driver=driver_id
            )
        
        # Keep metadata for analytics but mark as disconnected
        if driver_id in self.driver_metadata:
            self.driver_metadata[driver_id]["disconnected_at"] = datetime.now(timezone.utc)

    async def broadcast_to_driver(self, driver_id: int, message: Dict[str, Any]):
        """Send message to specific driver"""
        
        if driver_id not in self.active_connections:
            logger.warning(f"Driver {driver_id} not connected, cannot send message")
            return False
        
        websocket = self.active_connections[driver_id]
        
        try:
            message_text = json.dumps(message, default=str)
            await websocket.send_text(message_text)
            
            # Update last activity
            if driver_id in self.driver_metadata:
                self.driver_metadata[driver_id]["last_activity"] = datetime.now(timezone.utc)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message to driver {driver_id}: {e}")
            await self.disconnect_driver(driver_id)
            return False

    async def broadcast_to_company_dispatchers(
        self, 
        company_id: int, 
        message: Dict[str, Any],
        exclude_driver: Optional[int] = None
    ):
        """
        Broadcast message to all dispatchers in the company.
        
        Note: This sends to the collaboration WebSocket manager's company channel.
        Import and use the existing ConnectionManager from collaboration.
        """
        
        # Import here to avoid circular dependency
        from app.websocket.connection_manager import manager as collaboration_manager
        
        try:
            # Broadcast to webapp dispatchers through collaboration WebSocket
            # The collaboration manager handles company-level broadcasts
            await collaboration_manager.broadcast_to_company(company_id, message)
            
        except Exception as e:
            logger.error(f"Failed to broadcast to company {company_id} dispatchers: {e}")

    async def broadcast_to_all_company_drivers(
        self, 
        company_id: int, 
        message: Dict[str, Any]
    ):
        """Broadcast message to all connected drivers in a company"""
        
        if company_id not in self.company_drivers:
            return
        
        driver_ids = list(self.company_drivers[company_id])
        failed_drivers = []
        
        for driver_id in driver_ids:
            success = await self.broadcast_to_driver(driver_id, message)
            if not success:
                failed_drivers.append(driver_id)
        
        if failed_drivers:
            logger.warning(f"Failed to broadcast to {len(failed_drivers)} drivers in company {company_id}")

    async def update_driver_location(
        self, 
        driver_id: int, 
        location_data: Dict[str, Any]
    ):
        """Update driver location and broadcast to dispatchers"""
        
        # Cache location
        self.driver_locations[driver_id] = {
            **location_data,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Get company_id from metadata
        metadata = self.driver_metadata.get(driver_id, {})
        company_id = metadata.get("company_id")
        
        if not company_id:
            logger.warning(f"Cannot broadcast location for driver {driver_id}: no company_id")
            return
        
        # Get active load and update load record with current driver location
        if self.db:
            load = self.db.query(SimpleLoad).filter(
                SimpleLoad.assignedDriverId == str(driver_id),
                SimpleLoad.companyId == str(company_id),
                SimpleLoad.status.in_(['assigned', 'in_transit', 'at_pickup', 'loaded', 'at_delivery'])
            ).first()
            
            if load:
                # Update load record with current driver location
                load.current_driver_latitude = location_data.get("latitude")
                load.current_driver_longitude = location_data.get("longitude")
                load.last_location_update = datetime.now(timezone.utc)
                
                # Append to route history
                if not load.route_history:
                    load.route_history = []
                load.route_history.append({
                    "lat": location_data.get("latitude"),
                    "lng": location_data.get("longitude"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "speed": location_data.get("speed"),
                    "accuracy": location_data.get("accuracy")
                })
                
                self.db.commit()
                
                # Broadcast load location (driver mobile GPS)
                await self.broadcast_to_company_dispatchers(
                    company_id=company_id,
                    message={
                        "type": "load_location_update",
                        "data": {
                            "load_id": load.id,
                            "driver_id": driver_id,
                            "truck_id": load.assignedTruckId,
                            "location": location_data,
                            "load_status": load.status
                        }
                    }
                )
            else:
                # No active load - broadcast general driver location
                await self.broadcast_to_company_dispatchers(
                    company_id=company_id,
                    message={
                        "type": "driver_location_update",
                        "data": {
                            "driver_id": driver_id,
                            "active_load_id": metadata.get("active_load_id"),
                            "location": location_data
                        }
                    }
                )
        else:
            # Fallback if no database session
            await self.broadcast_to_company_dispatchers(
                company_id=company_id,
                message={
                    "type": "driver_location_update",
                    "data": {
                        "driver_id": driver_id,
                        "active_load_id": metadata.get("active_load_id"),
                        "location": location_data
                    }
                }
            )

    async def update_driver_status(
        self, 
        driver_id: int, 
        status: str,
        load_id: Optional[int] = None,
        eta: Optional[str] = None,
        notes: Optional[str] = None
    ):
        """Update driver status and broadcast to dispatchers"""
        
        metadata = self.driver_metadata.get(driver_id, {})
        company_id = metadata.get("company_id")
        
        if not company_id:
            logger.warning(f"Cannot broadcast status for driver {driver_id}: no company_id")
            return
        
        # Update metadata
        if driver_id in self.driver_metadata:
            self.driver_metadata[driver_id]["last_status"] = status
            self.driver_metadata[driver_id]["last_status_update"] = datetime.now(timezone.utc)
        
        # Broadcast to company dispatchers
        await self.broadcast_to_company_dispatchers(
            company_id=company_id,
            message={
                "type": "driver_status_update",
                "data": {
                    "driver_id": driver_id,
                    "status": status,
                    "load_id": load_id,
                    "eta": eta,
                    "notes": notes,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )

    async def ping_driver(self, driver_id: int) -> bool:
        """Send ping to driver and update last_ping timestamp"""
        
        success = await self.broadcast_to_driver(
            driver_id=driver_id,
            message={"type": "ping", "timestamp": datetime.now(timezone.utc).isoformat()}
        )
        
        if success and driver_id in self.driver_metadata:
            self.driver_metadata[driver_id]["last_ping"] = datetime.now(timezone.utc)
        
        return success

    def get_active_driver_connections(self, company_id: int) -> list:
        """Get list of active driver connections for a company"""
        
        if company_id not in self.company_drivers:
            return []
        
        active_drivers = []
        for driver_id in self.company_drivers[company_id]:
            metadata = self.driver_metadata.get(driver_id, {})
            location = self.driver_locations.get(driver_id)
            
            active_drivers.append({
                "driver_id": driver_id,
                "connected_at": metadata.get("connected_at"),
                "last_ping": metadata.get("last_ping"),
                "active_load_id": metadata.get("active_load_id"),
                "last_status": metadata.get("last_status"),
                "location": location
            })
        
        return active_drivers

    def get_driver_connection_info(self, driver_id: int) -> Optional[Dict[str, Any]]:
        """Get connection info for specific driver"""
        
        if driver_id not in self.active_connections:
            return None
        
        metadata = self.driver_metadata.get(driver_id, {})
        location = self.driver_locations.get(driver_id)
        
        return {
            "driver_id": driver_id,
            "is_connected": True,
            "company_id": metadata.get("company_id"),
            "connected_at": metadata.get("connected_at"),
            "last_ping": metadata.get("last_ping"),
            "last_activity": metadata.get("last_activity"),
            "active_load_id": metadata.get("active_load_id"),
            "last_status": metadata.get("last_status"),
            "connection_count": metadata.get("connection_count", 0),
            "location": location
        }

    async def cleanup_stale_connections(self, timeout_seconds: int = 30):
        """Clean up connections that haven't pinged in timeout_seconds (mobile-optimized: 30s)"""
        
        now = datetime.now(timezone.utc)
        stale_drivers = []
        
        for driver_id, metadata in self.driver_metadata.items():
            last_ping = metadata.get("last_ping")
            if last_ping and (now - last_ping).total_seconds() > timeout_seconds:
                stale_drivers.append(driver_id)
        
        for driver_id in stale_drivers:
            logger.warning(f"Cleaning up stale connection for driver {driver_id}")
            await self.disconnect_driver(driver_id)
        
        return len(stale_drivers)

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        
        return {
            "total_active_connections": len(self.active_connections),
            "companies_with_drivers": len(self.company_drivers),
            "total_drivers_tracked": len(self.driver_metadata),
            "drivers_with_location": len(self.driver_locations)
        }


# Global driver connection manager instance
driver_manager = DriverConnectionManager()
