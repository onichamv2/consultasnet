from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()

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

class Cliente(db.Model):
    __tablename__ = 'cliente'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    telefono = db.Column(db.String(50))
    filtro_netflix = db.Column(db.Boolean, default=True)
    pin_restablecer = db.Column(db.String(10))
    cuentas = db.relationship('Cuenta', back_populates='cliente', cascade='all, delete', lazy=True)
    filtros = db.relationship('Filtro', backref='cliente', cascade='all, delete', lazy=True)

class Filtro(db.Model):
    __tablename__ = 'filtro'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200))
    activo = db.Column(db.Boolean, default=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)

class Cuenta(db.Model):
    __tablename__ = 'cuenta'
    id = db.Column(db.Integer, primary_key=True)
    correo = db.Column(db.String(255), nullable=False)
    fecha_compra = db.Column(db.String(20))
    fecha_expiracion = db.Column(db.String(20))
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    cliente = db.relationship('Cliente', back_populates='cuentas')
