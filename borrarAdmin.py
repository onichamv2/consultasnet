# borrarAdmin.py
from app import app
from models import db, AdminUser

with app.app_context():
    admin = AdminUser.query.filter_by(username="admin").first()
    if admin:
        db.session.delete(admin)
        db.session.commit()
        print("✅ Usuario admin eliminado.")
    else:
        print("❌ No existe usuario admin.")