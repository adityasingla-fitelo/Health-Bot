from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# 🔹 SQLAlchemy Engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,    
    pool_size=5,
    max_overflow=10,
    future=True,            
)

# 🔹 Session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  
)

# 🔹 Base class for models
Base = declarative_base()


def init_db():
    """
    Initializes database tables.
    Should be called once on application startup.
    """
    from app.db import models  

    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI dependency that provides a DB session
    and ensures it's closed after request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
