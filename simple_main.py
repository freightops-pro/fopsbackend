"""
Simplified FastAPI app for testing
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="FreightOps Pro", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "FreightOps Pro API is running!"}

@app.get("/health/status")
async def health_check():
    return {"status": "ok", "message": "FreightOps API is running"}

@app.get("/health/db")
async def db_health():
    try:
        # Simple database connection test
        import os
        from sqlalchemy import create_engine, text
        
        database_url = os.getenv('DATABASE_URL', 'sqlite:///./test.db')
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        return {"status": "ok", "message": "Database connection successful"}
    except Exception as e:
        return {"status": "error", "message": f"Database connection failed: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

