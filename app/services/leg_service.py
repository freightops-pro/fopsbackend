from sqlalchemy.orm import Session
from typing import List, Dict
from app.models.userModels import Driver
from app.services.maps_service import calculate_distance
from app.services.rate_calculator import calculate_driver_pay
import logging

logger = logging.getLogger(__name__)

async def generate_legs(
    db: Session,
    load_id: str,
    stops: List[Dict],
    company_id: str,
    base_rate: float,
    accessorials: List[Dict]
) -> List[Dict]:
    """
    Auto-generate legs based on stops:
    - Pickup → Yard (Driver 1)
    - Yard → Delivery (Driver 2)
    - Delivery → Return (Driver 3 - optional)
    """
    try:
        # Fetch active drivers from company
        active_drivers = db.query(Driver).filter(
            Driver.companyId == company_id,
            Driver.status == "available",
            Driver.isActive == True
        ).limit(3).all()
        
        if not active_drivers:
            raise ValueError("No available drivers found for the company")
        
        legs = []
        
        # Ensure we have at least 2 stops (pickup and delivery)
        if len(stops) < 2:
            raise ValueError("At least 2 stops required for leg generation")
        
        # Sort stops by sequence number
        sorted_stops = sorted(stops, key=lambda x: x.get("sequence_number", 0))
        
        # Generate legs based on number of stops
        if len(sorted_stops) == 2:
            # Simple pickup to delivery
            pickup = sorted_stops[0]
            delivery = sorted_stops[1]
            
            # Calculate distance
            miles = await calculate_distance(pickup["address"], delivery["address"])
            
            # Assign to first available driver
            driver = active_drivers[0]
            
            # Calculate driver pay
            driver_pay = await calculate_driver_pay(
                db, driver.id, miles, base_rate, accessorials
            )
            
            legs.append({
                "leg_number": 1,
                "driver_id": driver.id,
                "start_stop_id": pickup["id"],
                "end_stop_id": delivery["id"],
                "miles": miles,
                "driver_pay": driver_pay,
                "origin": pickup["address"],
                "destination": delivery["address"],
                "pickup_time": pickup.get("appointment_start"),
                "delivery_time": delivery.get("appointment_end")
            })
        
        elif len(sorted_stops) == 3:
            # Pickup → Yard → Delivery (2 legs)
            pickup = sorted_stops[0]
            yard = sorted_stops[1]
            delivery = sorted_stops[2]
            
            # Leg 1: Pickup → Yard
            miles1 = await calculate_distance(pickup["address"], yard["address"])
            driver1 = active_drivers[0] if len(active_drivers) > 0 else None
            driver_pay1 = await calculate_driver_pay(
                db, driver1.id if driver1 else None, miles1, base_rate / 2, accessorials
            ) if driver1 else 0
            
            legs.append({
                "leg_number": 1,
                "driver_id": driver1.id if driver1 else None,
                "start_stop_id": pickup["id"],
                "end_stop_id": yard["id"],
                "miles": miles1,
                "driver_pay": driver_pay1,
                "origin": pickup["address"],
                "destination": yard["address"],
                "pickup_time": pickup.get("appointment_start"),
                "delivery_time": yard.get("appointment_end")
            })
            
            # Leg 2: Yard → Delivery
            miles2 = await calculate_distance(yard["address"], delivery["address"])
            driver2 = active_drivers[1] if len(active_drivers) > 1 else driver1
            driver_pay2 = await calculate_driver_pay(
                db, driver2.id if driver2 else None, miles2, base_rate / 2, accessorials
            ) if driver2 else 0
            
            legs.append({
                "leg_number": 2,
                "driver_id": driver2.id if driver2 else None,
                "start_stop_id": yard["id"],
                "end_stop_id": delivery["id"],
                "miles": miles2,
                "driver_pay": driver_pay2,
                "origin": yard["address"],
                "destination": delivery["address"],
                "pickup_time": yard.get("appointment_start"),
                "delivery_time": delivery.get("appointment_end")
            })
        
        else:
            # 4+ stops: Generate legs between consecutive stops
            for i in range(len(sorted_stops) - 1):
                start_stop = sorted_stops[i]
                end_stop = sorted_stops[i + 1]
                
                # Calculate distance
                miles = await calculate_distance(start_stop["address"], end_stop["address"])
                
                # Assign driver (cycle through available drivers)
                driver = active_drivers[i % len(active_drivers)]
                
                # Calculate driver pay (divide base rate by number of legs)
                leg_base_rate = base_rate / (len(sorted_stops) - 1)
                driver_pay = await calculate_driver_pay(
                    db, driver.id, miles, leg_base_rate, accessorials
                )
                
                legs.append({
                    "leg_number": i + 1,
                    "driver_id": driver.id,
                    "start_stop_id": start_stop["id"],
                    "end_stop_id": end_stop["id"],
                    "miles": miles,
                    "driver_pay": driver_pay,
                    "origin": start_stop["address"],
                    "destination": end_stop["address"],
                    "pickup_time": start_stop.get("appointment_start"),
                    "delivery_time": end_stop.get("appointment_end")
                })
        
        return legs
        
    except Exception as e:
        logger.error(f"Leg generation failed: {str(e)}")
        raise ValueError(f"Failed to generate legs: {str(e)}")

async def validate_leg_assignment(
    db: Session,
    leg_data: Dict,
    company_id: str
) -> bool:
    """
    Validate that a leg assignment is valid
    """
    try:
        driver_id = leg_data.get("driver_id")
        if not driver_id:
            return False
        
        # Check if driver exists and is available
        driver = db.query(Driver).filter(
            Driver.id == driver_id,
            Driver.companyId == company_id,
            Driver.status == "available",
            Driver.isActive == True
        ).first()
        
        return driver is not None
        
    except Exception as e:
        logger.error(f"Leg assignment validation failed: {str(e)}")
        return False

async def update_leg_status(
    db: Session,
    leg_id: int,
    status: str,
    company_id: str
) -> bool:
    """
    Update the status of a leg
    """
    try:
        from app.models.load_leg import LoadLeg
        
        leg = db.query(LoadLeg).filter(
            LoadLeg.id == leg_id,
            LoadLeg.company_id == company_id
        ).first()
        
        if not leg:
            return False
        
        leg.status = status
        
        if status == "dispatched":
            leg.dispatched = True
            from datetime import datetime
            leg.dispatched_at = datetime.utcnow()
        
        db.commit()
        return True
        
    except Exception as e:
        logger.error(f"Leg status update failed: {str(e)}")
        db.rollback()
        return False

async def get_leg_summary(
    db: Session,
    load_id: str,
    company_id: str
) -> List[Dict]:
    """
    Get summary of all legs for a load
    """
    try:
        from app.models.load_leg import LoadLeg
        
        legs = db.query(LoadLeg).filter(
            LoadLeg.load_id == load_id,
            LoadLeg.company_id == company_id
        ).all()
        
        summary = []
        for leg in legs:
            driver_name = ""
            if leg.driver:
                driver_name = f"{leg.driver.firstName} {leg.driver.lastName}"
            
            summary.append({
                "id": leg.id,
                "leg_number": leg.leg_number,
                "driver_id": leg.driver_id,
                "driver_name": driver_name,
                "miles": leg.miles,
                "driver_pay": float(leg.driver_pay or 0),
                "status": leg.status,
                "dispatched": leg.dispatched,
                "origin": leg.origin,
                "destination": leg.destination
            })
        
        return summary
        
    except Exception as e:
        logger.error(f"Leg summary failed: {str(e)}")
        return []

