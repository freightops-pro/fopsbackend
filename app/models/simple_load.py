from sqlalchemy import Column, String, DateTime, Numeric, func, Boolean, JSON, Float
from sqlalchemy.orm import relationship
from app.config.db import Base


class SimpleLoad(Base):
    __tablename__ = "simple_loads"

    id = Column(String, primary_key=True, nullable=False)
    companyId = Column(String, nullable=False)

    loadNumber = Column(String, nullable=False)
    customerName = Column(String, nullable=False)
    pickupLocation = Column(String, nullable=False)
    deliveryLocation = Column(String, nullable=False)

    pickupDate = Column(DateTime)
    deliveryDate = Column(DateTime)
    pickuptime = Column(DateTime)  # for UI convenience

    rate = Column(Numeric, default=0)
    notes = Column(String)
    status = Column(String, default="pending")
    priority = Column(String, default="normal")  # normal, low, medium, high, urgent

    assignedDriverId = Column(String)
    assignedTruckId = Column(String)

    # Truck assignment flow fields
    truckAssignmentStatus = Column(String, default="truck_assignment_required")  # truck_assignment_required, truck_assigned, driver_confirmed, trailer_set, truck_confirmed
    truckAssignmentTime = Column(DateTime)
    driverConfirmationTime = Column(DateTime)
    trailerSetupTime = Column(DateTime)
    truckConfirmationTime = Column(DateTime)

    # Pickup flow fields
    pickupStatus = Column(String, default="pending")  # pending, navigation, arrived, trailer_confirmed, container_confirmed, pickup_confirmed, departed
    navigationStartTime = Column(DateTime)
    pickupArrivalTime = Column(DateTime)
    trailerConfirmationTime = Column(DateTime)
    containerConfirmationTime = Column(DateTime)
    pickupConfirmationTime = Column(DateTime)
    departureTime = Column(DateTime)
    billOfLadingUrl = Column(String)
    pickupNotes = Column(String)

    # Delivery flow fields
    deliveryStatus = Column(String, default="in_transit")  # in_transit, arrived, docked, unloading, delivered
    arrivalTime = Column(DateTime)
    dockingTime = Column(DateTime)
    unloadingStartTime = Column(DateTime)
    unloadingEndTime = Column(DateTime)
    deliveryTime = Column(DateTime)
    proofOfDeliveryUrl = Column(String)
    recipientName = Column(String)
    deliveryNotes = Column(String)

    # Store all additional form fields (commodity, trailerType, container specifics, etc.)
    meta = Column(JSON)

    # Driver mobile location tracking
    current_driver_latitude = Column(Float, nullable=True)
    current_driver_longitude = Column(Float, nullable=True)
    last_location_update = Column(DateTime, nullable=True)
    
    # Pickup location verification
    actual_pickup_latitude = Column(Float, nullable=True)
    actual_pickup_longitude = Column(Float, nullable=True)
    actual_pickup_time = Column(DateTime, nullable=True)
    
    # Delivery location verification
    actual_delivery_latitude = Column(Float, nullable=True)
    actual_delivery_longitude = Column(Float, nullable=True)
    actual_delivery_time = Column(DateTime, nullable=True)
    
    # Route tracking (JSON array of location points)
    route_history = Column(JSON, nullable=True)

    createdAt = Column(DateTime, server_default=func.now())
    updatedAt = Column(DateTime, server_default=func.now(), onupdate=func.now())
    isActive = Column(Boolean, default=True)
    
    # Relationships
    load_board_entry = relationship("LoadBoard", back_populates="load", uselist=False)
    legs = relationship("LoadLeg", back_populates="load")


