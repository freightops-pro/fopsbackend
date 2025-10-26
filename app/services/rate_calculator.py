from typing import List, Dict
from sqlalchemy.orm import Session
from app.models.userModels import Driver
import logging

logger = logging.getLogger(__name__)

async def calculate_driver_pay(
    db: Session,
    driver_id: str,
    miles: float,
    base_rate: float,
    accessorials: List[Dict]
) -> float:
    """
    Calculate driver pay based on driver's individual pay profile
    """
    try:
        driver = db.query(Driver).filter(Driver.id == driver_id).first()
        if not driver:
            raise ValueError(f"Driver {driver_id} not found")
        
        # Use driver's pay profile from database
        # payType can be: "per_mile", "percentage", "flat_rate", "hourly"
        # payRate contains the actual rate value
        
        total_revenue = base_rate + sum(a.get("amount", 0) for a in accessorials)
        
        if driver.payType == "per_mile":
            driver_pay = miles * float(driver.payRate or 0)
        elif driver.payType == "percentage":
            driver_pay = total_revenue * (float(driver.payRate or 0) / 100)
        elif driver.payType == "flat_rate":
            driver_pay = float(driver.payRate or 0)
        elif driver.payType == "hourly":
            # Estimate hours based on miles (avg 50 mph)
            estimated_hours = miles / 50
            driver_pay = estimated_hours * float(driver.payRate or 0)
        else:
            # Default to 65% if pay type not specified
            driver_pay = total_revenue * 0.65
        
        return round(driver_pay, 2)
        
    except Exception as e:
        logger.error(f"Driver pay calculation failed: {str(e)}")
        # Fallback to 65% of revenue
        total_revenue = base_rate + sum(a.get("amount", 0) for a in accessorials)
        return round(total_revenue * 0.65, 2)

async def calculate_total_rate(
    base_rate: float,
    miles: float,
    accessorials: List[Dict]
) -> float:
    """
    Calculate total customer rate including base rate and accessorials
    """
    accessorial_total = sum(a.get("amount", 0) for a in accessorials)
    return round(base_rate + accessorial_total, 2)

async def calculate_leg_breakdown(
    db: Session,
    leg_data: Dict,
    company_id: str
) -> Dict:
    """
    Calculate detailed breakdown for a single leg
    """
    try:
        driver_id = leg_data.get("driver_id")
        miles = leg_data.get("miles", 0)
        base_rate = leg_data.get("base_rate", 0)
        accessorials = leg_data.get("accessorials", [])
        
        # Calculate driver pay
        driver_pay = await calculate_driver_pay(
            db, driver_id, miles, base_rate, accessorials
        )
        
        # Calculate total rate
        total_rate = await calculate_total_rate(base_rate, miles, accessorials)
        
        return {
            "driver_id": driver_id,
            "miles": miles,
            "base_rate": base_rate,
            "accessorials": accessorials,
            "driver_pay": driver_pay,
            "total_rate": total_rate,
            "profit": round(total_rate - driver_pay, 2)
        }
        
    except Exception as e:
        logger.error(f"Leg breakdown calculation failed: {str(e)}")
        return {
            "driver_id": leg_data.get("driver_id"),
            "miles": leg_data.get("miles", 0),
            "base_rate": leg_data.get("base_rate", 0),
            "accessorials": leg_data.get("accessorials", []),
            "driver_pay": 0,
            "total_rate": leg_data.get("base_rate", 0),
            "profit": 0
        }

async def validate_driver_availability(
    db: Session,
    driver_id: str,
    company_id: str
) -> bool:
    """
    Check if driver is available and belongs to the company
    """
    try:
        driver = db.query(Driver).filter(
            Driver.id == driver_id,
            Driver.companyId == company_id,
            Driver.status == "available",
            Driver.isActive == True
        ).first()
        
        return driver is not None
        
    except Exception as e:
        logger.error(f"Driver availability check failed: {str(e)}")
        return False

async def get_driver_pay_summary(
    db: Session,
    company_id: str
) -> List[Dict]:
    """
    Get summary of all active drivers and their pay profiles
    """
    try:
        drivers = db.query(Driver).filter(
            Driver.companyId == company_id,
            Driver.isActive == True
        ).all()
        
        summary = []
        for driver in drivers:
            summary.append({
                "id": driver.id,
                "name": f"{driver.firstName} {driver.lastName}",
                "pay_type": driver.payType,
                "pay_rate": float(driver.payRate or 0),
                "status": driver.status,
                "current_location": driver.currentLocation
            })
        
        return summary
        
    except Exception as e:
        logger.error(f"Driver pay summary failed: {str(e)}")
        return []

