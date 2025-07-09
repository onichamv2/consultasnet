import os
import imaplib
import email
from dotenv import load_dotenv

from flask import Flask, request, render_template
from flask_login import LoginManager
from flask_migrate import Migrate
from models import db, Cliente, ClienteFinal, Cuenta, AdminUser
from panelAdmin import panel_bp
from extensions import db

# --------------------------
# ✅ Cargar .env
# --------------------------
load_dotenv()

IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASS = os.getenv("IMAP_PASS")
IMAP_SERVER = os.getenv("IMAP_SERVER")
IMAP_PORT_RAW = os.getenv("IMAP_PORT")
IMAP_PORT = int(IMAP_PORT_RAW) if IMAP_PORT_RAW else None

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL and DATABASE_URL.startswith("postgresql://") and "+pg8000" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+pg8000://", 1)

print("✅ DATABASE_URL final:", DATABASE_URL)

SECRET_KEY = os.getenv("SECRET_KEY", "SUPER_SECRET")

if not all([IMAP_USER, IMAP_PASS, IMAP_SERVER, IMAP_PORT, DATABASE_URL]):
    raise Exception("❌ ERROR: Verifica tu archivo .env (IMAP y DATABASE_URL)")

# --------------------------
# ✅ Inicializar Flask
# --------------------------
app = Flask(__name__)
app.secret_key = SECRET_KEY

# --------------------------
# ✅ Motor SQLAlchemy
# --------------------------
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# --------------------------
# ✅ Migraciones: Flask-Migrate
# --------------------------
migrate = Migrate(app, db)

# --------------------------
# ✅ Login Manager
# --------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'panel.login'

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

# --------------------------
# ✅ Registrar Blueprint
# --------------------------
app.register_blueprint(panel_bp)

# --------------------------
# 🏠 Ruta principal
# --------------------------
@app.route('/')
def index():
    return render_template('index.html')

# --------------------------
# 🔍 Búsqueda IMAP + FILTROS
# --------------------------
@app.route('/buscar', methods=['POST'])
def buscar():
    correo_input = request.values.get('correo', '').strip().lower()
    pin_input = request.values.get('pin', '').strip()

    cuenta = Cuenta.query.filter(
        db.func.lower(Cuenta.correo) == correo_input
    ).first()

    filtros = []

    if cuenta:
        if cuenta.cliente:
            # Es mayorista/premium
            if cuenta.filtro_dispositivo:
                if not pin_input or pin_input != str(cuenta.cliente.pin_restablecer):
                    return "❌ PIN inválido o sin permiso."
                filtros.append("Un nuevo dispositivo está usando tu cuenta")

            if cuenta.filtro_netflix:
                filtros.append("Netflix: Tu código de inicio de sesión")
            if cuenta.filtro_actualizar_hogar:
                filtros.append("Confirmación: Se ha confirmado tu Hogar con Netflix")
            if cuenta.filtro_codigo_temporal:
                filtros.append("Tu código de acceso temporal de Netflix")

        elif cuenta.cliente_final:
            # Es cliente final
            if cuenta.filtro_dispositivo:
                if not pin_input or pin_input != str(cuenta.pin_final):
                    return "❌ PIN inválido o sin permiso."
                filtros.append("Un nuevo dispositivo está usando tu cuenta")

            if cuenta.filtro_netflix:
                filtros.append("Netflix: Tu código de inicio de sesión")
            if cuenta.filtro_actualizar_hogar:
                filtros.append("Confirmación: Se ha confirmado tu Hogar con Netflix")
            if cuenta.filtro_codigo_temporal:
                filtros.append("Tu código de acceso temporal de Netflix")

        else:
            return "❌ Esta cuenta no tiene cliente asociado."


    else:
        return "❌ Esta cuenta no existe."

    if not filtros:
        return "❌ No hay filtros activos para esta cuenta."

    print("========== DEBUG ==========")
    print(f"Correo buscado: {correo_input}")
    print(f"Filtros activos: {filtros}")
    print("===========================")

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(IMAP_USER, IMAP_PASS)
        mail.select("inbox")

        status, data = mail.search(None, f'(TO "{correo_input}")')
        ids = data[0].split()

        html_body = None

        for num in reversed(ids):
            typ, msg_data = mail.fetch(num, '(RFC822)')
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            asunto = email.header.decode_header(msg["Subject"])[0][0]
            if isinstance(asunto, bytes):
                asunto = asunto.decode(errors="replace")
            asunto = asunto.lower().strip()

            if any(f.lower() in asunto for f in filtros):
                if msg.is_multipart():
                    for part in msg.walk():
                        ctype = part.get_content_type()
                        charset = part.get_content_charset() or "utf-8"
                        if ctype == "text/html":
                            html_body = part.get_payload(decode=True).decode(charset, errors="replace")
                            break
                        elif ctype == "text/plain" and not html_body:
                            html_body = f"<pre>{part.get_payload(decode=True).decode(charset, errors='replace')}</pre>"
                else:
                    charset = msg.get_content_charset() or "utf-8"
                    if msg.get_content_type() == "text/html":
                        html_body = msg.get_payload(decode=True).decode(charset, errors="replace")
                    else:
                        html_body = f"<pre>{msg.get_payload(decode=True).decode(charset, errors='replace')}</pre>"
                break

        mail.logout()

        if html_body:
            html_body = html_body.encode().decode('unicode_escape')

        return render_template(
            'busqueda_resultado.html',
            cliente=cuenta.cliente if cuenta else None,
            cuentas=[cuenta] if cuenta else [],
            mensaje=html_body or "✅ No se encontró coincidencia, pero la conexión IMAP funcionó."
        )

    except Exception as e:
        return f"❌ Error IMAP: {str(e)}"


# --------------------------
# 🚀 Local
# --------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)

