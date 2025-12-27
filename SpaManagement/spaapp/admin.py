# admin.py
import json
import calendar
from datetime import datetime
from flask import redirect
from flask_admin import Admin, AdminIndexView, expose, BaseView
from flask_admin.contrib.sqla import ModelView
from flask_admin.theme import Bootstrap4Theme
from flask_login import current_user, logout_user

from spaapp import app, db, dao
from spaapp.models import (
    User, Service, Product,
    StaffShift, SystemConfig, UserRole
)


class MyAdminIndexView(AdminIndexView):
    @expose('/')
    def index(self):
        # 1. Kiểm tra đăng nhập & Quyền
        if not current_user.is_authenticated:
            return redirect('/login')

        if current_user.role != UserRole.MANAGER:
            return "Access denied", 403

        # 2. Xử lý Logic Thống kê (Chuyển từ index.py sang đây)
        today = datetime.now()

        # Tính tổng doanh thu
        total_revenue = dao.get_total_revenue(today.month, today.year)

        # Lấy top dịch vụ
        top_services = dao.get_top_services(today.month, today.year)

        # Lấy dữ liệu biểu đồ
        stats_data = dao.stats_revenue_by_month(today.month, today.year)

        # Xử lý dữ liệu biểu đồ cho ChartJS
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        labels = [f"Ngày {i}" for i in range(1, days_in_month + 1)]
        data = [0] * days_in_month

        for item in stats_data:
            day_index = int(item[0]) - 1  # Mảng bắt đầu từ 0
            data[day_index] = float(item[1])

        # 3. Load Menu
        menu = dao.load_menu(UserRole.MANAGER.value)

        # 4. Render template và truyền dữ liệu
        return self.render('admin/index.html',
                           menu=menu,
                           total_revenue=total_revenue,
                           top_services=top_services,
                           chart_labels=json.dumps(labels),
                           chart_data=json.dumps(data),
                           current_month=today.month,
                           current_year=today.year)


class MyUserView(ModelView):
    can_export = True
    list_template = 'admin/list_custom.html'
    create_template = 'admin/edit_custom.html'
    edit_template = 'admin/edit_custom.html'

    def render(self, template, **kwargs):
        kwargs['menu'] = dao.load_menu(UserRole.MANAGER.value)
        return super().render(template, **kwargs)


class UserView(MyUserView):
    column_searchable_list = ["full_name"]
    column_filters = [User.role]


# Khởi tạo Admin
admin = Admin(app=app, name="Quản Lý Spa", theme=Bootstrap4Theme(), index_view=MyAdminIndexView())

admin.add_view(UserView(User, db.session, name="Người dùng"))
admin.add_view(MyUserView(Service, db.session, name="Dịch vụ"))
admin.add_view(MyUserView(Product, db.session, name="Sản phẩm"))
admin.add_view(MyUserView(StaffShift, db.session, name="Ca làm việc"))
admin.add_view(MyUserView(SystemConfig, db.session, name="Cấu hình"))