from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import logging

from app.models.userModels import Driver
from app.models.simple_load import SimpleLoad
# from app.models.driver_location import DriverLocationHistory, DriverConnectionLog
from app.schema.driver_websocket import LoadAcceptance, LoadCompletion

logger = logging.getLogger(__name__)


class DriverService:
    """Service for managing driver operations and WebSocket interactions"""
    
    def __init__(self, db: Session):
        self.db = db

    async def get_driver_active_loads(
        self, 
        driver_id: int, 
        company_id: int
    ) -> List[SimpleLoad]:
        """Get all active loads assigned to a driver"""
        
        loads = self.db.query(SimpleLoad).filter(
            and_(
                SimpleLoad.assignedDriverId == str(driver_id),
                SimpleLoad.companyId == str(company_id),
                SimpleLoad.status.in_(['assigned', 'in_transit', 'at_pickup', 'loaded', 'at_delivery'])
            )
        ).order_by(SimpleLoad.pickuptime).all()
        
        return loads

    async def update_driver_location_history(
        self, 
        driver_id: int,
        company_id: int,
        location_data: Dict[str, Any]
    ):
        """Save driver location to history"""
        
        # TODO: Uncomment when driver_location models are properly migrated
        # location_record = DriverLocationHistory(
        #     driver_id=driver_id,
        #     company_id=company_id,
        #     latitude=location_data.get("latitude"),
        #     longitude=location_data.get("longitude"),
        #     accuracy=location_data.get("accuracy"),
        #     speed=location_data.get("speed"),
        #     heading=location_data.get("heading"),
        #     altitude=location_data.get("altitude"),
        #     is_moving=location_data.get("is_moving", False),
        #     is_on_duty=location_data.get("is_on_duty", True),
        #     load_id=location_data.get("load_id"),
        #     timestamp=location_data.get("timestamp", datetime.now(timezone.utc))
        # )
        # 
        # self.db.add(location_record)
        # self.db.commit()
        # 
        # logger.info(f"Location history saved for driver {driver_id}")
        # 
        # return location_record
        
        logger.info(f"Location history logging disabled for driver {driver_id}")
        return None

    async def notify_driver_load_assignment(
        self, 
        driver_id: int,
        load_id: int,
        company_id: int
    ):
        """Notify driver of new load assignment via WebSocket"""
        
        # Get load details
        load = self.db.query(SimpleLoad).filter(
            and_(
                SimpleLoad.id == load_id,
                SimpleLoad.company_id == company_id
            )
        ).first()
        
        if not load:
            raise ValueError("Load not found")
        
        # Update load status
        load.status = "assigned"
        load.assigned_driver_id = driver_id
        self.db.commit()
        
        logger.info(f"Load {load_id} assigned to driver {driver_id}")
        
        return load

    async def handle_load_acceptance(
        self,
        driver_id: int,
        load_id: int,
        acceptance_data: Dict[str, Any]
    ):
        """Handle driver accepting a load"""
        
        load = self.db.query(SimpleLoad).filter(
            SimpleLoad.id == load_id,
            SimpleLoad.assigned_driver_id == driver_id
        ).first()
        
        if not load:
            raise ValueError("Load not found or not assigned to this driver")
        
        # Update load status
        if acceptance_data.get("accepted"):
            load.status = "accepted"
            if acceptance_data.get("estimated_pickup_time"):
                load.pickuptime = acceptance_data.get("estimated_pickup_time")
        else:
            load.status = "rejected"
            load.assigned_driver_id = None
        
        self.db.commit()
        
        logger.info(f"Load {load_id} {'accepted' if acceptance_data.get('accepted') else 'rejected'} by driver {driver_id}")
        
        return load

    async def handle_load_completion(
        self,
        driver_id: int,
        load_id: int,
        completion_data: Dict[str, Any]
    ):
        """Handle driver completing a load"""
        
        load = self.db.query(SimpleLoad).filter(
            SimpleLoad.id == load_id,
            SimpleLoad.assigned_driver_id == driver_id
        ).first()
        
        if not load:
            raise ValueError("Load not found or not assigned to this driver")
        
        # Update load status
        load.status = "completed"
        load.deliverytime = completion_data.get("completed_at", datetime.now(timezone.utc))
        
        # Store POD/BOL upload status
        if completion_data.get("pod_uploaded"):
            load.pod_uploaded = True
        if completion_data.get("bol_uploaded"):
            load.bol_uploaded = True
        
        # Store completion notes
        if completion_data.get("notes"):
            load.delivery_notes = completion_data.get("notes")
        
        self.db.commit()
        
        logger.info(f"Load {load_id} completed by driver {driver_id}")
        
        return load

    async def get_driver_connection_info(
        self,
        driver_id: int,
        company_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get driver connection information from database"""
        
        # TODO: Uncomment when driver_location models are properly migrated
        # # Get most recent connection log
        # connection = self.db.query(DriverConnectionLog).filter(
        #     and_(
        #         DriverConnectionLog.driver_id == driver_id,
        #         DriverConnectionLog.company_id == company_id
        #     )
        # ).order_by(DriverConnectionLog.connected_at.desc()).first()
        # 
        # if not connection:
        #     return None
        # 
        # return {
        #     "driver_id": driver_id,
        #     "connected_at": connection.connected_at,
        #     "disconnected_at": connection.disconnected_at,
        #     "session_duration": connection.session_duration,
        #     "device_info": connection.device_info,
        #     "app_version": connection.app_version
        # }
        
        logger.info(f"Connection info disabled for driver {driver_id}")
        return None

    async def log_driver_connection(
        self,
        driver_id: int,
        company_id: int,
        connection_type: str = "websocket",
        device_info: Optional[Dict[str, Any]] = None
    ):
        """Log driver connection event"""
        
        # TODO: Uncomment when driver_location models are properly migrated
        # connection_log = DriverConnectionLog(
        #     driver_id=driver_id,
        #     company_id=company_id,
        #     connected_at=datetime.now(timezone.utc),
        #     connection_type=connection_type,
        #     device_info=device_info
        # )
        # 
        # self.db.add(connection_log)
        # self.db.commit()
        # 
        # return connection_log
        
        logger.info(f"Connection logging disabled for driver {driver_id}")
        return None

    async def log_driver_disconnection(
        self,
        driver_id: int,
        company_id: int,
        disconnect_reason: Optional[str] = None
    ):
        """Log driver disconnection event"""
        
        # TODO: Uncomment when driver_location models are properly migrated
        # # Find most recent connection
        # connection = self.db.query(DriverConnectionLog).filter(
        #     and_(
        #         DriverConnectionLog.driver_id == driver_id,
        #         DriverConnectionLog.company_id == company_id,
        #         DriverConnectionLog.disconnected_at == None
        #     )
        # ).order_by(DriverConnectionLog.connected_at.desc()).first()
        # 
        # if connection:
        #     connection.disconnected_at = datetime.now(timezone.utc)
        #     connection.disconnect_reason = disconnect_reason
        #     
        #     # Calculate session duration
        #     if connection.connected_at:
        #         duration = (connection.disconnected_at - connection.connected_at).total_seconds()
        #         connection.session_duration = int(duration)
        #     
        #     self.db.commit()
        # 
        # return connection
        
        logger.info(f"Disconnection logging disabled for driver {driver_id}")
        return None

    async def get_driver_location_history(
        self,
        driver_id: int,
        company_id: int,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Any]:
        """Get driver location history"""
        
        # TODO: Uncomment when driver_location models are properly migrated
        # query = self.db.query(DriverLocationHistory).filter(
        #     and_(
        #         DriverLocationHistory.driver_id == driver_id,
        #         DriverLocationHistory.company_id == company_id
        #     )
        # )
        # 
        # if start_time:
        #     query = query.filter(DriverLocationHistory.timestamp >= start_time)
        # 
        # if end_time:
        #     query = query.filter(DriverLocationHistory.timestamp <= end_time)
        # 
        # locations = query.order_by(
        #     DriverLocationHistory.timestamp.desc()
        # ).limit(limit).all()
        # 
        # return locations
        
        logger.info(f"Location history disabled for driver {driver_id}")
        return []

    async def get_driver_statistics(
        self,
        driver_id: int,
        company_id: int,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """Get driver performance statistics"""
        
        period_start = datetime.now(timezone.utc) - timedelta(days=period_days)
        
        # Count completed loads
        completed_loads = self.db.query(func.count(SimpleLoad.id)).filter(
            and_(
                SimpleLoad.assigned_driver_id == driver_id,
                SimpleLoad.company_id == company_id,
                SimpleLoad.status == "completed",
                SimpleLoad.deliverytime >= period_start
            )
        ).scalar()
        
        # Count active loads
        active_loads = self.db.query(func.count(SimpleLoad.id)).filter(
            and_(
                SimpleLoad.assigned_driver_id == driver_id,
                SimpleLoad.company_id == company_id,
                SimpleLoad.status.in_(['assigned', 'in_transit', 'at_pickup', 'loaded', 'at_delivery'])
            )
        ).scalar()
        
        # TODO: Uncomment when driver_location models are properly migrated
        # # Count total connections
        # total_connections = self.db.query(func.count(DriverConnectionLog.id)).filter(
        #     and_(
        #         DriverConnectionLog.driver_id == driver_id,
        #         DriverConnectionLog.company_id == company_id,
        #         DriverConnectionLog.connected_at >= period_start
        #     )
        # ).scalar()
        # 
        # # Average session duration
        # avg_session = self.db.query(func.avg(DriverConnectionLog.session_duration)).filter(
        #     and_(
        #         DriverConnectionLog.driver_id == driver_id,
        #         DriverConnectionLog.company_id == company_id,
        #         DriverConnectionLog.session_duration != None,
        #         DriverConnectionLog.connected_at >= period_start
        #     )
        # ).scalar()
        
        total_connections = 0
        avg_session = 0
        
        return {
            "driver_id": driver_id,
            "period_days": period_days,
            "completed_loads": completed_loads or 0,
            "active_loads": active_loads or 0,
            "total_connections": total_connections or 0,
            "average_session_duration_seconds": int(avg_session) if avg_session else 0
        }

    async def verify_pickup_location(self, driver_id: int, load_id: str, location: Dict[str, Any]):
        """Verify driver is at pickup location and timestamp it"""
        load = self.db.query(SimpleLoad).filter(
            and_(
                SimpleLoad.id == load_id,
                SimpleLoad.assignedDriverId == str(driver_id)
            )
        ).first()
        
        if not load:
            raise ValueError("Load not found")
        
        # Store actual pickup location and time
        load.actual_pickup_latitude = location.get("latitude")
        load.actual_pickup_longitude = location.get("longitude")
        load.actual_pickup_time = datetime.now(timezone.utc)
        load.status = "at_pickup"
        
        self.db.commit()
        
        # Broadcast verification
        from app.websocket.driver_connection_manager import driver_manager
        await driver_manager.broadcast_to_company_dispatchers(
            company_id=int(load.companyId),
            message={
                "type": "pickup_verified",
                "data": {
                    "load_id": load_id,
                    "location": location,
                    "verified_at": load.actual_pickup_time.isoformat()
                }
            }
        )
        
        return load

    async def verify_delivery_location(self, driver_id: int, load_id: str, location: Dict[str, Any]):
        """Verify driver is at delivery location and timestamp it"""
        load = self.db.query(SimpleLoad).filter(
            and_(
                SimpleLoad.id == load_id,
                SimpleLoad.assignedDriverId == str(driver_id)
            )
        ).first()
        
        if not load:
            raise ValueError("Load not found")
        
        # Store actual delivery location and time (proof of delivery)
        load.actual_delivery_latitude = location.get("latitude")
        load.actual_delivery_longitude = location.get("longitude")
        load.actual_delivery_time = datetime.now(timezone.utc)
        load.status = "completed"
        
        self.db.commit()
        
        return load