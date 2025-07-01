import os
import random
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
from models import db, AdminUser

# --- Cargar variables de entorno .env ---
load_dotenv()

# --- CREA CARPETA instance/ SI NO EXISTE ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)

# --- Config Flask ---
app = Flask(__name__)
app.secret_key = "23e8f1b60725ab9c7d32af4a18b7194bfc6da1c9a0dcb8ef5231f2b7e95c1a7b"

# --- Config DB ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(INSTANCE_DIR, 'mi_base.db')
db.init_app(app)

# --- Config Mail ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("SMTP_USER")
app.config['MAIL_PASSWORD'] = os.getenv("SMTP_PASS")

# ✅ CONFIGURA REMITENTE POR DEFECTO
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)

# --- Config Login ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

# --- Ruta Login ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = AdminUser.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            flash("❌ Usuario o contraseña incorrectos.")
            return render_template('login.html')

        code = f"{random.randint(100000,999999)}"
        user.current_2fa_code = code
        db.session.commit()

        msg = Message(
            subject="Tu código 2FA",
            recipients=[user.email],
            body=f"Hola {user.username},\n\nTu código de acceso es: {code}\n\nSaludos."
        )
        mail.send(msg)

        session['2fa_user_id'] = user.id
        flash("📬 Código enviado a tu correo.")
        return redirect(url_for('verify_2fa'))

    return render_template('login.html')

# --- Ruta Verificar 2FA ---
@app.route('/verify_2fa', methods=['GET', 'POST'])
def verify_2fa():
    if request.method == 'POST':
        input_code = request.form['code']
        user_id = session.get('2fa_user_id')

        if not user_id:
            flash("❌ Sesión no encontrada.")
            return redirect(url_for('login'))

        user = AdminUser.query.get(user_id)

        if user and user.current_2fa_code == input_code:
            user.current_2fa_code = None
            db.session.commit()
            login_user(user)
            return redirect(url_for('panel.dashboard'))
        else:
            flash("❌ Código incorrecto.")
            return render_template('verify_2fa.html')

    return render_template('verify_2fa.html')

# --- Ruta Logout ---
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.")
    return redirect(url_for('login'))

# --- Registrar Blueprint ---
from panelAdmin import panel_bp
app.register_blueprint(panel_bp)

# --- Crear tablas ---
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
