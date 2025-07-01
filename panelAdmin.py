from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required
from models import db, Cliente, Cuenta, AdminUser
from urllib.parse import quote_plus
import random
import smtplib
from email.mime.text import MIMEText
import os

panel_bp = Blueprint('panel', __name__, url_prefix='/panel')

# ---------------------------
# 💌 Enviar correo 2FA (Gmail)
# ---------------------------
def send_email_2fa(to_email, code):
    from_addr = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")

    msg = MIMEText(f"Tu código de verificación 2FA es: {code}", "plain")
    msg["Subject"] = "Tu código 2FA"
    msg["From"] = from_addr
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(from_addr, password)
        server.sendmail(from_addr, [to_email], msg.as_string())

# ---------------------------
# 🔑 LOGIN & LOGOUT
# ---------------------------
@panel_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = AdminUser.query.filter_by(username=username).first()
        if user and user.check_password(password):
            code = random.randint(100000, 999999)
            session['2fa_code'] = str(code)
            session['2fa_user_id'] = user.id

            # ✅ ENVÍA AL CORREO CORRECTO
            send_email_2fa(user.email, code)

            flash("Te enviamos un código 2FA a tu correo 📩")
            return redirect(url_for('panel.verify_2fa'))
        else:
            flash('❌ Usuario o contraseña incorrectos.')
    return render_template('login.html')

@panel_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión.')
    return redirect(url_for('panel.login'))

# ---------------------------
# 🔐 Verificar 2FA
# ---------------------------
@panel_bp.route('/verify_2fa', methods=['GET', 'POST'])
def verify_2fa():
    if request.method == 'POST':
        code_input = request.form['code']
        code_real = session.get('2fa_code')
        user_id = session.get('2fa_user_id')

        if code_real and code_input == code_real:
            user = AdminUser.query.get(user_id)
            login_user(user)
            session.pop('2fa_code', None)
            session.pop('2fa_user_id', None)
            flash("✅ Código verificado. Bienvenido.")
            return redirect(url_for('panel.dashboard'))
        else:
            flash("❌ Código incorrecto. Intenta de nuevo.")
    return render_template('verify_2fa.html')

# ---------------------------
# 🏠 DASHBOARD
# ---------------------------
@panel_bp.route('/dashboard')
@login_required
def dashboard():
    total_clientes = Cliente.query.count()
    total_cuentas = Cuenta.query.count()
    cuentas_vencidas = Cuenta.query.filter(
        Cuenta.fecha_expiracion < datetime.now().date()
    ).count()

    return render_template(
        'admin/dashboard.html',
        total_clientes=total_clientes,
        total_cuentas=total_cuentas,
        cuentas_vencidas=cuentas_vencidas
    )

# ---------------------------
# 📋 CLIENTES
# ---------------------------
@panel_bp.route('/clientes')
@login_required
def clientes():
    clientes = Cliente.query.all()
    return render_template('admin/clientes.html', clientes=clientes)

@panel_bp.route('/clientes/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_cliente():
    if request.method == 'POST':
        nombre = request.form['nombre']
        telefono = request.form['telefono']
        nuevo = Cliente(nombre=nombre, telefono=telefono)
        db.session.add(nuevo)
        db.session.commit()
        flash('✅ Cliente creado.')
        return redirect(url_for('panel.clientes'))
    return render_template('admin/nuevo_cliente.html')

@panel_bp.route('/clientes/<int:cliente_id>/filtros')
@login_required
def filtros_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    return render_template('admin/filtros.html', cliente=cliente)

@panel_bp.route('/clientes/<int:cliente_id>/filtros/netflix/toggle', methods=['POST'])
@login_required
def toggle_filtro_netflix(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    cliente.filtro_netflix = not cliente.filtro_netflix
    db.session.commit()
    flash(f'Filtro Netflix {"activado" if cliente.filtro_netflix else "desactivado"} ✅')
    return redirect(url_for('panel.filtros_cliente', cliente_id=cliente.id))

@panel_bp.route('/clientes/<int:cliente_id>/generar_pin')
@login_required
def generar_pin(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    nuevo_pin = str(random.randint(1000, 9999))
    cliente.pin_restablecer = nuevo_pin
    db.session.commit()
    flash(f"Nuevo PIN generado: {nuevo_pin}")
    return redirect(url_for('panel.clientes'))

@panel_bp.route('/clientes/<int:cliente_id>/reportar_vencidas')
@login_required
def reportar_cuentas_vencidas(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    hoy = datetime.now().date()

    cuentas_vencidas = Cuenta.query.filter(
        Cuenta.cliente_id == cliente.id,
        Cuenta.fecha_expiracion < hoy
    ).all()

    if not cuentas_vencidas:
        flash('✅ El cliente no tiene cuentas vencidas.')
        return redirect(url_for('panel.cuentas_cliente', cliente_id=cliente.id))

    mensaje = f"👋 Hola {cliente.nombre}, estas son tus cuentas vencidas:\n\n"
    for c in cuentas_vencidas:
        mensaje += f"• {c.correo} — Expiró: {c.fecha_expiracion}\n"

    mensaje += "\nPor favor regulariza cuando puedas. 👍"

    numero = cliente.telefono
    texto = quote_plus(mensaje)
    link_whatsapp = f"https://wa.me/{numero}?text={texto}"

    return redirect(link_whatsapp)

# ---------------------------
# ✅ CUENTAS CLIENTE
# ---------------------------
@panel_bp.route('/cuentas/<int:cliente_id>')
@login_required
def cuentas_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    cuentas = Cuenta.query.filter_by(cliente_id=cliente.id).all()
    return render_template('admin/cuentas_cliente.html', cliente=cliente, cuentas=cuentas)

@panel_bp.route('/cuentas/nueva/<int:cliente_id>', methods=['GET', 'POST'])
@login_required
def nueva_cuenta(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    if request.method == 'POST':
        hoy = datetime.now().date()
        fecha_expiracion = hoy + timedelta(days=30)

        correo_uno = request.form.get('correo_uno', '').strip()
        correos_varios = request.form.get('correos_varios', '').strip().splitlines()

        total = 0

        if correo_uno:
            nueva = Cuenta(
                fecha_compra=hoy.strftime("%Y-%m-%d"),
                fecha_expiracion=fecha_expiracion.strftime("%Y-%m-%d"),
                correo=correo_uno,
                cliente_id=cliente.id
            )
            db.session.add(nueva)
            total += 1

        for correo in correos_varios:
            correo = correo.strip()
            if correo:
                nueva = Cuenta(
                    fecha_compra=hoy.strftime("%Y-%m-%d"),
                    fecha_expiracion=fecha_expiracion.strftime("%Y-%m-%d"),
                    correo=correo,
                    cliente_id=cliente.id
                )
                db.session.add(nueva)
                total += 1

        db.session.commit()
        flash(f'✅ Se guardaron {total} cuenta(s).')
        return redirect(url_for('panel.cuentas_cliente', cliente_id=cliente.id))

    return render_template('admin/nueva_cuenta.html', cliente=cliente)

@panel_bp.route('/cuentas/editar/<int:cuenta_id>', methods=['GET', 'POST'])
@login_required
def editar_cuenta(cuenta_id):
    cuenta = Cuenta.query.get_or_404(cuenta_id)
    if request.method == 'POST':
        cuenta.fecha_compra = request.form['fecha_compra']
        cuenta.fecha_expiracion = request.form['fecha_expiracion']
        cuenta.correo = request.form['correo']
        db.session.commit()
        flash('✅ Cuenta actualizada.')
        return redirect(url_for('panel.cuentas_cliente', cliente_id=cuenta.cliente_id))
    return render_template('admin/editar_cuenta.html', cuenta=cuenta)

@panel_bp.route('/cuentas/eliminar/<int:cuenta_id>', methods=['POST'])
@login_required
def eliminar_cuenta(cuenta_id):
    cuenta = Cuenta.query.get_or_404(cuenta_id)
    cliente_id = cuenta.cliente_id
    db.session.delete(cuenta)
    db.session.commit()
    flash('✅ Cuenta eliminada.')
    return redirect(url_for('panel.cuentas_cliente', cliente_id=cliente_id))

@panel_bp.route('/cuentas/renovar/<int:cuenta_id>', methods=['POST'])
@login_required
def renovar_cuenta(cuenta_id):
    cuenta = Cuenta.query.get_or_404(cuenta_id)
    fecha_exp = datetime.strptime(cuenta.fecha_expiracion, "%Y-%m-%d").date()
    nueva_fecha = fecha_exp + timedelta(days=30)
    cuenta.fecha_expiracion = nueva_fecha.strftime("%Y-%m-%d")
    db.session.commit()
    flash('✅ Cuenta renovada +30 días.')
    return redirect(url_for('panel.cuentas_cliente', cliente_id=cuenta.cliente_id))

@panel_bp.route('/cuentas_vencidas')
@login_required
def cuentas_vencidas():
    hoy = datetime.now().date()
    cuentas = (
        db.session.query(Cuenta)
        .join(Cliente)
        .filter(Cuenta.fecha_expiracion < hoy)
        .all()
    )

    cuentas_por_cliente = {}
    for cuenta in cuentas:
        cliente_id = cuenta.cliente.id
        if cliente_id not in cuentas_por_cliente:
            cuentas_por_cliente[cliente_id] = {
                'cliente': cuenta.cliente,
                'cuentas': []
            }
        cuentas_por_cliente[cliente_id]['cuentas'].append(cuenta)

    return render_template(
        'admin/cuentas_vencidas.html',
        cuentas_por_cliente=cuentas_por_cliente
    )

@panel_bp.route('/buscar_correo')
@login_required
def buscar_correo():
    correo = request.args.get('correo')

    cuenta = Cuenta.query.filter_by(correo=correo).first()
    if cuenta:
        cliente_id = cuenta.cliente_id
        return redirect(url_for('panel.cuentas_cliente', cliente_id=cliente_id, highlight_id=cuenta.id))
    else:
        flash("No se encontró ninguna cuenta con ese correo.")
        return redirect(url_for('panel.dashboard'))
