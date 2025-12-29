import json
import hashlib
import random
from datetime import date, datetime, timedelta

from flask_sqlalchemy import SQLAlchemy
from unicodedata import category

from spaapp.models import User, UserRole, Category, Bill, Product, BillProduct, Appointment, Service, SystemConfig
from spaapp import db
from sqlalchemy import extract, func


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


def suggest_discount(user_id, current_bill_amount):
    discount_percent = 0
    reason = "Không có khuyến mãi"

    # 1. Lấy tổng chi tiêu tích lũy (VIP)
    total_spending, _ = get_customer_spending_stats(user_id)
    # Chính sách 1: VIP (> 10 triệu) -> Giảm 5%
    if total_spending >= 10000000:
        discount_percent = 5
        reason = "Khách hàng VIP (Chi tiêu > 10tr)"

    # Chính sách 2: Hóa đơn lớn (> 3 triệu) -> Giảm 10%
    # Ưu tiên mức giảm cao hơn
    if current_bill_amount >= 3000000:
        if 10 > discount_percent:
            discount_percent = 10
            reason = "Hóa đơn giá trị cao (> 3tr)"

    # Kiểm tra Config giới hạn giảm giá tối đa (ví dụ max 20%)
    config = SystemConfig.query.first()
    if config and discount_percent > config.max_discount_percent:
        discount_percent = config.max_discount_percent
        reason = f"Đã giới hạn tối đa {config.max_discount_percent}%"

    return discount_percent, reason

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

def get_available_technician(date):
    config = SystemConfig.query.first()
    max_per_day = config.max_appointments_per_tech_per_day

    technicians = User.query.filter(
        User.role == UserRole.TECHNICIAN,
        User.active == True
    ).all()

    available = []
    for t in technicians:
        if count_appointments_of_technician(t.id, date) < max_per_day:
            available.append(t)

    return random.choice(available) if available else None


def get_schedule_by_date(date):
    result = {}
    TIME_SLOTS = generate_time_slots()

    for t in TIME_SLOTS:
        result[t] = None

    # Lấy các lịch hẹn Active trong ngày từ Database
    db_appointments = Appointment.query.filter(
        Appointment.appointment_date == date,
        Appointment.active == True
    ).all()

    # Map lịch hẹn vào các khung giờ
    for a in db_appointments:
        time_key = a.start_time.strftime("%H:%M")
        if time_key in result:
            result[time_key] = a

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
            "id": bill.id,
            "customer": user.full_name,
            "services": " + ".join(services) if services else "Không có dịch vụ",
            "products": ", ".join(product_names) if product_names else "Không có sản phẩm",
            "total": f"{bill.total_amount} đ",
            "status": "paid" if bill.payment_method else "unpaid"
        }
        bills.append(bill_info)
    return bills


def get_recent_bills():
    today = date.today()
    yesterday = today - timedelta(days=1)

    bills_query = db.session.query(Bill, User).join(User, Bill.customer_id == User.id).filter(
        Bill.created_date.cast(db.Date) <= yesterday
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
            "id": bill.id,
            "customer": user.full_name,
            "services": " + ".join(services) if services else "Không có dịch vụ",
            "products": ", ".join(product_names) if product_names else "Không có sản phẩm",
            "total": f"{bill.total_amount} đ",
            "status": "paid" if bill.payment_method else "unpaid"
        }
        bills.append(bill_info)
    return bills

def pay_bill(bill_id, payment_method, discount_percent=0):  # Thêm tham số discount_percent
    bill = Bill.query.get(bill_id)
    if bill:
        bill.payment_method = payment_method
        bill.discount_percent = discount_percent

        # Tính toán lại tổng tiền cuối cùng trước khi lưu
        # Logic: (Dịch vụ + Sản phẩm) - Giảm giá + VAT
        subtotal = float(bill.service_amount) + float(bill.product_amount)
        discount_amount = subtotal * (discount_percent / 100)
        after_discount = subtotal - discount_amount
        vat_amount = after_discount * (float(bill.vat_percent) / 100)

        bill.total_amount = after_discount + vat_amount

        # (Tùy chọn) Cập nhật trạng thái nếu có cột status
        # bill.status = 'paid'

        db.session.commit()
        return True
    return False

def create_bill_from_appointment(appt):
    config = SystemConfig.query.first()
    vat = config.vat_percent

    price = appt.service.price if appt.service else appt.package.price
    vat_amount = price * vat / 100
    total = price + vat_amount

    bill = Bill(
        appointment_id=appt.id,
        customer_id=appt.customer_id,
        service_amount=price,
        vat_percent=vat,
        total_amount=total,
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
                       note, created_by, technician_id=None):  # technician_id mặc định là None

    appointment_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()
    start_time = datetime.strptime(start_time, "%H:%M").time()

    service = Service.query.get(service_id)

    # Tính giờ kết thúc
    end_time = (
            datetime.combine(date.today(), start_time)
            + timedelta(minutes=service.duration_minute)
    ).time()

    # TRƯỜNG HỢP 1: NẾU CÓ technician_id (Do Lễ tân chọn hoặc Phân công sau này)
    if technician_id:
        technician = User.query.get(int(technician_id))

        config = SystemConfig.query.first()
        max_customers = config.max_appointments_per_tech_per_day
        current_count = count_appointments_of_technician(technician_id, appointment_date)

        if current_count >= max_customers:
            raise Exception(f"KTV {technician.full_name} đã nhận đủ {max_customers} khách trong ngày!")

        # 2. Check trùng giờ
        if is_time_conflict(technician.id, appointment_date, start_time, end_time):
            raise Exception(f"KTV {technician.full_name} bị trùng lịch lúc {start_time}!")

        status = "confirmed"  # Đã có nhân viên -> Đã xác nhận

    # TRƯỜNG HỢP 2: KHÁCH TỰ ĐẶT (Chưa có KTV)
    else:
        technician_id = None
        status = "pending"  # Chờ phân công

    appt = Appointment(
        customer_id=customer_id,
        service_id=service_id,
        technician_id=technician_id,  # Có thể là ID hoặc None
        appointment_date=appointment_date,
        start_time=start_time,
        end_time=end_time,
        status=status,
        note=note,
        created_by=created_by
    )

    db.session.add(appt)
    db.session.commit()
    return appt


def assign_technician(appt_id, technician_id):
    appt = Appointment.query.get(appt_id)
    if not appt:
        return False, "Không tìm thấy lịch hẹn"

    # Gọi lại logic kiểm tra trùng lịch/số lượng khách ở trên
    # (Bạn có thể tách logic check ở bước 2 ra hàm riêng để tái sử dụng,
    # nhưng viết thẳng vào đây cũng được cho nhanh)

    appointment_date = appt.appointment_date

    # 1. Check giới hạn
    config = SystemConfig.query.first()
    if count_appointments_of_technician(technician_id, appointment_date) >= config.max_appointments_per_tech_per_day:
        return False, "Kỹ thuật viên này đã đầy lịch hôm nay"

    # 2. Check trùng giờ
    if is_time_conflict(technician_id, appointment_date, appt.start_time, appt.end_time):
        return False, "Kỹ thuật viên bị trùng giờ với lịch khác"

    # Nếu thỏa mãn hết: Update
    appt.technician_id = technician_id
    appt.status = "confirmed"  # Đổi trạng thái sang Đã xác nhận
    db.session.commit()

    return True, "Phân công thành công"

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

#5 khach/ktv/ngay
def count_appointments_of_technician(technician_id, date):
    return Appointment.query.filter(
        Appointment.technician_id == technician_id,
        Appointment.appointment_date == date,
        Appointment.active == True
    ).count()

def stats_service_usage_by_month(month, year):
    # Đếm số lần xuất hiện của dịch vụ trong bảng Appointment theo tháng/năm
    return db.session.query(Service.name, func.count(Appointment.id))\
             .join(Appointment, Appointment.service_id == Service.id)\
             .filter(extract('month', Appointment.appointment_date) == month)\
             .filter(extract('year', Appointment.appointment_date) == year)\
             .group_by(Service.name).all()


def get_upcoming_appointments_by_customer(user_id):
    today = date.today()
    return Appointment.query.filter(
        Appointment.customer_id == user_id,
        Appointment.appointment_date >= today,
        Appointment.status != 'DONE',  # Chỉ lấy lịch chưa hoàn thành
        Appointment.active == True
    ).order_by(Appointment.appointment_date, Appointment.start_time).limit(5).all()


def get_customer_spending_stats(user_id):
    # Tính tổng chi tiêu trọn đời
    total_query = db.session.query(func.sum(Bill.total_amount)) \
        .filter(Bill.customer_id == user_id).scalar()

    total_all_time = total_query if total_query else 0

    # Tính tổng chi tiêu tháng này
    current_month = datetime.now().month
    current_year = datetime.now().year

    monthly_query = db.session.query(func.sum(Bill.total_amount)) \
        .filter(Bill.customer_id == user_id,
                extract('month', Bill.created_date) == current_month,
                extract('year', Bill.created_date) == current_year).scalar()

    total_month = monthly_query if monthly_query else 0

    return total_all_time, total_month


def stats_revenue_by_month(month=None, year=None):
    if not month:
        month = datetime.now().month
    if not year:
        year = datetime.now().year

    # Query tổng tiền theo từng ngày
    # extract('day', ...) lấy ngày trong tháng (1, 2, ..., 31)
    query = db.session.query(
        extract('day', Bill.created_date),
        func.sum(Bill.total_amount)
    ).filter(
        extract('month', Bill.created_date) == month,
        extract('year', Bill.created_date) == year
    ).group_by(
        extract('day', Bill.created_date)
    ).all()
    return query


def get_top_services(month=None, year=None, limit=5):
    if not month: month = datetime.now().month
    if not year: year = datetime.now().year

    return db.session.query(
        Service.name,
        func.count(Appointment.id).label('count')
    ).join(Appointment, Appointment.service_id == Service.id) \
        .filter(
        extract('month', Appointment.appointment_date) == month,
        extract('year', Appointment.appointment_date) == year,
        Appointment.status == 'DONE'  # Chỉ tính các lịch đã hoàn thành
    ).group_by(Service.name) \
        .order_by(func.count(Appointment.id).desc()) \
        .limit(limit).all()


def get_total_revenue(month=None, year=None):
    if not month: month = datetime.now().month
    if not year: year = datetime.now().year

    return db.session.query(func.sum(Bill.total_amount)) \
        .filter(
        extract('month', Bill.created_date) == month,
        extract('year', Bill.created_date) == year
    ).scalar() or 0


def get_receptionist_stats():
    today = date.today()
    now_time = datetime.now().time()

    today_appts = Appointment.query.filter(
        Appointment.appointment_date == today,
        Appointment.active == True
    ).all()

    total_today = len(today_appts)

    pending_count = Appointment.query.filter(
        Appointment.status == 'pending',
        Appointment.active == True,
        Appointment.appointment_date >= today
    ).count()

    technician_count = User.query.filter(User.role == UserRole.TECHNICIAN, User.active == True).count()

    total_slots_per_day = len(generate_time_slots())

    max_capacity = technician_count * total_slots_per_day
    empty_slots = max_capacity - total_today
    if empty_slots < 0: empty_slots = 0

    return {
        "total_today": total_today,
        "pending": pending_count,
        "empty_slots": empty_slots
    }


def get_or_create_guest_customer(full_name, phone):
    existing_user = User.query.filter_by(phone=phone).first()
    if existing_user:
        return existing_user

    # Username sẽ là SĐT, Password mặc định là 123456 (hash md5)
    import hashlib
    default_password = hashlib.md5("123456".encode('utf-8')).hexdigest()

    new_user = User(
        full_name=full_name,
        username=phone,  # Dùng SĐT làm username luôn
        password=default_password,
        phone=phone,
        role=UserRole.CUSTOMER,
        image="https://res.cloudinary.com/dy1unykph/image/upload/v1740037805/default-avatar.webp"  # Ảnh mặc định
    )

    db.session.add(new_user)
    db.session.commit()

    return new_user