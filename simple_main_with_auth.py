"""
Simplified FastAPI app with authentication for testing login error messages
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, text
import os
import hashlib
import hmac

app = FastAPI(title="FreightOps Pro", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./test.db')
engine = create_engine(DATABASE_URL)

# Request models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    customerId: str = None

@app.get("/")
async def root():
    return {"message": "FreightOps Pro API is running!"}

@app.get("/health/status")
async def health_check():
    return {"status": "ok", "message": "FreightOps API is running"}

@app.get("/health/db")
async def db_health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "message": "Database connection successful"}
    except Exception as e:
        return {"status": "error", "message": f"Database connection failed: {str(e)}"}

@app.post("/api/login")
async def login(req_body: LoginRequest):
    """Login endpoint with improved error messages"""
    email = req_body.email
    password = req_body.password
    
    # Input validation
    if not email or not password:
        raise HTTPException(
            status_code=400,
            detail="Email and password are required"
        )
    
    # For testing purposes, we'll simulate a failed login
    # In a real app, this would check against the database
    if email == "test@example.com" and password == "wrongpassword":
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password. Please check your credentials and try again."
        )
    
    # Simulate other error cases
    if not email or "@" not in email:
        raise HTTPException(
            status_code=400,
            detail="Please enter a valid email address"
        )
    
    if len(password) < 6:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters long"
        )
    
    # For successful login (this won't be reached with the test credentials)
    return {
        "success": True,
        "message": "Login successful",
        "token": "fake-jwt-token"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
