"""Модели БД автопарка. SQLAlchemy — демо на SQLite, прод на PostgreSQL (только смена DB_URL)."""
from sqlalchemy import Column, Integer, String, BigInteger, Date, DateTime, Boolean, ForeignKey, Text, func
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

ROLES = ("owner", "admin", "driver")
CAR_STATUSES = ("rented", "free", "repair")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    role = Column(String(20), nullable=False, default="driver")  # owner/admin/driver
    phone = Column(String(30))
    created_at = Column(DateTime, server_default=func.now())


class Car(Base):
    __tablename__ = "cars"
    id = Column(Integer, primary_key=True)
    plate = Column(String(20), unique=True, nullable=False)      # госномер
    model = Column(String(120), nullable=False)
    status = Column(String(20), nullable=False, default="free")  # rented/free/repair
    mileage = Column(Integer, default=0)
    to_interval_km = Column(Integer, default=10000)              # интервал ТО
    last_to_mileage = Column(Integer, default=0)
    insurance_until = Column(Date)
    docs_path = Column(String(500))                              # папка документов авто
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    driver = relationship("Driver", back_populates="car")


class Driver(Base):
    __tablename__ = "drivers"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    full_name = Column(String(200), nullable=False)
    license_no = Column(String(40))
    rent_amount = Column(Integer, default=0)                     # аренда ₽/нед
    rent_due_day = Column(Integer, default=1)                    # день недели платежа (0=пн)
    created_at = Column(DateTime, server_default=func.now())
    docs_path = Column(String(500))
    active = Column(Boolean, default=True)
    user = relationship("User")
    car = relationship("Car", back_populates="driver", uselist=False)
    payments = relationship("Payment", back_populates="driver")


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    photo_file_id = Column(String(300))                          # file_id чека
    status = Column(String(20), default="pending")               # pending/confirmed/rejected
    created_at = Column(DateTime, server_default=func.now())
    confirmed_at = Column(DateTime)
    note = Column(Text)
    driver = relationship("Driver", back_populates="payments")


class MileageLog(Base):
    __tablename__ = "mileage_log"
    id = Column(Integer, primary_key=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False)
    mileage = Column(Integer, nullable=False)
    photo_file_id = Column(String(300))
    created_at = Column(DateTime, server_default=func.now())


class Issue(Base):
    __tablename__ = "issues"
    id = Column(Integer, primary_key=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.id"))
    text = Column(Text, nullable=False)
    photo_file_id = Column(String(300))
    status = Column(String(20), default="open")                  # open/closed
    created_at = Column(DateTime, server_default=func.now())
