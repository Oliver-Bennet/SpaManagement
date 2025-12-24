import cloudinary
from flask import Flask, render_template, request, redirect, url_for, abort, flash
from flask_login import current_user, login_user,  login_required, logout_user
from spaapp import dao, db
from spaapp import login_manager, app
from spaapp.models import UserRole, User, Service, Bill
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
    # print(menu)
    # print(UserRole.CUSTOMER.value)
    return render_template("customerLayout/index.html", menu=menu)


@app.route("/customer/book", methods=["GET", "POST"])
@login_required
def customer_book():
    if current_user.role != UserRole.CUSTOMER:
        abort(403)

    if request.method == "POST":
        try:
            dao.create_appointment(
                customer_id=current_user.id,
                service_id=request.form.get("service_id"),
                appointment_date=request.form.get("date"),
                start_time=request.form.get("start_time"),
                note=request.form.get("note"),
                created_by=current_user.id
            )
            flash("Đặt lịch thành công!", "success")
        except Exception as e:
            flash(str(e), "error")

        return redirect(url_for("customer_book"))

    return render_template(
        "customerLayout/book.html",
        services=dao.get_services(),
        time_slots=dao.generate_time_slots()
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
    menu = dao.load_menu(UserRole.RECEPTIONIST.value)
    today = datetime.today()
    return render_template("receptionistLayout/index.html", today=today, menu=menu)

@app.route("/receptionist/calendar")
@login_required
def receptionist_calendar():
    if current_user.role != UserRole.RECEPTIONIST:
        abort(403)
    today = datetime.now().date()
    selected_date = request.args.get("date")

    if selected_date:
        selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
    else:
        selected_date = today

    days = [today + timedelta(days=i) for i in range(-1, 6)]

    schedule = get_schedule_by_date(selected_date)
    return render_template("receptionistLayout/calendar.html",
                           days=days,
                           selected_date=selected_date,
                           schedule=schedule,
                           now=datetime.now,
                           today=date.today()
                           )
@app.route("/receptionist/book")
@login_required
def receptionist_book():
    if current_user.role != UserRole.RECEPTIONIST:
        abort(403)
    date = request.args.get("date")
    time = request.args.get("time")
    services = Service.query.filter(Service.active == True).all()
    return render_template("receptionistLayout/book.html", date=date, time=time, services=services)

#KTV
@app.route("/technician")
@login_required
def technician_home():
    if current_user.role != UserRole.TECHNICIAN:
        abort(403)
    today = date.today()
    # appointments = dao.get_appointments_by_technician(
    #     technician_id=current_user.id,
    #     date=today
    # )
    appointments = dao.get_appointments_by_technician(current_user.id, today)
    #Tao lich gia
    # fake_appt = SimpleNamespace(
    #     id=1,
    #     start_time="09:00",
    #     end_time="10:00",
    #     status="DONE",
    #     customer=SimpleNamespace(full_name="Nguyễn Văn A"),
    #     service=SimpleNamespace(name="Massage thư giãn"),
    #     package=None
    # )
    data = [dao.serialize_appointment(a) for a in appointments]
    return render_template(
        "technicianLayout/index.html",
        today=today,
        today_appointments=appointments,
        appointments=data
        # today_appointments = [fake_appt]
    )

@app.route("/technician/record/<int:appt_id>", methods=["GET", "POST"])
@login_required
def technician_record(appt_id):
    appt = dao.get_appointment_by_id(appt_id)

    if request.method == "POST":
        appt.status = "DONE"
        dao.create_bill_from_appointment(appt)
        db.session.commit()
        return redirect(url_for("technician_home"))

    # fake_appt = SimpleNamespace(
    #     id=appt_id,
    #     start_time="09:00",
    #     end_time="10:00",
    #     status="PENDING",
    #     customer=SimpleNamespace(full_name="Nguyễn Văn A"),
    #     service=SimpleNamespace(name="Massage thư giãn"),
    #     package=None
    # )

    return render_template(
        "technicianLayout/record.html",
        appt=appt
        # appt=fake_appt
    )

@app.route("/cashier/")
def cashier_home():
    menu = dao.load_menu(UserRole.CASHIER.value)
    today = datetime.today()
    bills = dao.get_bills_for_today()
    print(bills)
    return render_template("cashierLayout/index.html", today=today, menu=menu, bills=bills)

@app.route("/cashier/bill/<id>")
def bill_new(id):
    data = dao.get_bill_data(1)
    return render_template("cashierLayout/bill.html", data=data)

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


# @app.route("/admin/")
# def admin_home():
#     menu = dao.load_menu(UserRole.MANAGER.value)
#     return render_template("admin/index.html", menu=menu)

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