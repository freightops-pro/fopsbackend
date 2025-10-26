from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool
from app.config.settings import settings
from app.config.connection_pool import connection_pool_manager
from urllib.parse import urlparse

# Parse the database URL
url = settings.DATABASE_URL
parsed = urlparse(url)

# Default connect_args
connect_args = {}

if "neon.tech" in (parsed.hostname or ""):
    # Neon-specific optimizations
    connect_args = {
        "sslmode": "require",
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
        "channel_binding": "require"
    }

# Create database engine
if settings.ENVIRONMENT == "test":
    # Use in-memory SQLite for testing
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
elif settings.DATABASE_URL.startswith("sqlite"):
    # Use SQLite for development
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
        # Use optimized connection pool for production (5000+ users)
        engine = connection_pool_manager.create_engine()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base
Base = declarative_base()

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create all tables
def create_tables():
    Base.metadata.create_all(bind=engine)



# ----------------For production-----------------------------

# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker, declarative_base
# from sqlalchemy.pool import StaticPool
# from app.config.settings import settings
# from urllib.parse import urlparse

# # Parse the database URL
# url = settings.DATABASE_URL
# parsed = urlparse(url)

# # Default connect_args
# connect_args = {}

# if "neon.tech" in (parsed.hostname or ""):
#     connect_args = {
#         "sslmode": "require",
#         "keepalives": 1,
#         "keepalives_idle": 30,
#         "keepalives_interval": 10,
#         "keepalives_count": 5,
#     }

# # Create database engine
# if settings.ENVIRONMENT == "test":
#     engine = create_engine(
#         "sqlite:///:memory:",
#         connect_args={"check_same_thread": False},
#         poolclass=StaticPool,
#     )
# elif settings.DATABASE_URL.startswith("sqlite"):
#     engine = create_engine(
#         settings.DATABASE_URL,
#         connect_args={"check_same_thread": False},
#         poolclass=StaticPool,
#     )
# else:
#     engine = create_engine(
#         settings.DATABASE_URL,
#         pool_pre_ping=True,
#         pool_recycle=300,
#         pool_size=5,
#         max_overflow=10,
#         connect_args=connect_args,
#     )

# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base = declarative_base()

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()

# def create_tables():
#     Base.metadata.create_all(bind=engine)
