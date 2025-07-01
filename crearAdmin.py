from models import db, AdminUser
from admin import app

with app.app_context():
    username = input("Usuario: ")
    email = input("Email: ")
    password = input("Clave: ")

    admin = AdminUser(username=username, email=email)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()

    print("✅ Admin creado con éxito")
