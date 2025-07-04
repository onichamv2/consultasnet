# crearAdmin.py
from app import app
from models import db, AdminUser

# ✅ Pide datos por teclado
username = input("👤 Usuario: ")
email = input("📧 Correo: ")
password = input("🔑 Clave: ")

with app.app_context():
    admin = AdminUser(username=username, email=email)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print(f"✅ Usuario admin '{username}' creado correctamente.")
