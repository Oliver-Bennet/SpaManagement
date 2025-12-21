import json
import hashlib
from datetime import date

from flask_sqlalchemy import SQLAlchemy
from unicodedata import category

from spaapp.models import User, UserRole, Category, Bill, Product, BillProduct, Appointment
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