import os
import imaplib
import email
from dotenv import load_dotenv
from app import app

from flask import Flask, request, render_template, Response
from flask_login import LoginManager
from models import db, Cliente, Cuenta, AdminUser
from panelAdmin import panel_bp
from flask import jsonify

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
DATABASE_URL = os.getenv("DATABASE_URL")
print("DATABASE_URL:", DATABASE_URL)
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
# 🏠 Página principal
# --------------------------
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# --------------------------
# 📌 Ruta de búsqueda con filtros alineados
# --------------------------
@app.route('/buscar', methods=['POST'])
def buscar():
    correo_input = request.form.get('correo', '').strip().lower()
    pin_input = request.form.get('pin', '').strip()

    if not correo_input:
        return Response("<div class='alert alert-danger'>❌ Debes enviar un correo válido.</div>", content_type='text/html; charset=utf-8')

    cuenta = Cuenta.query.filter(db.func.lower(Cuenta.correo) == correo_input).first()

    filtros = []

    if cuenta:
        if cuenta.cliente:
            # 🎩 PREMIUM
            if cuenta.filtro_netflix:
                filtros.append("Netflix: Tu código de inicio de sesión")
            if cuenta.filtro_actualizar_hogar:
                filtros.append("Confirmación: Se ha confirmado tu Hogar con Netflix")
            if cuenta.filtro_codigo_temporal:
                filtros.append("Tu código de acceso temporal de Netflix")
            if pin_input and cuenta.filtro_dispositivo:
                filtros.append("Un nuevo dispositivo está usando tu cuenta")

        elif cuenta.cliente_final:
            # 👥 FINAL
            if cuenta.filtro_netflix:
                filtros.append("Netflix: Tu código de inicio de sesión")
            if cuenta.filtro_actualizar_hogar:
                filtros.append("Confirmación: Se ha confirmado tu Hogar con Netflix")
            if cuenta.filtro_codigo_temporal:
                filtros.append("Tu código de acceso temporal de Netflix")
            # Solo se agrega *Un nuevo dispositivo* si PIN coincide
            if pin_input:
                if cuenta.pin_final and cuenta.pin_final == pin_input:
                    filtros.append("Un nuevo dispositivo está usando tu cuenta")

        else:
            # Cuenta sin cliente asociado
            return Response("<div class='alert alert-danger'>❌ Esta cuenta no tiene cliente asociado.</div>", content_type='text/html; charset=utf-8')

    else:
        return Response("<div class='alert alert-danger'>❌ Esta cuenta no existe.</div>", content_type='text/html; charset=utf-8')

    if not filtros:
        return Response("<div class='alert alert-danger'>❌ No hay filtros activos para esta cuenta o el PIN no coincide.</div>", content_type='text/html; charset=utf-8')

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
        mensaje = html_body or "<div class='alert alert-warning'>✅ No se encontró ningún correo filtrado para este correo.</div>"

    except Exception as e:
        mensaje = f"<div class='alert alert-danger'>❌ Error IMAP: {str(e)}</div>"

    return Response(mensaje, content_type='text/html; charset=utf-8')

#SI FALLA ESTO SE AÑADIO ULTIMO
@app.route('/api/consulta_hogar', methods=['POST'])
def consulta_hogar():
    data = request.json
    correo_input = data.get('correo', '').strip().lower()
    pin_input = data.get('pin', '').strip()
    opcion = data.get('opcion', '').strip()

    if not correo_input:
        return jsonify({"resultado": "❌ Debes enviar un correo válido."})

    cuenta = Cuenta.query.filter(db.func.lower(Cuenta.correo) == correo_input).first()

    filtros = []

    if cuenta:
        if cuenta.cliente:
            if cuenta.filtro_netflix:
                filtros.append("Netflix: Tu código de inicio de sesión")
            if cuenta.filtro_actualizar_hogar:
                filtros.append("Confirmación: Se ha confirmado tu Hogar con Netflix")
            if cuenta.filtro_codigo_temporal:
                filtros.append("Tu código de acceso temporal de Netflix")
            if pin_input and cuenta.filtro_dispositivo:
                filtros.append("Un nuevo dispositivo está usando tu cuenta")
        elif cuenta.cliente_final:
            if cuenta.filtro_netflix:
                filtros.append("Netflix: Tu código de inicio de sesión")
            if cuenta.filtro_actualizar_hogar:
                filtros.append("Confirmación: Se ha confirmado tu Hogar con Netflix")
            if cuenta.filtro_codigo_temporal:
                filtros.append("Tu código de acceso temporal de Netflix")
            if pin_input and cuenta.pin_final == pin_input and cuenta.filtro_dispositivo:
                filtros.append("Un nuevo dispositivo está usando tu cuenta")
        else:
            return jsonify({"resultado": "❌ Esta cuenta no tiene cliente asociado."})
    else:
        return jsonify({"resultado": "❌ Esta cuenta no existe."})

    if not filtros:
        return jsonify({"resultado": "❌ No hay filtros activos o el PIN no coincide."})

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(IMAP_USER, IMAP_PASS)
        mail.select("inbox")

        status, data = mail.search(None, f'(TO "{correo_input}")')
        ids = data[0].split()

        mensaje_final = "✅ No se encontró ningún correo filtrado para este correo."

        for num in reversed(ids):
            typ, msg_data = mail.fetch(num, '(RFC822)')
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            asunto = email.header.decode_header(msg["Subject"])[0][0]
            if isinstance(asunto, bytes):
                asunto = asunto.decode(errors="replace")
            asunto = asunto.lower().strip()

            if any(f.lower() in asunto for f in filtros):
                # Si es para 'netflix', intenta extraer el código (ejemplo simple)
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(errors="replace").strip()
                            break
                else:
                    body = msg.get_payload(decode=True).decode(errors="replace").strip()

                match = re.search(r"\b(\d{4})\b", body)
                if match:
                    mensaje_final = f"✅ Tu código es: {match.group(1)}"
                else:
                    mensaje_final = "❌ No se encontró código numérico."
            
                break

        mail.logout()
    except Exception as e:
        mensaje_final = f"❌ Error IMAP: {str(e)}"

    return jsonify({"resultado": mensaje_final})
#HASTA AQUI

# --------------------------
# 📌 Run
# --------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)
