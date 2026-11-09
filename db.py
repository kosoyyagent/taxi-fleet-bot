import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

# демо: sqlite:///fleet.db; прод: postgresql+psycopg2://user:pass@host/fleet
DB_URL = os.getenv("FLEET_DB_URL", "sqlite:///fleet.db")

engine = create_engine(DB_URL, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    Base.metadata.create_all(engine)
