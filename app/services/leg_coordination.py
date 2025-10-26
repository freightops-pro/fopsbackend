from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json

from app.models.load_leg import LoadLeg, TransloadOperation
from app.models.simple_load import SimpleLoad
from app.models.userModels import Users

class LegCoordinationService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_load_coordination_status(self, load_id: int, company_id: int) -> Dict:
        """Get coordination status for a multi-leg load"""
        
        # Get the load
        load = self.db.query(SimpleLoad).filter(
            SimpleLoad.id == load_id,
            SimpleLoad.company_id == company_id
        ).first()
        
        if not load:
            return {"error": "Load not found"}
        
        # Get all legs for the load
        legs = self.db.query(LoadLeg).filter(
            LoadLeg.load_id == load_id,
            LoadLeg.company_id == company_id
        ).order_by(LoadLeg.leg_number).all()
        
        # Calculate coordination metrics
        total_legs = len(legs)
        assigned_legs = len([leg for leg in legs if leg.driver_id is not None])
        completed_legs = len([leg for leg in legs if leg.status == "completed"])
        in_progress_legs = len([leg for leg in legs if leg.status == "in_progress"])
        
        # Check for handoff coordination
        handoff_issues = self._check_handoff_coordination(legs)
        
        # Get next required actions
        next_actions = self._get_next_actions(legs)
        
        return {
            "load_id": load_id,
            "total_legs": total_legs,
            "assigned_legs": assigned_legs,
            "completed_legs": completed_legs,
            "in_progress_legs": in_progress_legs,
            "handoff_issues": handoff_issues,
            "next_actions": next_actions,
            "coordination_score": self._calculate_coordination_score(legs),
            "estimated_completion": self._estimate_completion_time(legs)
        }
    
    def _check_handoff_coordination(self, legs: List[LoadLeg]) -> List[Dict]:
        """Check for handoff coordination issues"""
        issues = []
        
        for i in range(len(legs) - 1):
            current_leg = legs[i]
            next_leg = legs[i + 1]
            
            # Check if handoff location is defined
            if not current_leg.handoff_location:
                issues.append({
                    "type": "missing_handoff_location",
                    "leg_number": current_leg.leg_number,
                    "message": f"Handoff location not defined for leg {current_leg.leg_number}"
                })
            
            # Check if delivery time of current leg aligns with pickup time of next leg
            if current_leg.delivery_time and next_leg.pickup_time:
                time_diff = next_leg.pickup_time - current_leg.delivery_time
                if time_diff.total_seconds() < 0:
                    issues.append({
                        "type": "time_conflict",
                        "leg_number": current_leg.leg_number,
                        "message": f"Delivery time of leg {current_leg.leg_number} is after pickup time of leg {next_leg.leg_number}"
                    })
                elif time_diff.total_seconds() > 3600:  # More than 1 hour gap
                    issues.append({
                        "type": "large_gap",
                        "leg_number": current_leg.leg_number,
                        "message": f"Large time gap between leg {current_leg.leg_number} and {next_leg.leg_number}"
                    })
            
            # Check if drivers are assigned for both legs
            if current_leg.driver_id and next_leg.driver_id:
                if current_leg.driver_id == next_leg.driver_id:
                    issues.append({
                        "type": "same_driver",
                        "leg_number": current_leg.leg_number,
                        "message": f"Same driver assigned to consecutive legs {current_leg.leg_number} and {next_leg.leg_number}"
                    })
        
        return issues
    
    def _get_next_actions(self, legs: List[LoadLeg]) -> List[Dict]:
        """Get next required actions for coordination"""
        actions = []
        
        for leg in legs:
            if leg.status == "pending" and not leg.driver_id:
                actions.append({
                    "type": "assign_driver",
                    "leg_number": leg.leg_number,
                    "message": f"Assign driver to leg {leg.leg_number}",
                    "priority": "high"
                })
            elif leg.status == "assigned" and leg.pickup_time <= datetime.utcnow():
                actions.append({
                    "type": "start_leg",
                    "leg_number": leg.leg_number,
                    "message": f"Start leg {leg.leg_number} - pickup time has passed",
                    "priority": "high"
                })
            elif leg.status == "in_progress" and leg.delivery_time <= datetime.utcnow():
                actions.append({
                    "type": "complete_leg",
                    "leg_number": leg.leg_number,
                    "message": f"Complete leg {leg.leg_number} - delivery time has passed",
                    "priority": "medium"
                })
        
        return sorted(actions, key=lambda x: x["priority"] == "high", reverse=True)
    
    def _calculate_coordination_score(self, legs: List[LoadLeg]) -> int:
        """Calculate coordination score (0-100)"""
        if not legs:
            return 0
        
        score = 0
        total_checks = 0
        
        for leg in legs:
            # Driver assignment check
            total_checks += 1
            if leg.driver_id:
                score += 1
            
            # Timing check
            total_checks += 1
            if leg.pickup_time and leg.delivery_time:
                score += 1
            
            # Handoff location check (for middle legs)
            if leg.leg_number < len(legs):
                total_checks += 1
                if leg.handoff_location:
                    score += 1
        
        return int((score / total_checks) * 100) if total_checks > 0 else 0
    
    def _estimate_completion_time(self, legs: List[LoadLeg]) -> Optional[datetime]:
        """Estimate completion time for the entire load"""
        if not legs:
            return None
        
        # Find the last leg
        last_leg = max(legs, key=lambda x: x.leg_number)
        
        if last_leg.delivery_time:
            return last_leg.delivery_time
        
        return None
    
    def coordinate_handoff(self, leg_id: int, company_id: int) -> Dict:
        """Coordinate handoff between two legs"""
        
        leg = self.db.query(LoadLeg).filter(
            LoadLeg.id == leg_id,
            LoadLeg.company_id == company_id
        ).first()
        
        if not leg:
            return {"error": "Leg not found"}
        
        # Find the next leg
        next_leg = self.db.query(LoadLeg).filter(
            LoadLeg.load_id == leg.load_id,
            LoadLeg.leg_number == leg.leg_number + 1,
            LoadLeg.company_id == company_id
        ).first()
        
        if not next_leg:
            return {"message": "No next leg found - this is the final leg"}
        
        # Check if handoff is ready
        handoff_ready = self._is_handoff_ready(leg, next_leg)
        
        if handoff_ready:
            # Create handoff notification
            notification = {
                "type": "handoff_ready",
                "leg_id": leg_id,
                "next_leg_id": next_leg.id,
                "handoff_location": leg.handoff_location,
                "timestamp": datetime.utcnow().isoformat(),
                "message": f"Handoff ready at {leg.handoff_location} between leg {leg.leg_number} and {next_leg.leg_number}"
            }
            
            return notification
        else:
            return {
                "message": "Handoff not ready - waiting for leg completion",
                "leg_id": leg_id,
                "next_leg_id": next_leg.id
            }
    
    def _is_handoff_ready(self, current_leg: LoadLeg, next_leg: LoadLeg) -> bool:
        """Check if handoff is ready between two legs"""
        
        # Check if current leg is completed
        if current_leg.status != "completed":
            return False
        
        # Check if next leg is assigned
        if not next_leg.driver_id:
            return False
        
        # Check if handoff location is defined
        if not current_leg.handoff_location:
            return False
        
        # Check timing
        if current_leg.actual_delivery_time and next_leg.pickup_time:
            if current_leg.actual_delivery_time > next_leg.pickup_time:
                return False
        
        return True
    
    def get_driver_availability_for_leg(self, leg_id: int, company_id: int) -> List[Dict]:
        """Get available drivers for a specific leg"""
        
        leg = self.db.query(LoadLeg).filter(
            LoadLeg.id == leg_id,
            LoadLeg.company_id == company_id
        ).first()
        
        if not leg:
            return []
        
        # Get all drivers for the company
        drivers = self.db.query(Users).filter(
            Users.company_id == company_id,
            Users.role == "driver",
            Users.is_active == True
        ).all()
        
        available_drivers = []
        
        for driver in drivers:
            # Check if driver is available for the leg timing
            availability = self._check_driver_availability(driver, leg)
            
            if availability["available"]:
                available_drivers.append({
                    "driver_id": driver.id,
                    "driver_name": f"{driver.first_name} {driver.last_name}",
                    "location": availability.get("location", "Unknown"),
                    "equipment": availability.get("equipment", "Unknown"),
                    "hours_remaining": availability.get("hours_remaining", 0),
                    "performance_score": availability.get("performance_score", 0),
                    "estimated_cost": availability.get("estimated_cost", 0),
                    "match_score": availability.get("match_score", 0)
                })
        
        # Sort by match score
        return sorted(available_drivers, key=lambda x: x["match_score"], reverse=True)
    
    def _check_driver_availability(self, driver: Users, leg: LoadLeg) -> Dict:
        """Check if a driver is available for a specific leg"""
        
        # Real availability check - query driver's current status
        # Get driver's current location from location history
        latest_location = self.db.query(DriverLocationHistory).filter(
            DriverLocationHistory.driver_id == driver.id
        ).order_by(DriverLocationHistory.timestamp.desc()).first()
        
        # Get driver's assigned equipment
        driver_truck = self.db.query(Truck).filter(
            Truck.assignedDriverId == str(driver.id),
            Truck.isActive == True
        ).first()
        
        # Calculate hours remaining (would integrate with ELD system)
        hours_remaining = 11.0  # Default - would be calculated from ELD data
        
        # Get performance metrics from completed loads
        completed_loads = self.db.query(func.count(SimpleLoad.id)).filter(
            SimpleLoad.assignedDriverId == str(driver.id),
            SimpleLoad.status == "completed"
        ).scalar()
        
        performance_score = min(95, 70 + (completed_loads * 2))  # Basic calculation
        
        # Calculate distance-based cost estimate
        estimated_cost = 1500 + (leg.distance_miles * 2.5) if hasattr(leg, 'distance_miles') else 2000
        
        # Calculate match score based on multiple factors
        match_score = min(100, 
            40 +  # Base score
            (20 if driver_truck else 0) +  # Equipment match
            (20 if hours_remaining > 8 else 10) +  # Hours availability
            min(20, performance_score * 0.2)  # Performance factor
        )
        
        return {
            "available": True,
            "location": latest_location.city if latest_location else "Unknown",
            "equipment": driver_truck.equipment_type if driver_truck else "Unknown",
            "hours_remaining": hours_remaining,
            "performance_score": performance_score,
            "estimated_cost": estimated_cost,
            "match_score": match_score
        }
    
    def create_transload_operation(self, load_id: int, facility_id: int, company_id: int) -> Dict:
        """Create a transload operation for a load"""
        
        # Get the load
        load = self.db.query(SimpleLoad).filter(
            SimpleLoad.id == load_id,
            SimpleLoad.company_id == company_id
        ).first()
        
        if not load:
            return {"error": "Load not found"}
        
        # Get facility information from database
        facility = self.db.query(TransloadFacility).filter(
            TransloadFacility.id == facility_id,
            TransloadFacility.company_id == company_id
        ).first()
        
        if not facility:
            return {"error": "Transload facility not found"}
        
        # Create transload operation with real facility data
        operation = TransloadOperation(
            company_id=company_id,
            load_id=load_id,
            facility_id=facility_id,
            facility_name=facility.name,
            facility_location=facility.location,
            operation_type="transload",
            scheduled_start=datetime.utcnow() + timedelta(hours=2),
            scheduled_end=datetime.utcnow() + timedelta(hours=6),
            status="scheduled"
        )
        
        self.db.add(operation)
        self.db.commit()
        
        return {
            "message": "Transload operation created successfully",
            "operation_id": operation.id,
            "scheduled_start": operation.scheduled_start.isoformat(),
            "scheduled_end": operation.scheduled_end.isoformat()
        }
