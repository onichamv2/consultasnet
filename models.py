from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy import Date
from extensions import db  # ✅ solo usa este db

# ---------------------------
# 👤 Admin User
# ---------------------------
class AdminUser(UserMixin, db.Model):
    __tablename__ = 'admin_user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    current_2fa_code = db.Column(db.String(6), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# ---------------------------
# 🧑‍💼 Cliente Premium
# ---------------------------
class Cliente(db.Model):
    __tablename__ = 'cliente'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150))
    telefono = db.Column(db.String(50))
    pin_restablecer = db.Column(db.String(10))

    # ✅ Relación correcta
    cuentas = db.relationship('Cuenta', back_populates='cliente',
    cascade='all, delete',
    lazy=True)

# ---------------------------
# 👤 Cliente Final
# ---------------------------
class ClienteFinal(db.Model):
    __tablename__ = 'cliente_final'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    telefono = db.Column(db.String(100))
    pin_restablecer = db.Column(db.String(10))
    cuentas = db.relationship(
        'Cuenta',
        back_populates='cliente_final',
        cascade='all, delete',
        lazy=True
    )


# ---------------------------
# 📩 Cuenta (mayoristas y finales)
# ---------------------------
class Cuenta(db.Model):
    __tablename__ = 'cuenta'
    id = db.Column(db.Integer, primary_key=True)
    correo = db.Column(db.String(255), nullable=False)
    fecha_compra = db.Column(Date)
    fecha_expiracion = db.Column(Date)
    activo = db.Column(db.Boolean, default=True)

    filtro_netflix = db.Column(db.Boolean, default=True)
    filtro_dispositivo = db.Column(db.Boolean, default=True)
    filtro_actualizar_hogar = db.Column(db.Boolean, default=True)
    filtro_codigo_temporal = db.Column(db.Boolean, default=True)

    pin_final = db.Column(db.String(10))

    # ✅ SOLO UNA VEZ:
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=True)
    cliente = db.relationship('Cliente', back_populates='cuentas', lazy='joined')

    # Si vas a usar ClienteFinal:
    cliente_final_id = db.Column(db.Integer, db.ForeignKey('cliente_final.id'), nullable=True)
    cliente_final = db.relationship('ClienteFinal', back_populates='cuentas', lazy='joined')

