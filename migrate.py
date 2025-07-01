# migrate.py
from app import db, app

with app.app_context():
    print("🔄 Creando todas las tablas en la base de datos...")
    db.create_all()
    print("✅ ¡Migración completada correctamente!")
