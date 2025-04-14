from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os
from dotenv import load_dotenv
from datetime import datetime

# Загрузка переменных окружения
load_dotenv()

# Настройка базы данных
Base = declarative_base()

class Tour(Base):
    __tablename__ = 'tours'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1000))
    image_path = Column(String(255))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    price = Column(Integer, nullable=False)
    total_seats = Column(Integer, nullable=False)
    available_seats = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)
    bookings = relationship("Booking", back_populates="tour")

class Booking(Base):
    __tablename__ = 'bookings'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    user_name = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=False)
    tour_id = Column(Integer, ForeignKey('tours.id'), nullable=False)
    tour = relationship("Tour", back_populates="bookings")
    booking_date = Column(Date, default=datetime.now, nullable=False)
    is_active = Column(Boolean, default=True)

# Создание подключения к PostgreSQL
DB_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
engine = create_engine(DB_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine) 