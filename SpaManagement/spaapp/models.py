# app/models.py
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Numeric, Text, Date, Time,  ForeignKey, Enum
from enum import Enum as RoleEnum
from flask_login import UserMixin
from sqlalchemy.orm import validates

from spaapp import db

class Category(db.Model):
    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(String(50), nullable=False)
    url = Column(String(50), nullable=False)

class UserRole(RoleEnum):
    MANAGER = "1"
    RECEPTIONIST = "2"
    TECHNICIAN = "3"
    CASHIER = "4"
    CUSTOMER = "5"

class Base(db.Model):
    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    active = Column(Boolean, default=True)
    created_date = Column(DateTime, default=datetime.now())
# 1
class User(Base, UserMixin):
    __tablename__ = 'users'

    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(15), unique=True, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.CUSTOMER)
    image = Column(String(300), default="https://res.cloudinary.com/dy1unykph/image/upload/v1740037805/apple-iphone-16-pro-natural-titanium_lcnlu2.webp")

    def get_id(self):
        return str(self.id)  # Flask-Login yêu cầu trả về string

    def __str__(self):
        return self.full_name

    def __repr__(self):
        return f'<User {self.full_name} - {self.role.value}>'
#2
# from abc import ABC, abstractmethod

# class ServiceComponent(ABC):
#     @abstractmethod
#     def get_price(self):
#         pass

#     @abstractmethod
#     def get_duration(self):
#         pass

#     @abstractmethod
#     def get_name(self):
#         pass

#     @abstractmethod
#     def get_details(self):
#         pass

class Service(Base):#, ServiceComponent):
    __tablename__ = 'services'

    name = Column(String(150), nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    duration_minute = Column(Integer, nullable=False)
    category = Column(String(50))

    def get_price(self):
        return self.price

    def get_duration(self):
        return self.duration_minute

    def get_name(self):
        return self.name

    def get_details(self):
        return [self]  # chỉ có chính nó

    def __str__(self):
        return self.name

    @validates('duration_minute')
    def validate_duration(self, key, duration):
        if duration < 15 or duration > 120:
            raise ValueError("Thời lượng dịch vụ phải từ 15 đến 120 phút theo quy định!")
        return duration
#3
class ServicePackage(Base):
    __tablename__ = 'service_packages'

    name = Column(String(150), nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    description = Column(Text)

    def get_price(self):
        return self.price  # dùng giá cố định của gói (hoặc tính động nếu muốn)

    def get_duration(self):
        return sum(component.service.get_duration() for component in self.components)

    def get_name(self):
        return self.name

    def get_details(self):
        details = []
        for comp in self.components:
            details.extend(comp.service.get_details())
        return details

    def __str__(self):
        return self.name
# còn vụ composite pattern nữa
#4
class Product(Base):
    __tablename__ = 'products'

    name = Column(String(150), nullable=False)
    price = Column(Numeric(12, 2), nullable=False)
    stock = Column(Integer, default=0)
    warning_stock = Column(Integer, default=10)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f'<Product "{self.name}">'
#5
class Appointment(Base):
    __tablename__ = 'appointments'

    customer_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    service_id = Column(Integer, ForeignKey('services.id'), nullable=True)
    package_id = Column(Integer, ForeignKey('service_packages.id'), nullable=True)
    technician_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    appointment_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    status = Column(String(20), default='pending')
    note = Column(Text)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)

    # ===== RELATIONSHIP =====
    customer = db.relationship("User", foreign_keys=[customer_id])
    technician = db.relationship("User", foreign_keys=[technician_id])
    creator = db.relationship("User", foreign_keys=[created_by])

    service = db.relationship("Service")
    package = db.relationship("ServicePackage")

    def __repr__(self):
        return f'<Appointment {self.id} - {self.appointment_date}>'

    def get_service_name(self):
        if self.service:
            return self.service.name
        if self.package:
            return self.package.name
        return "Không xác định"

    def get_customer_name(self):
        return self.customer.full_name if self.customer else "Không xác định"
# ---> còn vụ composite pattern và appointmentservice nữa
#6
class ServiceRecord(Base):
    __tablename__ = 'service_records'

    appointment_id = Column(Integer, ForeignKey('appointments.id'), unique=True, nullable=False)
    actual_start = Column(DateTime)
    actual_end = Column(DateTime)
    technician_note = Column(Text)
    customer_feedback = Column(Text)
    rating = Column(Integer)  # 1-5
#7
class Bill(Base):
    __tablename__ = 'bills'

    appointment_id = Column(Integer, ForeignKey('appointments.id'), nullable=True)
    customer_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    service_amount = Column(Numeric(12, 2), default=0)
    product_amount = Column(Numeric(12, 2), default=0)
    discount_percent = Column(Numeric(5, 2), default=0)
    vat_percent = Column(Numeric(5, 2), default=10)
    total_amount = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(String(20))
    cashier_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    customer = db.relationship("User", foreign_keys=[customer_id], backref="bills")
    cashier = db.relationship("User", foreign_keys=[cashier_id])
    products = db.relationship("BillProduct", backref="bill")
    appointment = db.relationship("Appointment", backref="bills")
#8
class BillProduct(db.Model):
    __tablename__ = 'bill_products'

    bill_id = Column(Integer, ForeignKey('bills.id'), primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), primary_key=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)

    product = db.relationship("Product", backref="bill_products")

#9
class DailyRevenueReport(Base):
    __tablename__ = 'daily_revenue_reports'

    report_date = Column(Date, nullable=False)
    cashier_id = Column(Integer, db.ForeignKey('users.id'), nullable=False)
    cash_amount = Column(Numeric(12, 2), default=0)
    transfer_amount = Column(Numeric(12, 2), default=0)
    total_bills = Column(Integer, default=0)
    note = Column(Text)
#10
class StaffShift(Base):
    __tablename__ = 'staff_shifts'

    technician_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    shift_date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
#11
class SystemConfig(db.Model):
    __tablename__ = 'system_config'

    id = Column(Integer, primary_key=True, default=1)
    vat_percent = Column(Numeric(5, 2), default=10)
    max_discount_percent = Column(Numeric(5, 2), default=20)
    max_appointments_per_tech_per_day = Column(db.Integer, default=5)
    updated_by = Column(Integer, ForeignKey('users.id'))
    updated_at = Column(DateTime, default=datetime.now())