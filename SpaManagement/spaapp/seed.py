from spaapp import app, db, dao
from spaapp.models import User, Service, SystemConfig, Product, BillProduct, Bill, Appointment
import json, hashlib

with app.app_context():
    db.create_all()

    with open("data/users.json", encoding="utf-8") as f:
        users = json.load(f)

        for u in users:
            user = User(**u)
            user.password=hashlib.md5(user.password.encode("utf-8")).hexdigest()
            db.session.add(user)

    db.session.commit()
    load_datas = [
        ("data/services.json", Service, None),
        ("data/config.json", SystemConfig, None),
        ("data/appointments.json", Appointment, None),
        ("data/bills.json", Bill, None),
        ("data/products.json", Product, None),
        ("data/bill_products.json", BillProduct, None)
    ]

    for a,b,c in load_datas:
        dao.seed_json(a, b, c)




