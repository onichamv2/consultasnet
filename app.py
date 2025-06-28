import os
from flask import Flask, request, render_template
import imaplib
import email
from dotenv import load_dotenv

load_dotenv()

IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASS = os.getenv("IMAP_PASS")
IMAP_SERVER = os.getenv("IMAP_SERVER")
IMAP_PORT = int(os.getenv("IMAP_PORT"))

if not all([IMAP_USER, IMAP_PASS, IMAP_SERVER, IMAP_PORT]):
    raise Exception("❌ ERROR: Verifica tu archivo .env")

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/buscar', methods=['POST'])
def buscar():
    correo_input = request.json.get('correo')
    filtros = [
        #"Netflix: Tu código de inicio de sesión",
        "Importante: Cómo actualizar tu Hogar con Netflix",
        "Tu código de acceso temporal de Netflix"
    ]

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(IMAP_USER, IMAP_PASS)
        mail.select("inbox")

        status, data = mail.search(None, f'(TO "{correo_input}")')
        ids = data[0].split()

        if not ids:
            mail.logout()
            return {"error": "No se encontraron correos para este correo."}

        asunto = None
        html_body = None

        for num in ids[::-1]:
            typ, msg_data = mail.fetch(num, '(RFC822)')
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            asunto = email.header.decode_header(msg["Subject"])[0][0]
            if isinstance(asunto, bytes):
                asunto = asunto.decode(errors="replace")

            if any(f in asunto for f in filtros):
                # Buscamos el contenido HTML si existe
                if msg.is_multipart():
                    for part in msg.walk():
                        ctype = part.get_content_type()
                        if ctype == "text/html":
                            charset = part.get_content_charset() or "utf-8"
                            html_body = part.get_payload(decode=True).decode(charset, errors="replace")
                            break
                        elif ctype == "text/plain" and not html_body:
                            charset = part.get_content_charset() or "utf-8"
                            html_body = f"<pre>{part.get_payload(decode=True).decode(charset, errors='replace')}</pre>"
                else:
                    if msg.get_content_type() == "text/html":
                        charset = msg.get_content_charset() or "utf-8"
                        html_body = msg.get_payload(decode=True).decode(charset, errors="replace")
                    else:
                        charset = msg.get_content_charset() or "utf-8"
                        html_body = f"<pre>{msg.get_payload(decode=True).decode(charset, errors='replace')}</pre>"
                break

        mail.logout()

        if html_body:
            return {"mensaje": html_body}
        else:
            return {"error": "No se encontró correo válido con ese filtro."}

    except Exception as e:
        return {"error": f"Error: {str(e)}"}

if __name__ == "__main__":
    app.run(debug=True)
