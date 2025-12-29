import calendar
import json

import cloudinary
from flask import Flask, render_template, request, redirect, url_for, abort, flash, jsonify
from flask_login import current_user, login_user,  login_required, logout_user
from spaapp import dao, db
from spaapp import login_manager, app
from spaapp.models import UserRole, User, Service, Bill, ServiceRecord
from datetime import date, datetime, timedelta
from dao import get_schedule_by_date
from datetime import  date
from types import SimpleNamespace

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/customer/")
def customer_home():
    menu = dao.load_menu(UserRole.CUSTOMER.value)
    upcoming_appts = dao.get_upcoming_appointments_by_customer(current_user.id)
    total_spending, monthly_spending = dao.get_customer_spending_stats(current_user.id)
    return render_template("customerLayout/index.html",
                           menu=menu,
                           now=datetime.now,
                           upcoming_appointments=upcoming_appts,
                           total_spending=total_spending,
                           monthly_spending=monthly_spending
                           )


@app.route("/customer/book", methods=["GET", "POST"])
@login_required
def customer_book():
    if current_user.role != UserRole.CUSTOMER:
        abort(403)
    menu = dao.load_menu(UserRole.CUSTOMER.value)

    if request.method == "POST":
        try:
            date_str = request.form.get("date")
            time_str = request.form.get("start_time")

            booking_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            if booking_dt < datetime.now():
                raise Exception("Không thể đặt lịch khi đã qua giờ!")

            dao.create_appointment(
                customer_id=current_user.id,
                service_id=request.form.get("service_id"),
                appointment_date=date_str,
                start_time=time_str,
                note=request.form.get("note"),
                created_by=current_user.id
            )
            flash("Đặt lịch thành công!", "success")
        except Exception as e:
            flash(str(e), "danger")

        return redirect(url_for("customer_book"))

    return render_template(
        "customerLayout/book.html",
        services=dao.get_services(),
        time_slots=dao.generate_time_slots(),
        menu=menu
    )

@app.route("/customer/profile")
def customer_profile():
    menu = dao.load_menu(UserRole.CUSTOMER.value)
    return render_template("customerLayout/profile.html", menu=menu)

# @app.route("/customer/book")
# def customer_book():
#     menu = dao.load_menu(UserRole.CUSTOMER.value)
#     date = request.args.get("date")
#     time = request.args.get("time")
#     services = Service.query.filter(Service.active == True).all()
#     return render_template("receptionistLayout/book.html", date=date, time=time, services=services, menu=menu)


@app.route("/customer/history")
def customer_history():
    menu = dao.load_menu(UserRole.CUSTOMER.value)
    return render_template("customerLayout/history.html", menu=menu)

@app.route("/customer/appointments")
def customer_appointments():
    menu = dao.load_menu(UserRole.CUSTOMER.value)
    return render_template("customerLayout/appointments.html", menu=menu)



@app.route("/receptionist/")
def receptionist_home():
    if current_user.role != UserRole.RECEPTIONIST:
        abort(403)
    menu = dao.load_menu(UserRole.RECEPTIONIST.value)
    today = datetime.today()
    stats = dao.get_receptionist_stats()
    return render_template("receptionistLayout/index.html", today=today, menu=menu, stats=stats)

@app.route("/receptionist/calendar")
@login_required
def receptionist_calendar():
    if current_user.role != UserRole.RECEPTIONIST:
        abort(403)
    menu = dao.load_menu(UserRole.RECEPTIONIST.value)
    today = datetime.now().date()
    selected_date = request.args.get("date")

    if selected_date:
        selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
    else:
        selected_date = today

    days = [today + timedelta(days=i) for i in range(-1, 6)]

    schedule = get_schedule_by_date(selected_date)
    technicians = dao.get_technicians()
    return render_template("receptionistLayout/calendar.html",
                           days=days,
                           selected_date=selected_date,
                           schedule=schedule,
                           now=datetime.now,
                           today=date.today(),
                           menu=menu,
                           technicians=technicians
                           )
@app.route("/receptionist/book", methods=["GET", "POST"])
@login_required
def receptionist_book():
    if current_user.role != UserRole.RECEPTIONIST:
        abort(403)

    menu = dao.load_menu(UserRole.RECEPTIONIST.value)

    date = request.args.get("date")
    time = request.args.get("time")

    customers = dao.get_customers()

    technicians = dao.get_technicians()
    services = dao.get_services()

    if request.method == "POST":
        try:
            # KIỂM TRA LOGIC KHÁCH HÀNG
            customer_id = request.form.get("customer_id")
            new_fullname = request.form.get("new_fullname")
            new_phone = request.form.get("new_phone")

            # Nếu có nhập tên mới -> Tức là đang dùng chế độ Khách mới
            if new_fullname and new_phone:
                # Gọi hàm DAO vừa viết để tạo hoặc lấy user
                customer = dao.get_or_create_guest_customer(new_fullname, new_phone)
                customer_id = customer.id

            # Nếu không có customer_id (trường hợp quên chọn)
            if not customer_id:
                raise Exception("Vui lòng chọn khách hàng hoặc nhập thông tin khách mới")

            dao.create_appointment(
                customer_id=customer_id,  # Dùng ID đã xử lý ở trên
                service_id=request.form.get("service_id"),
                appointment_date=request.form.get("date"),
                start_time=request.form.get("start_time"),
                technician_id=request.form.get("technician_id"),
                note=request.form.get("note"),
                created_by=current_user.id
            )
            flash("Đặt lịch thành công!", "success")
        except Exception as e:
            flash(str(e), "danger")

    return render_template(
        "receptionistLayout/book.html",
        date=date,
        time=time,
        services=services,
        technicians=technicians,
        menu=menu,
        customers=customers
    )


@app.route("/receptionist/assign-technician", methods=["POST"])
@login_required
def assign_technician_route():
    if current_user.role != UserRole.RECEPTIONIST:
        abort(403)

    appt_id = request.form.get("appointment_id")
    tech_id = request.form.get("technician_id")

    success, message = dao.assign_technician(appt_id, tech_id)

    if success:
        # Lấy thông tin KTV để trả về cho giao diện hiển thị
        tech = User.query.get(tech_id)
        return jsonify({
            "status": "success",
            "message": message,
            "tech_name": tech.full_name
        })
    else:
        return jsonify({"status": "error", "message": message}), 400

#KTV
@app.route("/technician")
@login_required
def technician_home():
    if current_user.role != UserRole.TECHNICIAN:
        abort(403)

    # Lấy ngày từ URL hoặc mặc định là hôm nay ---
    date_str = request.args.get("date")
    today = date.today()

    if date_str:
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            selected_date = today
    else:
        selected_date = today

    days = [today + timedelta(days=i) for i in range(-1, 6)]
    appointments = dao.get_appointments_by_technician(current_user.id, selected_date)
    data = [dao.serialize_appointment(a) for a in appointments]
    return render_template(
        "technicianLayout/index.html",
        today=today,
        selected_date=selected_date,
        days=days,
        today_appointments=appointments,
        appointments=data
    )

@app.route("/technician/record/<int:appt_id>", methods=["GET", "POST"])
@login_required
def technician_record(appt_id):
    appt = dao.get_appointment_by_id(appt_id)

    if not appt:
        return "Không tìm thấy lịch hẹn", 404

    if request.method == "POST":
        tech_note = request.form.get("technician_note")
        cust_feedback = request.form.get("customer_feedback")
        rating_val = request.form.get("rating")

        appt.status = "DONE"
        dao.create_bill_from_appointment(appt)

        appt_record = ServiceRecord(
            appointment_id=appt.id,
            actual_start=datetime.now(),
            actual_end=datetime.now(),
            technician_note=tech_note,
            customer_feedback=cust_feedback,
            rating=int(rating_val) if rating_val else 5
        )

        db.session.add(appt_record)
        db.session.commit()

        flash("Đã hoàn thành dịch vụ và lưu hồ sơ!", "success")

        return redirect(url_for('technician_home', date=appt.appointment_date))

    return render_template(
        "technicianLayout/record.html",
        appt=appt
    )

@app.route("/cashier/")
def cashier_home():
    menu = dao.load_menu(UserRole.CASHIER.value)
    recent_bills = dao.get_recent_bills()
    today = datetime.today()
    bills = dao.get_bills_for_today()
    print(bills)
    return render_template("cashierLayout/index.html", today=today, menu=menu, bills=bills, recent_bills=recent_bills)



@app.route("/cashier/bill/<int:bill_id>")
@login_required
def bill_new(bill_id):
    if current_user.role != UserRole.CASHIER:
        abort(403)

    data = dao.get_bill_data(bill_id)

    if not data:
        flash("Không tìm thấy hóa đơn!", "danger")
        return redirect(url_for('cashier_home'))

    discount = 0
    discount_reason = ""

    # Nếu hóa đơn chưa chốt (chưa có discount), thì tính toán gợi ý
    if data['order'].discount_percent == 0:
        subtotal = data['subtotal']  # Tổng tiền chưa thuế/giảm giá
        customer_id = data['order'].customer_id
        discount, discount_reason = dao.suggest_discount(customer_id, subtotal)
    else:
        discount = data['order'].discount_percent
        discount_reason = "Đã áp dụng"

    return render_template("cashierLayout/bill.html",
                           data=data,
                           discount=discount,
                           discount_reason=discount_reason
                           )


@app.route("/api/pay/<int:bill_id>", methods=["POST"])
@login_required
def process_payment(bill_id):
    if current_user.role != UserRole.CASHIER:
        abort(403)

    # Lấy dữ liệu từ JS gửi lên
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Dữ liệu gửi lên không hợp lệ"}), 400

    payment_method = data.get("payment_method")
    discount_val = data.get("discount_percent", 0)

    if dao.pay_bill(bill_id, payment_method, float(discount_val)):
        flash("Xác nhận thanh toán thành công!", "success")
        return jsonify({"status": "success", "message": "Thanh toán thành công"})

    return {"error": "Lỗi không tìm thấy hóa đơn"}, 404


# @app.route("/admin/")
# def admin_home():
#     if current_user.role != UserRole.MANAGER:
#         abort(403)
#     menu = dao.load_menu(UserRole.MANAGER.value)
#     today = datetime.now()
#     total_revenue = dao.get_total_revenue(today.month, today.year)
#     top_services = dao.get_top_services(today.month, today.year)
#     stats_data = dao.stats_revenue_by_month(today.month, today.year)
#
#     days_in_month = calendar.monthrange(today.year, today.month)[1]
#     labels = [f"Ngày {i}" for i in range(1, days_in_month + 1)]
#     data = [0] * days_in_month
#
#     # Fill dữ liệu thật vào mảng data
#     # item là (day, amount)
#     for item in stats_data:
#         day_index = int(item[0]) - 1  # Mảng bắt đầu từ 0
#         data[day_index] = float(item[1])
#
#     return render_template("admin/index.html",
#                            menu=menu,
#                            total_revenue=total_revenue,
#                            top_services=top_services,
#                            chart_labels=json.dumps(labels),  # Chuyển sang JSON string để JS đọc được
#                            chart_data=json.dumps(data),
#                            current_month=today.month,
#                            current_year=today.year
#                            )

# @app.route("/admin/user/")
# @login_required
# def admin_users():
#     if current_user.role != UserRole.MANAGER:
#         return "Access denied", 403
#     users = User.query.all()
#     return render_template("admin/users.html", users=users)

# @app.route("/admin/service/")
# @login_required
# def admin_service():
#     if current_user.role != UserRole.MANAGER:
#         return "Access denied", 403
#     services = Service.query.all()
#     return render_template("admin/service.html", services=services)

@login_manager.user_loader
def get_user(user_id):
    return dao.get_user_by_id(user_id=user_id)

#login
@app.route("/login", methods=["GET", "POST"])
def login():
    role_map = {
        UserRole.MANAGER: "admin.index",
        UserRole.RECEPTIONIST: "receptionist_home",
        UserRole.TECHNICIAN: "technician_home",
        UserRole.CASHIER: "cashier_home",
        UserRole.CUSTOMER: "customer_home"
    }

    if current_user.is_authenticated:
        # print(type(current_user.role), current_user.role)

        return redirect(url_for(
            role_map.get(current_user.role, "customer_home")
        ))

    err_msg = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = dao.auth_user(username, password)

        if user:
            login_user(user)

            next = request.args.get('next')

            if next:
                return redirect(next)
            
            return redirect(url_for(
                role_map.get(user.role, "customer_home")
            ))

        else:
            err_msg = "Tài khoản hoặc mật khẩu không đúng!"

        # xử lý đăng nhập...
        next_page = request.args.get("next")
        return redirect(next_page or url_for("index"))

    return render_template("login.html", err_msg=err_msg)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/register", methods=["get", "post"])
def register():
    err_msg = None
    if request.method.__eq__("POST"):
        password = request.form.get("password")
        confirm = request.form.get("confirm")

        if password.__eq__(confirm):
            full_name = request.form.get('full_name')
            username = request.form.get("username")
            image = request.files.get('image')
            phone = request.form.get('phone')
            file_path = None

            # if image:
            #     res = cloudinary.uploader.upload(image)
            #     file_path = res['secure_url']

            try:
                dao.add_user(full_name, username, password, phone, image=file_path)
                return redirect('/login')
            except:
                db.session.rollback()
                err_msg = "Hệ thống đang bị lỗi! Vui lòng quay lại sau!"
        else:
            err_msg = "Mật khẩu không khớp!"

    return render_template("register.html", err_msg=err_msg)

@app.route("/forgot-password")
def forgot_password():
    return render_template("forgot-password.html")
#
# if __name__ == "__main__":
#     app.run(debug=True)