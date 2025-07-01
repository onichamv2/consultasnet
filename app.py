import os
import imaplib
import email
from dotenv import load_dotenv

from flask import Flask, request, render_template
from flask_login import LoginManager
from models import Cliente, Cuenta, AdminUser
from panelAdmin import panel_bp

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

import asyncio

# --------------------------
# ✅ Cargar .env
# --------------------------
load_dotenv()

IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASS = os.getenv("IMAP_PASS")
IMAP_SERVER = os.getenv("IMAP_SERVER")
IMAP_PORT = int(os.getenv("IMAP_PORT", 993))
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "SUPER_SECRET")

if not all([IMAP_USER, IMAP_PASS, IMAP_SERVER, IMAP_PORT, DATABASE_URL]):
    raise Exception("❌ ERROR: Verifica tu archivo .env (IMAP y DATABASE_URL)")

# --------------------------
# ✅ Inicializar Flask
# --------------------------
app = Flask(__name__)
app.secret_key = SECRET_KEY

# --------------------------
# ✅ Motor ASYNC y sesión
# --------------------------
engine = create_async_engine(DATABASE_URL, echo=True)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# --------------------------
# ✅ Configurar Login Manager
# --------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'panel.login'

@login_manager.user_loader
async def load_user(user_id):
    async with AsyncSessionLocal() as session:
        return await session.get(AdminUser, int(user_id))

# --------------------------
# ✅ Registrar Blueprints
# --------------------------
app.register_blueprint(panel_bp)

# --------------------------
# 🏠 Ruta principal
# --------------------------
@app.route('/')
def index():
    return render_template('index.html')

# --------------------------
# 🔍 Ruta de búsqueda ASYNC
# --------------------------
@app.route('/buscar', methods=['POST'])
async def buscar():
    correo_input = request.values.get('correo', '').strip()

    if not correo_input:
        return "❌ Debes enviar un correo válido."

    async with AsyncSessionLocal() as session:
        cliente = await session.scalar(
            Cliente.query.filter(Cliente.cuentas.any(Cuenta.correo == correo_input)).limit(1)
        )

        cuentas = await session.execute(
            Cuenta.query.filter_by(correo=correo_input)
        )
        cuentas = cuentas.scalars().all()

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

        for num in reversed(ids):
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

        if html_body:
            html_body = html_body.encode().decode('unicode_escape')

        return render_template(
            'busqueda_resultado.html',
            cliente=cliente,
            cuentas=cuentas,
            mensaje=html_body
        )

    except Exception as e:
        return f"❌ Error IMAP: {str(e)}"

# --------------------------
# 🚀 Ejecutar localmente
# --------------------------
if __name__ == "__main__":
    async def run():
        async with engine.begin() as conn:
            # Aquí deberías usar Alembic en producción
            pass

    asyncio.run(run())
    app.run(host='0.0.0.0', port=5000)
