import os
import imaplib
import email
from dotenv import load_dotenv
from app import app

from flask import Flask, request, render_template, Response
from flask_login import LoginManager
from models import db, Cliente, Cuenta, AdminUser
from panelAdmin import panel_bp

# --------------------------
# 📌 Cargar .env
# --------------------------
load_dotenv()

IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASS = os.getenv("IMAP_PASS")
IMAP_SERVER = os.getenv("IMAP_SERVER")
IMAP_PORT = int(os.getenv("IMAP_PORT", 993))

# --------------------------
# 📌 App Flask
# --------------------------
app = Flask(__name__)
app.secret_key = 'TU_SECRET_KEY_PRO'

# --------------------------
# 📌 DB config
# --------------------------
# 👉 Cambiar para usar Postgres en producción
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'mi_base.db')}"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# --------------------------
# 📌 Login
# --------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'panel.login'

@login_manager.user_loader
def load_user(user_id):
    return AdminUser.query.get(int(user_id))

# --------------------------
# 📌 Registrar Blueprint
# --------------------------
app.register_blueprint(panel_bp)

# --------------------------
# 🏠 Página principal (solo muestra formulario)
# --------------------------
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# --------------------------
# 📌 Ruta AJAX — devuelve solo HTML del resultado
# --------------------------
@app.route('/buscar', methods=['POST'])
def buscar():
    correo_input = request.form.get('correo', '').strip()
    pin_input = request.form.get('pin', '').strip()

    mensaje = "<div class='alert alert-danger'>❌ Debes enviar un correo válido.</div>"

    if correo_input:
        cliente = Cliente.query.filter(Cliente.cuentas.any(Cuenta.correo == correo_input)).first()

        # Armado de filtros
        if pin_input and cliente and cliente.pin_restablecer == pin_input:
            filtros = ["Un nuevo dispositivo está usando tu cuenta"]
        else:
            filtros = [
                "Importante: Cómo actualizar tu Hogar con Netflix",
                "Tu código de acceso temporal de Netflix"
            ]
            if cliente and cliente.filtro_netflix:
                filtros.append("Netflix: Tu código de inicio de sesión")

        try:
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            mail.login(IMAP_USER, IMAP_PASS)
            mail.select("inbox")

            status, data = mail.search(None, f'(TO "{correo_input}")')
            ids = data[0].split()

            html_body = None

            for num in ids[::-1]:
                typ, msg_data = mail.fetch(num, '(RFC822)')
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                asunto = email.header.decode_header(msg["Subject"])[0][0]
                if isinstance(asunto, bytes):
                    asunto = asunto.decode(errors="replace")

                if any(f in asunto for f in filtros):
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
            mensaje = html_body or "<div class='alert alert-warning'>No se encontró ningún correo filtrado para este correo.</div>"

        except Exception as e:
            mensaje = f"<div class='alert alert-danger'>❌ Error IMAP: {str(e)}</div>"

    return Response(mensaje, content_type='text/html; charset=utf-8')

# --------------------------
# 📌 Run
# --------------------------
if __name__ == "__main__":
    with app.app_context():
        from models import db  # Para asegurar que db esté en contexto
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)

