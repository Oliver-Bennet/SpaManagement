import json
import hashlib
import random
from datetime import date, datetime, timedelta

from flask_sqlalchemy import SQLAlchemy
from unicodedata import category

from spaapp.models import User, UserRole, Category, Bill, Product, BillProduct, Appointment, Service, SystemConfig
from spaapp import db


def get_user_by_id(user_id):
    return User.query.get(user_id)
    
def auth_user(username,password):
    password = hashlib.md5(password.encode("utf-8")).hexdigest()
    # user.role = UserRole(user.role) if isinstance(user.role, str) else user.role
    return User.query.filter(User.username.__eq__(username), User.password.__eq__(password)).first()

def add_user(full_name, username, password, phone, image=None):
    password = hashlib.md5(password.strip().encode('utf-8')).hexdigest()

    user = User(
        full_name=full_name.strip(),
        username=username.strip(),
        password=password,
        phone=phone.strip(),
        image=image
    )

    db.session.add(user)
    db.session.commit()
    return user

# Lễ tân đặt lịch cho khách
appointments = [
{
        "date": "2025-12-21",
        "time": "10:30",
        "customer": "Lan",
        "service": "Massage",
        "staff": "Minh",
        "status": "Đã xác nhận"
    },
    {
        "date": "2025-12-21",
        "time": "14:30",
        "customer": "Hoa",
        "service": "Da mặt",
        "staff": "Hương",
        "status": "Đã xác nhận"
    }
]

def add_product_to_bill(bill_id, product_id, quantity):
    product = Product.query.get(product_id)
    bill = Bill.query.get(bill_id)

    subtotal = product.price * quantity

    bp = BillProduct(
        bill_id=bill_id,
        product_id=product_id,
        quantity=quantity,
        unit_price=product.price,
        subtotal=subtotal
    )

    bill.product_amount += subtotal
    bill.total_amount = bill.service_amount + bill.product_amount

    db.session.add(bp)
    db.session.commit()

def get_services():
    return Service.query.filter_by(active=True).all()

def get_technicians():
    return User.query.filter_by(role=UserRole.TECHNICIAN).all()

def get_customers():
    return User.query.filter_by(role=UserRole.CUSTOMER).all()

def generate_time_slots(start="09:00", end="17:00", step=60):
    slots = []

    cur = datetime.strptime(start, "%H:%M")
    end_time = datetime.strptime(end, "%H:%M")

    while cur < end_time:
        slots.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step)

    return slots

def get_random_technician():
    techs = User.query.filter(
        User.role == "3",
        User.active == True
    ).all()
    return random.choice(techs) if techs else None

def get_available_technicians(date, time):
    max_appt = SystemConfig.query.first().max_appointments_per_tech_per_day

    techs = User.query.filter(
        User.role == UserRole.TECHNICIAN,
        User.active == True
    ).all()

    available = []

    for t in techs:
        count = Appointment.query.filter(
            Appointment.technician_id == t.id,
            Appointment.appointment_date == date
        ).count()

        if count < max_appt:
            available.append(t)

    return available


def get_schedule_by_date(date):
    result = {}
    TIME_SLOTS = generate_time_slots()
    for t in TIME_SLOTS:
        result[t] = None

    for a in appointments:
        if a["date"] == date:
            result[a["time"]] = a

    return result

def load_menu(role):
    with open("data/menu.json", encoding="utf-8") as f:
        menus = json.load(f)

    items = menus.get(str(role))  # list các dict
    return [Category(**item) for item in items]  # trả về list Category

def seed_json(jsonPath, modelClass, transform=None):

    with open(jsonPath, encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        if transform:
            item = transform(item)

        obj = modelClass(**item)
        db.session.add(obj)

    db.session.commit()


def get_bill_data(bill_id):
    bill = Bill.query.get(bill_id)
    if not bill:
        return None

    bill_products = BillProduct.query.filter_by(bill_id=bill.id).all()
    # Gắn product object vào mỗi item để template dễ dùng
    for item in bill_products:
        item.product = Product.query.get(item.product_id)

    subtotal = sum([float(item.subtotal) for item in bill_products]) + float(bill.service_amount)
    discount_amount = subtotal * (float(bill.discount_percent or 0) / 100)
    vat_amount = subtotal * (float(bill.vat_percent or 10) / 100)

    data = {
        "order": bill,
        "order_items": bill_products,
        "subtotal": subtotal,
        "summary": {
            "vat_amount": vat_amount,
            "discount_rate": float(bill.discount_percent or 0),
            "discount_amount": discount_amount,
            "total": subtotal - discount_amount + vat_amount
        }
    }
    return data

def get_bills_for_today():
    today = date.today()

    bills_query = db.session.query(Bill, User).join(User, Bill.customer_id == User.id).filter(
        Bill.created_date.cast(db.Date) == today
    ).all()

    bills = []
    for bill, user in bills_query:
        # Lấy danh sách sản phẩm trong hóa đơn
        bill_products = BillProduct.query.filter_by(bill_id=bill.id).all()
        product_names = [Product.query.get(bp.product_id).name for bp in bill_products]

        # Lấy danh sách dịch vụ, ví dụ nếu có appointment liên kết với bill
        services = []
        if bill.appointment_id:
            appointment = Appointment.query.get(bill.appointment_id)
            if appointment.service:
                services.append(appointment.service.name)
            if appointment.package:
                services.append(appointment.package.name)

        bill_info = {
            "customer": user.full_name,
            "services": " + ".join(services) if services else "Không có dịch vụ",
            "products": ", ".join(product_names) if product_names else "Không có sản phẩm",
            "total": f"{bill.total_amount} đ",
            "status": "paid" if bill.payment_method else "unpaid"
        }
        bills.append(bill_info)
    return bills

def create_bill_from_appointment(appt):
    bill = Bill(
        appointment_id=appt.id,
        customer_id=appt.customer_id,
        service_amount=appt.service.price if appt.service else appt.package.price,
        total_amount=appt.service.price if appt.service else appt.package.price,
        cashier_id=appt.created_by
    )
    db.session.add(bill)
    db.session.commit()


#Trang chu KTV va xem lich tung ngay
def get_appointments_by_technician(technician_id, date):
    return Appointment.query.filter(
        Appointment.technician_id == technician_id,
        Appointment.appointment_date == date,
        Appointment.active == True
    ).order_by(Appointment.start_time).all()

#Trang record
def get_appointment_by_id(appt_id):
    return Appointment.query.get(appt_id)

#Tao lich hen moi (cho le tan va khach)
def create_appointment(customer_id, service_id,
                       appointment_date, start_time,
                       note, created_by):

    appointment_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()
    start_time = datetime.strptime(start_time, "%H:%M").time()

    service = Service.query.get(service_id)

    end_time = (
        datetime.combine(date.today(), start_time)
        + timedelta(minutes=service.duration_minute)
    ).time()

    techs = get_available_technicians(appointment_date)

    if not techs:
        raise Exception("Không có kỹ thuật viên khả dụng")

    technician = random.choice(techs)

    appt = Appointment(
        customer_id=customer_id,
        service_id=service_id,
        technician_id=technician.id,
        appointment_date=appointment_date,
        start_time=start_time,
        end_time=end_time,
        status="pending",
        note=note,
        created_by=created_by
    )

    db.session.add(appt)
    db.session.commit()

#Hoan thanh dich vu (Dong bang)
def complete_appointment(appt_id, note=None):
    appt = get_appointment_by_id(appt_id)
    if appt:
        appt.status = "DONE"
        if note:
            appt.note = note
        db.session.commit()
    return appt

#Lay lich theo ngay
def get_appointments_by_date(date):
    return Appointment.query.filter(
        Appointment.appointment_date == date,
        Appointment.active == True
    ).order_by(Appointment.start_time).all()

#Kiem tra trung lich
def is_time_conflict(technician_id, appointment_date, start_time, end_time):
    return Appointment.query.filter(
        Appointment.technician_id == technician_id,
        Appointment.appointment_date == appointment_date,
        Appointment.start_time < end_time,
        Appointment.end_time > start_time,
        Appointment.active == True
    ).first() is not None

#Huy lich
def cancel_appointment(appt_id):
    appt = get_appointment_by_id(appt_id)
    if appt:
        appt.active = False
        db.session.commit()
    return appt

def serialize_appointment(appt):
    return {
        "customer": appt.get_customer_name(),
        "service": appt.get_service_name(),
        "time": f"{appt.start_time} - {appt.end_time}",
        "status": appt.status
    }
