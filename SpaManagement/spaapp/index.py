import cloudinary
from flask import Flask, render_template, request, redirect, url_for
from flask_login import current_user, login_user,  login_required, logout_user
from spaapp import dao, db
from spaapp import login_manager, app
from spaapp.models import UserRole, User, Service
from datetime import date, datetime, timedelta
from dao import get_schedule_by_date, TIME_SLOTS

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/customer/")
def customer_home():
    menu = dao.load_menu(UserRole.CUSTOMER.value)
    # print(menu)
    # print(UserRole.CUSTOMER.value)
    return render_template("customerLayout/index.html", menu=menu)

@app.route("/receptionist/")
def receptionist_home():
    menu = dao.load_menu(UserRole.RECEPTIONIST.value)
    today = datetime.today()
    return render_template("receptionistLayout/index.html", today=today, menu=menu)

@app.route("/receptionist/calendar")
def calendar():
    today = datetime.now().date()
    selected_date = request.args.get("date")

    if selected_date:
        selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
    else:
        selected_date = today

    days = [today + timedelta(days=i) for i in range(-1, 6)]

    schedule = get_schedule_by_date(selected_date.strftime("%Y-%m-%d"))
    return render_template("receptionistLayout/calendar.html",
                           days=days,
                           selected_date=selected_date,
                           schedule=schedule
                           )
@app.route("/receptionist/book")
def book():
    date = request.args.get("date")
    time = request.args.get("time")
    services = Service.query.filter(Service.active == True).all()
    return render_template("receptionistLayout/book.html", date=date, time=time, services=services)

#KTV
@app.route("/technician")
@login_required
def technician_home():
    today = date.today()
    appointments = dao.get_appointments_by_technician(
        technician_id=current_user.id,
        date=today
    )
    return render_template(
        "technicianLayout/home.html",
        today=today,
        today_appointments=appointments
    )

@app.route("/technician/record/<int:appt_id>", methods=["GET", "POST"])
@login_required
def technician_record(appt_id):
    appt = dao.get_appointment_by_id(appt_id)

    if request.method == "POST":
        appt.status = "DONE"
        db.session.commit()
        return redirect(url_for("technician_home"))

    return render_template(
        "technicianLayout/record.html",
        appt=appt
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
            role_map.get(UserRole(current_user.role), "customer_home")
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
                role_map.get(UserRole(user.role), "customer_home")
            ))

        else:
            err_msg = "Tài khoản hoặc mật khẩu không đúng!"

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
