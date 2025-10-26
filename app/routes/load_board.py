from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.config.db import get_db
from app.models.userModels import Users, Companies
from app.models.simple_load import SimpleLoad
from app.models.load_board import LoadBoard, LoadBooking
from app.schema.load_board import (
    LoadBoardCreate, LoadBoardUpdate, LoadBoardResponse, 
    LoadBookingCreate, LoadBookingUpdate, LoadBookingResponse
)
from app.routes.user import get_current_user

router = APIRouter()

def get_current_company_id(current_user: Users = Depends(get_current_user)) -> str:
    """Get current user's company ID"""
    return current_user.companyid

@router.get("/load-board", response_model=List[LoadBoardResponse])
async def get_available_loads(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    pickup_location: Optional[str] = None,
    delivery_location: Optional[str] = None,
    min_rate: Optional[float] = None,
    max_rate: Optional[float] = None
):
    """Get available loads from the load board"""
    try:
        query = db.query(LoadBoard).filter(LoadBoard.is_available == True)
        
        # Apply filters
        if pickup_location:
            query = query.join(SimpleLoad).filter(
                SimpleLoad.pickupLocation.ilike(f"%{pickup_location}%")
            )
        
        if delivery_location:
            query = query.join(SimpleLoad).filter(
                SimpleLoad.deliveryLocation.ilike(f"%{delivery_location}%")
            )
        
        if min_rate:
            query = query.filter(LoadBoard.posted_rate >= min_rate)
        
        if max_rate:
            query = query.filter(LoadBoard.posted_rate <= max_rate)
        
        loads = query.offset(skip).limit(limit).all()
        return loads
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch available loads: {str(e)}"
        )

@router.post("/load-board", response_model=LoadBoardResponse)
async def post_load_to_board(
    load_data: LoadBoardCreate,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Post a load to the load board (brokers only)"""
    try:
        # Verify user is a broker
        company = db.query(Companies).filter(
            Companies.id == current_user.companyid,
            Companies.businessType == "brokerage"
        ).first()
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only brokerage companies can post loads"
            )
        
        # Verify load exists and belongs to broker
        load = db.query(SimpleLoad).filter(
            SimpleLoad.id == load_data.load_id,
            SimpleLoad.companyId == current_user.companyid
        ).first()
        
        if not load:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Load not found or access denied"
            )
        
        # Check if load is already posted
        existing_post = db.query(LoadBoard).filter(
            LoadBoard.load_id == load_data.load_id,
            LoadBoard.is_available == True
        ).first()
        
        if existing_post:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Load is already posted to the board"
            )
        
        # Create load board entry
        load_board = LoadBoard(
            broker_company_id=current_user.companyid,
            load_id=load_data.load_id,
            posted_rate=load_data.posted_rate,
            commission_percentage=load_data.commission_percentage
        )
        
        db.add(load_board)
        db.commit()
        db.refresh(load_board)
        
        return load_board
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to post load: {str(e)}"
        )

@router.post("/load-board/{load_board_id}/book", response_model=LoadBookingResponse)
async def book_load(
    load_board_id: str,
    booking_data: LoadBookingCreate,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Book a load from the load board (carriers only)"""
    try:
        # Verify user is a carrier
        company = db.query(Companies).filter(
            Companies.id == current_user.companyid,
            Companies.businessType == "carrier"
        ).first()
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only carrier companies can book loads"
            )
        
        # Verify load board entry exists and is available
        load_board = db.query(LoadBoard).filter(
            LoadBoard.id == load_board_id,
            LoadBoard.is_available == True
        ).first()
        
        if not load_board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Load not found or no longer available"
            )
        
        # Check if carrier already has a booking for this load
        existing_booking = db.query(LoadBooking).filter(
            LoadBooking.load_board_id == load_board_id,
            LoadBooking.carrier_company_id == current_user.companyid,
            LoadBooking.status.in_(["pending", "accepted"])
        ).first()
        
        if existing_booking:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have a booking request for this load"
            )
        
        # Create booking
        booking = LoadBooking(
            load_board_id=load_board_id,
            carrier_company_id=current_user.companyid,
            requested_rate=booking_data.requested_rate,
            message=booking_data.message
        )
        
        db.add(booking)
        db.commit()
        db.refresh(booking)
        
        return booking
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to book load: {str(e)}"
        )

@router.get("/my-bookings", response_model=List[LoadBookingResponse])
async def get_my_bookings(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's company's bookings"""
    try:
        bookings = db.query(LoadBooking).filter(
            LoadBooking.carrier_company_id == current_user.companyid
        ).all()
        
        return bookings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch bookings: {str(e)}"
        )

@router.get("/my-posted-loads", response_model=List[LoadBoardResponse])
async def get_my_posted_loads(
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's company's posted loads"""
    try:
        posted_loads = db.query(LoadBoard).filter(
            LoadBoard.broker_company_id == current_user.companyid
        ).all()
        
        return posted_loads
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch posted loads: {str(e)}"
        )

@router.get("/load-board/{load_board_id}/bookings", response_model=List[LoadBookingResponse])
async def get_load_bookings(
    load_board_id: str,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all bookings for a posted load (brokers only)"""
    try:
        # Verify user owns this load board entry
        load_board = db.query(LoadBoard).filter(
            LoadBoard.id == load_board_id,
            LoadBoard.broker_company_id == current_user.companyid
        ).first()
        
        if not load_board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Load board entry not found or access denied"
            )
        
        bookings = db.query(LoadBooking).filter(
            LoadBooking.load_board_id == load_board_id
        ).all()
        
        return bookings
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch bookings: {str(e)}"
        )

@router.put("/load-board/{load_board_id}/bookings/{booking_id}", response_model=LoadBookingResponse)
async def respond_to_booking(
    load_board_id: str,
    booking_id: str,
    response_data: LoadBookingUpdate,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Respond to a booking request (brokers only)"""
    try:
        # Verify user owns this load board entry
        load_board = db.query(LoadBoard).filter(
            LoadBoard.id == load_board_id,
            LoadBoard.broker_company_id == current_user.companyid
        ).first()
        
        if not load_board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Load board entry not found or access denied"
            )
        
        # Find the booking
        booking = db.query(LoadBooking).filter(
            LoadBooking.id == booking_id,
            LoadBooking.load_board_id == load_board_id
        ).first()
        
        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        # Update booking
        if response_data.status:
            booking.status = response_data.status
        if response_data.broker_response:
            booking.broker_response = response_data.broker_response
        if response_data.broker_rate:
            booking.broker_rate = response_data.broker_rate
        
        # If accepted, mark load as unavailable and assign carrier
        if response_data.status == "accepted":
            load_board.is_available = False
            load_board.carrier_company_id = booking.carrier_company_id
            load_board.booking_confirmed_at = datetime.utcnow()
        
        db.commit()
        db.refresh(booking)
        
        return booking
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to respond to booking: {str(e)}"
        )
