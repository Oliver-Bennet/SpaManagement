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
        if not current_user.is_authenticated:
            return redirect('/login')

        if current_user.role != UserRole.MANAGER:
            return "Access denied", 403

        menu = dao.load_menu(UserRole.MANAGER.value)
        return self.render('admin/index.html', menu=menu)

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


admin = Admin(app=app, name="Quản Lý CRUD", theme=Bootstrap4Theme(), index_view=MyAdminIndexView())

admin.add_view(UserView(User, db.session))
admin.add_view(MyUserView(Service, db.session))
admin.add_view(MyUserView(Product, db.session))
admin.add_view(MyUserView(StaffShift, db.session))
admin.add_view(MyUserView(SystemConfig, db.session))
