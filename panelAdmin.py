from datetime import datetime, timedelta, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required
from models import db, Cliente, ClienteFinal, Cuenta, AdminUser
import random, smtplib, os
from email.mime.text import MIMEText
from collections import defaultdict
from models import ClienteFinal
from urllib.parse import quote
from sqlalchemy.orm import joinedload
from sqlalchemy import func

panel_bp = Blueprint('panel', __name__, url_prefix='/panel')

# ---------------------------
# 💌 Enviar correo 2FA
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

@panel_bp.route('/verify_2fa', methods=['GET', 'POST'])
def verify_2fa():
    if request.method == 'POST':
        if session.get('2fa_code') == request.form['code']:
            user = AdminUser.query.get(session.get('2fa_user_id'))
            login_user(user)
            session.pop('2fa_code', None)
            session.pop('2fa_user_id', None)
            flash("✅ Código verificado. Bienvenido.")
            return redirect(url_for('panel.dashboard'))
        else:
            flash("❌ Código incorrecto.")
    return render_template('verify_2fa.html')

# ---------------------------
# 🏠 DASHBOARD
# ---------------------------
# ---------------------------
# 🏠 DASHBOARD CORREGIDO
# ---------------------------
# dashboard
@panel_bp.route('/dashboard')
@login_required
def dashboard():
    total_clientes = Cliente.query.count()
    total_clientes_finales = (
        db.session.query(ClienteFinal)
        .join(Cuenta, Cuenta.cliente_final_id == ClienteFinal.id)
        .distinct()
        .count()
    )

    total_cuentas = Cuenta.query.count()
    total_mayoristas = Cuenta.query.filter(Cuenta.cliente_id != None).count()
    total_finales = Cuenta.query.filter(Cuenta.cliente_final_id != None).count()
    cuentas_vencidas = Cuenta.query.filter(Cuenta.fecha_expiracion < datetime.now().date()).count()

    return render_template('admin/dashboard.html',
        total_clientes=total_clientes,
        total_clientes_finales=total_clientes_finales,
        total_mayoristas=total_mayoristas,
        total_finales=total_finales,
        total_cuentas=total_cuentas,
        cuentas_vencidas=cuentas_vencidas
    )


# ---------------------------
# 📋 CLIENTES PREMIUM
# ---------------------------
@panel_bp.route('/clientes')
@login_required
def clientes():
    page = request.args.get('page', 1, type=int)

    # ⚡️ Consulta con COUNT optimizado
    pagination = (
        db.session.query(
            Cliente,
            func.count(Cuenta.id).label('cuentas_count')
        )
        .outerjoin(Cuenta, Cuenta.cliente_id == Cliente.id)
        .group_by(Cliente.id)
        .paginate(page=page, per_page=20)
    )

    return render_template(
        'admin/clientes.html',
        clientes=pagination.items,
        pagination=pagination,
        today=date.today()
    )

@panel_bp.route('/clientes/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_cliente():
    if request.method == 'POST':
        nombre = request.form['nombre']
        telefono = request.form['telefono']
        correo = request.form['correo']   # <- Aquí se usaba el `correo`

        # 🚫 Cliente SIN filtros
        nuevo_cliente = Cliente(
            nombre=nombre,
            telefono=telefono
        )
        db.session.add(nuevo_cliente)
        db.session.commit()

        # ✅ Cuenta CON filtros
        hoy = datetime.now().date()
        nueva_cuenta = Cuenta(
            correo=correo,
            fecha_compra=hoy,
            fecha_expiracion=hoy + timedelta(days=30),
            cliente_id=nuevo_cliente.id,
            filtro_netflix=True,
            filtro_dispositivo=True,
            filtro_actualizar_hogar=True,
            filtro_codigo_temporal=True
        )
        db.session.add(nueva_cuenta)
        db.session.commit()

        flash('✅ Cliente y cuenta creada correctamente.')
        return redirect(url_for('panel.clientes'))

    return render_template('admin/nuevo_cliente.html')


@panel_bp.route('/clientes/<int:cliente_id>/eliminar', methods=['POST'])
@login_required
def eliminar_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    if cliente.cuentas:
        flash('❌ No puedes eliminar este cliente porque tiene cuentas activas.')
    else:
        db.session.delete(cliente)
        db.session.commit()
        flash('✅ Cliente eliminado.')
    return redirect(url_for('panel.clientes'))

@panel_bp.route('/api/cliente/<int:cliente_id>')
@login_required
def api_get_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    return {
        "id": cliente.id,
        "nombre": cliente.nombre,
        "telefono": cliente.telefono
    }

@panel_bp.route('/api/cliente/<int:cliente_id>', methods=['POST'])
@login_required
def api_update_cliente(cliente_id):
    data = request.get_json()
    cliente = Cliente.query.get_or_404(cliente_id)
    cliente.nombre = data.get('nombre')
    cliente.telefono = data.get('telefono')
    db.session.commit()
    return {"success": True}

# ---------------------------
# 📋 CLIENTES FINALES
# ---------------------------
@panel_bp.route('/clientes_finales')
@login_required
def clientes_finales():
    cuentas = (
        db.session.query(Cuenta)
        .options(joinedload(Cuenta.cliente_final))
        .filter(Cuenta.cliente_final_id != None)
        .all()
    )
    today = datetime.now().date()
    return render_template('admin/clientes_finales.html', clientes=clientes)

@panel_bp.route('/api/cuenta_final/<int:cuenta_id>')
@login_required
def api_get_cuenta_final(cuenta_id):
    cuenta = Cuenta.query.get_or_404(cuenta_id)
    return {
        "id": cuenta.id,
        "correo": cuenta.correo,
        "pin_final": cuenta.pin_final,
        "fecha_compra": cuenta.fecha_compra.isoformat(),
        "fecha_expiracion": cuenta.fecha_expiracion.isoformat(),
        "telefono": cuenta.cliente_final.telefono  # ✅ AQUI!
    }

# ✅ NUEVO: Generar PIN Final por fetch()
@panel_bp.route('/api/cuenta_final/<int:cuenta_id>/generar_pin_final', methods=['POST'])
@login_required
def api_generar_pin_final(cuenta_id):
    cuenta = Cuenta.query.get_or_404(cuenta_id)
    nuevo_pin = str(random.randint(1000, 9999))
    cuenta.pin_final = nuevo_pin
    db.session.commit()
    return {"success": True, "nuevo_pin": nuevo_pin}

@panel_bp.route('/api/cuenta_final/<int:cuenta_id>', methods=['POST'])
@login_required
def api_update_cuenta_final(cuenta_id):
    data = request.get_json()
    cuenta = Cuenta.query.get_or_404(cuenta_id)

    # 🔑 SOLO actualiza lo que envías: telefono y correo
    if cuenta.cliente_final:
        cuenta.cliente_final.telefono = data.get('telefono')

    cuenta.correo = data.get('correo')
    # NO SE TOCAN pin_final, fecha_compra, fecha_expiracion
    db.session.commit()
    return {"success": True}
    

    db.session.add(nuevo_cliente)
    db.session.commit()
    hoy = datetime.now().date()
    nueva_cuenta = Cuenta(
        correo=data.get('correo'),
        fecha_compra=hoy,
        fecha_expiracion=hoy + timedelta(days=30),
        cliente_final_id=nuevo_cliente.id,
        filtro_netflix=data.get('filtro_netflix', True),
        filtro_dispositivo=data.get('filtro_dispositivo', True),
        filtro_actualizar_hogar=data.get('filtro_actualizar_hogar', True),
        filtro_codigo_temporal=data.get('filtro_codigo_temporal', True),
        pin_final=str(random.randint(1000, 9999))
    )
    db.session.add(nueva_cuenta)
    db.session.commit()
    return {"success": True}

# ---------------------------
# CUENTAS PREMIUM
# ---------------------------

@panel_bp.route('/cuentas/<int:cliente_id>')
@login_required
def cuentas_cliente(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    cuentas = Cuenta.query.filter_by(cliente_id=cliente.id).order_by(Cuenta.id.asc()).all()
    today = datetime.now().date()

    # 🔑 Forzar que fecha_expiracion sea siempre date (no string)
    for cuenta in cuentas:
        if isinstance(cuenta.fecha_expiracion, str):
            cuenta.fecha_expiracion = datetime.strptime(cuenta.fecha_expiracion, '%Y-%m-%d').date()

    return render_template('admin/cuentas_cliente.html',
                           cliente=cliente,
                           cuentas=cuentas,
                           today=today)


# ---------------------------
# ✅ Ruta para NUEVA CUENTA PREMIUM (Mayoristas)
# ---------------------------
@panel_bp.route('/cuentas/nueva/<int:cliente_id>', methods=['GET', 'POST'])
@login_required
def nueva_cuenta(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    if request.method == 'POST':
        hoy = datetime.now().date()
        fecha_expiracion = hoy + timedelta(days=30)

        filtros = {
            'filtro_netflix': True,
            'filtro_dispositivo': True,
            'filtro_actualizar_hogar': True,
            'filtro_codigo_temporal': True
        }

        if request.form.get('correo_uno'):
            correo = request.form.get('correo_uno').strip()
            db.session.add(
                Cuenta(
                    correo=correo,
                    fecha_compra=hoy,
                    fecha_expiracion=fecha_expiracion,
                    cliente_id=cliente.id,
                    **filtros
                )
            )

        for line in request.form.get('correos_varios', '').split('\n'):
            correo = line.strip()
            if correo:
                db.session.add(
                    Cuenta(
                        correo=correo,
                        fecha_compra=hoy,
                        fecha_expiracion=fecha_expiracion,
                        cliente_id=cliente.id,
                        **filtros
                    )
                )

        db.session.commit()
        flash('✅ Cuenta(s) nueva(s) creada(s) correctamente.')
        return redirect(url_for('panel.cuentas_cliente', cliente_id=cliente.id))

    return render_template('admin/nueva_cuenta.html', cliente=cliente)


@panel_bp.route('/api/cuenta/<int:cuenta_id>')
@login_required
def api_get_cuenta(cuenta_id):
    cuenta = Cuenta.query.get_or_404(cuenta_id)
    return {
        "id": cuenta.id,
        "correo": cuenta.correo,
        "fecha_compra": cuenta.fecha_compra.isoformat(),
        "fecha_expiracion": cuenta.fecha_expiracion.isoformat()
    }

@panel_bp.route('/api/cuenta/<int:cuenta_id>', methods=['POST'])
@login_required
def api_update_cuenta(cuenta_id):
    data = request.get_json()
    cuenta = Cuenta.query.get_or_404(cuenta_id)
    cuenta.correo = data['correo']
    cuenta.fecha_compra = datetime.strptime(data['fecha_compra'], '%Y-%m-%d').date()
    cuenta.fecha_expiracion = datetime.strptime(data['fecha_expiracion'], '%Y-%m-%d').date()
    db.session.commit()
    return {"success": True}


# ---------------------------
# Resto: Renovar, Eliminar, Vencidas, Buscar
# ---------------------------
@panel_bp.route('/cuentas/renovar/<int:cuenta_id>', methods=['POST'])
@login_required
def renovar_cuenta(cuenta_id):
    cuenta = Cuenta.query.get_or_404(cuenta_id)
    hoy = datetime.now().date()

    # 🔑 Base es HOY si ya venció, o fecha_expiracion si aún está activa
    base = max(hoy, cuenta.fecha_expiracion)
    cuenta.fecha_expiracion = base + timedelta(days=30)

    # ✅ NO TOQUES fecha_compra. Se queda como historial.
    # ⚡️ Reactiva filtros si quieres:
    cuenta.filtro_netflix = True
    cuenta.filtro_dispositivo = True
    cuenta.filtro_actualizar_hogar = True
    cuenta.filtro_codigo_temporal = True

    db.session.commit()
    flash('✅ Cuenta renovada +30 días.')
    return redirect(url_for('panel.cuentas_cliente', cliente_id=cuenta.cliente_id))

@panel_bp.route('/cuentas/eliminar/<int:cuenta_id>', methods=['POST'])
@login_required
def eliminar_cuenta(cuenta_id):
    cuenta = Cuenta.query.get_or_404(cuenta_id)
    cliente_id = cuenta.cliente_id
    db.session.delete(cuenta)
    db.session.commit()
    flash('✅ Cuenta eliminada.')
    return redirect(url_for('panel.cuentas_cliente', cliente_id=cliente_id))

@panel_bp.route('/cuentas_vencidas')
@login_required
def cuentas_vencidas():
    cuentas = Cuenta.query.filter(Cuenta.fecha_expiracion < datetime.now().date()).all()
    cuentas_por_cliente = defaultdict(list)
    for cuenta in cuentas:
        cuentas_por_cliente[cuenta.cliente_id].append(cuenta)
    return render_template('admin/cuentas_vencidas.html',
        cuentas=cuentas,
        cuentas_por_cliente=cuentas_por_cliente
    )

@panel_bp.route('/buscar_correo')
@login_required
def buscar_correo():
    cuenta = Cuenta.query.filter_by(correo=request.args.get('correo')).first()
    if cuenta:
        return redirect(url_for('panel.cuentas_cliente', cliente_id=cuenta.cliente_id)) if cuenta.cliente_id else redirect(url_for('panel.clientes_finales'))
    flash("❌ No se encontró ninguna cuenta con ese correo.")
    return redirect(url_for('panel.dashboard'))

@panel_bp.route('/api/cliente/<int:cliente_id>/generar_pin', methods=['POST'])
@login_required
def api_generar_pin(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    nuevo_pin = str(random.randint(1000, 9999))
    cliente.pin_restablecer = nuevo_pin
    db.session.commit()
    return {"success": True, "nuevo_pin": nuevo_pin}

# ✅ API para crear nuevo Cliente Final + su cuenta SIEMPRE con filtros activos
@panel_bp.route('/api/nuevo_cliente_final', methods=['POST'])
@login_required
def api_nuevo_cliente_final():
    data = request.get_json()

    nombre = data.get('nombre')
    telefono = data.get('telefono')
    correo = data.get('correo')

    # ⚙️ Fuerza filtros activos siempre
    filtro_netflix = True
    filtro_dispositivo = True
    filtro_actualizar_hogar = True
    filtro_codigo_temporal = True

    # 1️⃣ Crear ClienteFinal
    nuevo_cliente = ClienteFinal(
        nombre=nombre,
        telefono=telefono
    )
    db.session.add(nuevo_cliente)
    db.session.commit()

    # 2️⃣ Crear Cuenta vinculada con filtros activos
    hoy = datetime.now().date()
    nueva_cuenta = Cuenta(
        correo=correo,
        fecha_compra=hoy,
        fecha_expiracion=hoy + timedelta(days=30),
        cliente_final_id=nuevo_cliente.id,
        filtro_netflix=filtro_netflix,
        filtro_dispositivo=filtro_dispositivo,
        filtro_actualizar_hogar=filtro_actualizar_hogar,
        filtro_codigo_temporal=filtro_codigo_temporal,
        pin_final=str(random.randint(1000, 9999))
    )
    db.session.add(nueva_cuenta)
    db.session.commit()

    return {"success": True}

@panel_bp.route('/cuentas_finales/renovar/<int:cuenta_id>', methods=['POST'])
@login_required
def renovar_cuenta_final(cuenta_id):
    cuenta = Cuenta.query.get_or_404(cuenta_id)
    hoy = datetime.now().date()

    base = max(hoy, cuenta.fecha_expiracion)
    cuenta.fecha_expiracion = base + timedelta(days=30)

    # ✅ NO toques fecha_compra

    # Reactivar filtros:
    cuenta.filtro_netflix = True
    cuenta.filtro_dispositivo = True
    cuenta.filtro_actualizar_hogar = True
    cuenta.filtro_codigo_temporal = True

    db.session.commit()
    flash('✅ Cuenta Final renovada +30 días.')
    return redirect(url_for('panel.clientes_finales'))


@panel_bp.route('/clientes_finales/eliminar/<int:cliente_id>', methods=['POST'])
@login_required
def eliminar_cliente_final(cliente_id):
    cliente = ClienteFinal.query.get_or_404(cliente_id)
    db.session.delete(cliente)  # 💥 Borrará su cuenta también
    db.session.commit()
    flash("✅ Cliente Final eliminado.")
    return redirect(url_for('panel.clientes_finales'))


@panel_bp.route('/clientes/<int:cliente_id>/reportar')
@login_required
def reportar_cuentas(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)

    vencidas = []
    for cuenta in cliente.cuentas:
        if cuenta.fecha_expiracion:
            fecha_exp = cuenta.fecha_expiracion
            fecha_fmt = fecha_exp.strftime('%d/%m/%Y')
            if fecha_exp < datetime.now().date():  #Si prefieres que venza después de la fecha:
                vencidas.append(f"📌 *{cuenta.correo}* (Expiró: {fecha_fmt})")
        else:
            vencidas.append(f"📌 *{cuenta.correo}* (Sin fecha de expiración)")

    if not vencidas:
        mensaje = f"👋 Hola {cliente.nombre}, por ahora no tienes cuentas vencidas. ✅"
    else:
        mensaje = (
            f"👋 Hola *{cliente.nombre}*:\n"
            f"Tienes estas cuentas vencidas:\n\n"
            + "\n".join(vencidas) +
            "\n\nPor favor, contáctame para renovarlas. 🔄"
        )

    mensaje_encoded = quote(mensaje)

    telefono = cliente.telefono or ""
    if telefono.startswith("0"):
        telefono = telefono[1:]
    if not telefono.startswith("51"):
        telefono = "51" + telefono

    whatsapp_link = f"https://wa.me/{telefono}?text={mensaje_encoded}"

    return redirect(whatsapp_link)

# -------------------------------
# 📌 Ruta para CLIENTES FINALES
# -------------------------------

@panel_bp.route('/cuenta_final/<int:cliente_id>/reportar')
@login_required
def reportar_cuenta_final(cliente_id):
    cliente = ClienteFinal.query.get_or_404(cliente_id)

    vencidas = []
    for cuenta in cliente.cuentas:
        if cuenta.fecha_expiracion and cuenta.fecha_expiracion < datetime.now().date():
            vencidas.append(f"📧 {cuenta.correo}")

    if not vencidas:
        mensaje = f"👋 Hola {cliente.nombre}, por ahora no tienes cuentas vencidas. ✅"
    else:
        mensaje = (
            f"👋 Hola {cliente.nombre}:\n"
            f"Tienes estas cuentas vencidas:\n\n"
            + "\n".join(vencidas) +
            "\n\nPor favor, contáctame para renovarlas."
        )

    mensaje_encoded = quote(mensaje)
    telefono = cliente.telefono or ""
    if telefono.startswith("0"):
        telefono = telefono[1:]
    if not telefono.startswith("51"):
        telefono = "51" + telefono

    whatsapp_link = f"https://wa.me/{telefono}?text={mensaje_encoded}"
    return redirect(whatsapp_link)




@panel_bp.route('/api/nueva_cuenta_premium', methods=['POST'])
def api_nueva_cuenta_premium():
    from flask import request, jsonify
    from models import db, Cuenta
    from datetime import datetime, timedelta

    data = request.get_json()

    cliente_id = data.get('cliente_id')
    correo_uno = data.get('correo_uno', '').strip()
    correos_varios = data.get('correos_varios', '').split('\n')
    hoy = datetime.now().date()
    fecha_expiracion = hoy + timedelta(days=30)

    filtros = {
        'filtro_netflix': True,
        'filtro_dispositivo': True,
        'filtro_actualizar_hogar': True,
        'filtro_codigo_temporal': True
    }

    if correo_uno:
        nueva = Cuenta(
            correo=correo_uno,
            fecha_compra=hoy,
            fecha_expiracion=fecha_expiracion,
            cliente_id=cliente_id,
            **filtros
        )
        db.session.add(nueva)

    for line in correos_varios:
        correo = line.strip()
        if correo:
            nueva = Cuenta(
                correo=correo,
                fecha_compra=hoy,
                fecha_expiracion=fecha_expiracion,
                cliente_id=cliente_id,
                **filtros
            )
            db.session.add(nueva)

    db.session.commit()
    return jsonify({'success': True})
