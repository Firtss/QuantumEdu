from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.secret_key = 'clave_secreta_para_sesiones_quantum' # Permite usar sesiones seguras

# ==========================================
# CONFIGURACIÓN DE CONEXIÓN A MYSQL
# ==========================================
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:Santos.12@localhost/QuantumEdu_DB'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==========================================
# MODELO DE USUARIO
# ==========================================
class Usuario(db.Model):
    __tablename__ = 'Usuarios'
    id_usuario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.Enum('Estudiante', 'Lider', 'Administrador'), default='Estudiante')
    strikes = db.Column(db.Integer, default=0)
    fecha_restriccion = db.Column(db.DateTime, nullable=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

# ==========================================
# MODELO DE SOLICITUDES / NOTIFICACIONES
# ==========================================
class Solicitud(db.Model):
    __tablename__ = 'Solicitudes'
    id_solicitud = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('Usuarios.id_usuario'), nullable=False)
    tipo = db.Column(db.Enum('Comunidad', 'Lider'), nullable=False)
    nombre_destino = db.Column(db.String(150), nullable=False)  # Nombre del foro propuesto o comunidad a liderar
    justificacion = db.Column(db.Text, nullable=False)
    estado = db.Column(db.Enum('Pendiente', 'Aprobada', 'Rechazada'), default='Pendiente')
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación para extraer los datos del alumno solicitante de forma ágil
    usuario = db.relationship('Usuario', backref='solicitudes')
# ==========================================
# MODELO DE COMUNIDAD
# ==========================================
class Comunidad(db.Model):
    __tablename__ = 'Comunidades'
    id_comunidad = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    
    # NUEVO CAMPO: Fecha de creación
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    id_lider = db.Column(db.Integer, db.ForeignKey('Usuarios.id_usuario', ondelete='SET NULL'), nullable=True)

# ==========================================
# MODELO DE SUSCRIPCIONES
# ==========================================
class Suscripcion(db.Model):
    __tablename__ = 'suscripciones'
    id_usuario = db.Column(db.Integer, db.ForeignKey('Usuarios.id_usuario', ondelete='CASCADE'), primary_key=True)
    id_comunidad = db.Column(db.Integer, db.ForeignKey('Comunidades.id_comunidad', ondelete='CASCADE'), primary_key=True)
    fecha_suscripcion = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación para acceder directo a los datos de la comunidad desde la suscripción
    comunidad = db.relationship('Comunidad', backref='suscripciones_usuarios')

# ==========================================
# MODELO DE COMENTARIOS 
# ==========================================
class Comentario(db.Model):
    __tablename__ = 'comentarios'
    id_comentario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_publicacion = db.Column(db.Integer, db.ForeignKey('publicaciones.id_publicacion', ondelete='CASCADE'), nullable=False)
    id_autor = db.Column(db.Integer, db.ForeignKey('Usuarios.id_usuario'), nullable=False) 
    contenido = db.Column(db.Text, nullable=False)
    visible = db.Column(db.Integer, default=1) 
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow) 

    autor = db.relationship('Usuario', backref='sus_comentarios')

# ==========================================
# MODELO DE PUBLICACION
# ==========================================
class Publicacion(db.Model):
    __tablename__ = 'publicaciones' 
    id_publicacion = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_comunidad = db.Column(db.Integer, nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('Usuarios.id_usuario'), nullable=False)
    contenido = db.Column(db.Text, nullable=False)
    fecha_publicacion = db.Column(db.DateTime, default=datetime.utcnow)
    imagen_url = db.Column(db.String(255), nullable=True)
    enlace_externo = db.Column(db.String(500), nullable=True)
    documento_url = db.Column(db.String(255), nullable=True)

    autor = db.relationship('Usuario', backref='sus_publicaciones')
    
    # SOLUCIÓN AQUÍ: Expresión nativa directa sin comillas gracias al reordenamiento de clases
    comentarios = db.relationship('Comentario', backref='publicacion', cascade='all, delete-orphan', order_by=Comentario.fecha_creacion.asc())

# ==========================================
# MODELO DE RECURSO
# ==========================================
class Recurso(db.Model):
    __tablename__ = 'recursos' 
    id_recurso = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_comunidad = db.Column(db.Integer, nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('Usuarios.id_usuario'), nullable=False)
    titulo = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(50), nullable=False) 
    enlace = db.Column(db.String(255), nullable=False)
    fecha_subida = db.Column(db.DateTime, default=datetime.utcnow)
    
    autor = db.relationship('Usuario', backref='sus_recursos')

# Ruta para el CSS
@app.route('/styles.css')
@app.route('/css/styles.css')
def serve_css():
    if os.path.exists('css/styles.css'):
        return send_from_directory('css', 'styles.css')
    return send_from_directory('.', 'styles.css')

# ==========================================
# LÓGICA DE AUTENTICACIÓN (LOGIN Y REGISTRO)
# ==========================================

@app.route('/procesar_registro', methods=['POST'])
def procesar_registro():
    nombre = request.form.get('nombre')
    correo = request.form.get('correo')
    password = request.form.get('password')
    
    usuario_existente = Usuario.query.filter_by(correo=correo).first()
    if usuario_existente:
        return "<h3>❌ El correo ya está registrado. Intenta con otro o inicia sesión.</h3><a href='/registro.html'>Regresar</a>"
    
    try:
        nuevo_usuario = Usuario(
            nombre=nombre,
            correo=correo,
            password_hash=password, 
            rol='Estudiante'
        )
        db.session.add(nuevo_usuario)
        db.session.commit()
        
        return redirect('/login.html')
    except Exception as e:
        db.session.rollback()
        return f"<h3>❌ Error al registrar usuario: {str(e)}</h3>"

@app.route('/procesar_login', methods=['POST'])
def procesar_login():
    correo = request.form.get('correo')
    password = request.form.get('password')
    
    usuario = Usuario.query.filter_by(correo=correo, password_hash=password).first()
    
    if usuario:
        session['usuario_id'] = usuario.id_usuario
        session['usuario_nombre'] = usuario.nombre
        session['usuario_rol'] = usuario.rol
        
        if usuario.rol == 'Administrador':
            return redirect('/admin.html')
        elif usuario.rol == 'Lider':
            return redirect('/mis_foros.html')
        else:
            return redirect('/usuario.html')
    else:
        return "<h3>❌ Credenciales incorrectas. Verifica tu correo o contraseña.</h3><a href='/login.html'>Intentar de nuevo</a>"
    
@app.route('/logout')
def logout():
    session.clear()  # Borra de golpe los datos del usuario de la sesión
    return redirect('/login.html')  # Lo manda directo al inicio de sesión

# 1. RUTA PARA VER EL FORO DE UNA COMUNIDAD ESPECÍFICA
@app.route('/comunidad/<int:id_comunidad>')
def ver_comunidad(id_comunidad):
    if not session.get('usuario_id'):
        return redirect('/login.html')
    
    comunidad = Comunidad.query.get_or_404(id_comunidad)
    publicaciones = Publicacion.query.filter_by(id_comunidad=id_comunidad).order_by(Publicacion.fecha_publicacion.desc()).all()
    
    return render_template('foro_grupo.html', comunidad=comunidad, publicaciones=publicaciones)

# 2. RUTA PARA CREAR UNA PUBLICACIÓN (CON SUBIDA DE ARCHIVOS ACTIVA)
@app.route('/comunidad/<int:id_comunidad>/publicar', methods=['POST'])
def crear_publicacion(id_comunidad):
    if not session.get('usuario_id'):
        return redirect('/login.html')

    contenido = request.form.get('contenido_publicacion')
    enlace = request.form.get('enlace_externo')
    user_id = session.get('usuario_id')

    # Garantizar la existencia de la carpeta para las cargas
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Procesamiento seguro de imágenes
    imagen = request.files.get('imagen_adjunta')
    nombre_imagen = None
    if imagen and imagen.filename != '':
        nombre_imagen = secure_filename(imagen.filename)
        imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_imagen))

    # Procesamiento seguro de documentos (PDF, etc.)
    documento = request.files.get('documento_adjunto')
    nombre_doc = None
    if documento and documento.filename != '':
        nombre_doc = secure_filename(documento.filename)
        documento.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_doc))

    if contenido:
        nueva_pub = Publicacion(
            id_comunidad=id_comunidad, 
            id_usuario=user_id, 
            contenido=contenido,
            imagen_url=nombre_imagen,
            enlace_externo=enlace,
            documento_url=nombre_doc
        )
        db.session.add(nueva_pub)
        db.session.commit()

    return redirect(f'/comunidad/{id_comunidad}')

# 3. RUTA PARA ENVIAR UN COMENTARIO
@app.route('/publicacion/<int:id_publicacion>/comentar', methods=['POST'])
def crear_comentario(id_publicacion):
    if not session.get('usuario_id'):
        return redirect('/login.html')
    
    contenido = request.form.get('contenido_comentario')
    user_id = session.get('usuario_id')
    
    publicacion_obj = Publicacion.query.get_or_404(id_publicacion)
    
    if contenido and contenido.strip() != '':
        nuevo_comentario = Comentario(
            id_publicacion=id_publicacion,
            id_autor=user_id, 
            contenido=contenido
        )
        db.session.add(nuevo_comentario)
        db.session.commit()
        
    return redirect(f'/comunidad/{publicacion_obj.id_comunidad}')

# 4. RUTA PARA SUSCRIBIRSE O DESUSCRIBIRSE DE UNA COMUNIDAD
@app.route('/comunidad/<int:id_comunidad>/suscribir', methods=['POST'])
def toggle_suscripcion(id_comunidad):
    if not session.get('usuario_id'):
        return redirect('/login.html')
    
    user_id = session.get('usuario_id')
    
    # Comprobar si ya existe la suscripción
    suscripcion_existente = Suscripcion.query.filter_by(id_usuario=user_id, id_comunidad=id_comunidad).first()
    
    if suscripcion_existente:
        # Si ya existe, lo eliminamos (Desuscribirse)
        db.session.delete(suscripcion_existente)
    else:
        # Si no existe, lo creamos (Suscribirse)
        nueva_sub = Suscripcion(id_usuario=user_id, id_comunidad=id_comunidad)
        db.session.add(nueva_sub)
        
    db.session.commit()
    return redirect('/foro_general.html')

# ==========================================
# RUTA PARA VINCULAR UN LÍDER A UNA COMUNIDAD
# ==========================================
@app.route('/asignar_lider', methods=['POST'])
def asignar_lider():
    id_usuario = request.form.get('id_usuario')
    id_comunidad = request.form.get('id_comunidad')
    
    # Buscamos la comunidad y el usuario (que ya es líder)
    usuario = Usuario.query.get(id_usuario)
    comunidad = Comunidad.query.get(id_comunidad)
    
    if usuario and comunidad:
        # CORREGIDO: Ya no cambiamos el rol. Solo asignamos la comunidad a este líder.
        comunidad.id_lider = usuario.id_usuario
        db.session.commit()
        
    return redirect('/admin.html')

@app.context_processor
def inject_notifications():
    """Inyecta de forma automática las alertas reales en el sidebar.html"""
    user_id = session.get('usuario_id')
    user_rol = session.get('usuario_rol')
    
    if user_id:
        if user_rol == 'Administrador':
            # El administrador ve todas las solicitudes que estén 'Pendientes'
            alertas = Solicitud.query.filter_by(estado='Pendiente').order_by(Solicitud.fecha.desc()).all()
            return dict(solicitudes_pendientes=alertas, total_alertas=len(alertas))
        else:
            # Los estudiantes ven el histórico de resolución de sus propias solicitudes
            mis_alertas = Solicitud.query.filter_by(id_usuario=user_id).order_by(Solicitud.fecha.desc()).limit(5).all()
            # Contamos cuántas de sus solicitudes cambiaron de estado recientemente (ejemplo simplificado)
            alertas_nuevas = Solicitud.query.filter_by(id_usuario=user_id, estado='Aprobada').count()
            return dict(solicitudes_usuario=mis_alertas, total_alertas=alertas_nuevas)
            
    return dict(solicitudes_pendientes=[], solicitudes_usuario=[], total_alertas=0)

# ==========================================
# RUTAS: ENVIAR SOLICITUDES (ESTUDIANTE)
# ==========================================
@app.route('/solicitar_comunidad', methods=['POST'])
def solicitar_comunidad():
    if not session.get('usuario_id'): return redirect('/login.html')
    
    nombre_foro = request.form.get('nombre_propuesto')
    justificacion = request.form.get('justificacion')
    
    nueva_solicitud = Solicitud(
        id_usuario=session['usuario_id'],
        tipo='Comunidad',
        nombre_destino=nombre_foro,
        justificacion=justificacion
    )
    db.session.add(nueva_solicitud)
    db.session.commit()
    flash('¡Tu propuesta de comunidad ha sido enviada al Administrador!', 'success')
    return redirect(request.referrer) # Redirige automáticamente a la página de donde vino el usuario

@app.route('/solicitar_lider', methods=['POST'])
def solicitar_lider():
    if not session.get('usuario_id'): return redirect('/login.html')
    
    nombre_comunidad = request.form.get('comunidad_nombre')
    motivacion = request.form.get('motivacion')
    
    nueva_solicitud = Solicitud(
        id_usuario=session['usuario_id'],
        tipo='Lider',
        nombre_destino=nombre_comunidad,
        justificacion=motivacion
    )
    db.session.add(nueva_solicitud)
    db.session.commit()
    flash('¡Solicitud de Líder registrada! Pendiente de aprobación.', 'success')
    return redirect(request.referrer)

# ==========================================
# RUTAS: ACCIONES ADMINISTRADOR (APROBAR/RECHAZAR)
# ==========================================
@app.route('/admin/solicitud/<int:id_sol>/aprobar', methods=['POST'])
def aprobar_solicitud(id_sol):
    if session.get('usuario_rol') != 'Administrador': return "Acceso denegado", 403
    
    sol = Solicitud.query.get_or_404(id_sol)
    sol.estado = 'Aprobada'
    
    if sol.tipo == 'Comunidad':
        # Creación automática de la Comunidad Real en la Base de Datos
        # Ajusta los campos según las columnas exactas de tu modelo Comunidad
        nueva_comunidad = Comunidad(
            nombre=sol.nombre_destino,
            descripcion=sol.justificacion,
            categoria='General',  # Puedes mejorar esto pidiendo al usuario que elija una categoría en la solicitud
            id_lider=None  # Inicialmente sin líder o asigna al proponente si deseas
        )
        db.session.add(nueva_comunidad)
        
    elif sol.tipo == 'Lider':
        # Buscamos la comunidad correspondiente por su nombre para asignarle el líder
        comunidad = Comunidad.query.filter_by(nombre=sol.nombre_destino).first()
        if comunidad:
            comunidad.id_lider = sol.id_usuario
        
        # Ascendemos el Rol del Usuario solicitante a 'Lider'
        usuario_solicitante = Usuario.query.get(sol.id_usuario)
        if usuario_solicitante:
            usuario_solicitante.rol = 'Lider'
            
    db.session.commit()
    flash('Solicitud aprobada con éxito.', 'success')
    return redirect(request.referrer)

@app.route('/admin/solicitud/<int:id_sol>/rechazar', methods=['POST'])
def rechazar_solicitud(id_sol):
    if session.get('usuario_rol') != 'Administrador': return "Acceso denegado", 403
    
    sol = Solicitud.query.get_or_404(id_sol)
    sol.estado = 'Rechazada'
    db.session.commit()
    flash('La solicitud ha sido rechazada.', 'warning')
    return redirect(request.referrer)

# ==========================================
# RUTA: ELIMINAR COMUNIDAD REAL (ADMIN)
# ==========================================
@app.route('/admin/comunidad/<int:id_com>/eliminar', methods=['POST'])
def eliminar_comunidad(id_com):
    # Verificación estricta de seguridad
    if session.get('usuario_rol') != 'Administrador': 
        return "Acceso denegado. Se requieren permisos de Administrador.", 403
    
    comunidad = Comunidad.query.get_or_404(id_com)
    nombre_borrado = comunidad.nombre
    
    try:
        # 1. ELIMINAR SUSCRIPCIONES (Esto soluciona el error de "blank-out")
        Suscripcion.query.filter_by(id_comunidad=id_com).delete()
        
        # 2. ELIMINAR PUBLICACIONES Y RECURSOS
        # Buscamos todas las publicaciones de la comunidad y las borramos
        publicaciones = Publicacion.query.filter_by(id_comunidad=id_com).all()
        for pub in publicaciones:
            db.session.delete(pub) # Esto activará la cascada y borrará sus comentarios
            
        Recurso.query.filter_by(id_comunidad=id_com).delete()

        # 3. AHORA SÍ, BORRAMOS LA COMUNIDAD LIMPIA
        db.session.delete(comunidad)
        db.session.commit()
        
        flash(f'La comunidad "{nombre_borrado}" y todos sus datos han sido eliminados.', 'danger')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al intentar eliminar la comunidad: {str(e)}', 'warning')
        
    return redirect(request.referrer)

# ==========================================
# RUTA: CREAR COMUNIDAD MANUALMENTE (ADMIN)
# ==========================================
@app.route('/crear_comunidad', methods=['POST'])
def crear_comunidad():
    # 1. Verificación de seguridad
    if session.get('usuario_rol') != 'Administrador':
        return "Acceso denegado. Solo administradores pueden crear foros.", 403

    # 2. Capturar los datos del formulario de admin.html
    nombre = request.form.get('nombre_comunidad')
    categoria = request.form.get('categoria_comunidad')
    descripcion = request.form.get('descripcion_comunidad')

    # ========================================================
    # NUEVO: Verificar si el nombre ya está ocupado en la BD
    # ========================================================
    comunidad_existente = Comunidad.query.filter_by(nombre=nombre).first()
    if comunidad_existente:
        flash(f'Atención: Ya existe una comunidad llamada "{nombre}". Por favor elige un nombre distinto.', 'warning')
        return redirect(request.referrer)

    # 3. Crear el objeto para la Base de Datos si el nombre está libre
    nueva_comunidad = Comunidad(
        nombre=nombre,
        categoria=categoria,
        descripcion=descripcion,
        id_lider=None 
    )

    try:
        db.session.add(nueva_comunidad)
        db.session.commit()
        flash(f'¡La comunidad "{nombre}" se creó exitosamente! Ya es visible en el sistema.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Hubo un error al crear la comunidad: {str(e)}', 'danger')

    # 4. Recargar la página actual del Administrador
    return redirect(request.referrer)

# ==========================================
# RUTA: ELIMINAR PUBLICACIÓN (LÍDER/ADMIN)
# ==========================================
@app.route('/eliminar_publicacion/<int:id_publicacion>', methods=['POST'])
def eliminar_publicacion(id_publicacion):
    if not session.get('usuario_id'):
        return redirect('/login.html')

    user_id = session.get('usuario_id')
    user_rol = session.get('usuario_rol')
    
    publicacion = Publicacion.query.get_or_404(id_publicacion)
    comunidad = Comunidad.query.get(publicacion.id_comunidad)
    
    # Validar que sea Administrador, o el Líder de ESTA comunidad, o el autor del post
    if user_rol == 'Administrador' or comunidad.id_lider == user_id or publicacion.id_usuario == user_id:
        try:
            db.session.delete(publicacion)
            db.session.commit()
            flash('Publicación eliminada correctamente.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al eliminar la publicación: {str(e)}', 'danger')
    else:
        flash('No tienes permiso para eliminar esta publicación.', 'danger')
        
    return redirect(request.referrer)

# ==========================================
# RUTA: ELIMINAR COMENTARIO (LÍDER/ADMIN)
# ==========================================
@app.route('/eliminar_comentario/<int:id_comentario>', methods=['POST'])
def eliminar_comentario(id_comentario):
    if not session.get('usuario_id'):
        return redirect('/login.html')

    user_id = session.get('usuario_id')
    user_rol = session.get('usuario_rol')
    
    comentario = Comentario.query.get_or_404(id_comentario)
    publicacion = Publicacion.query.get(comentario.id_publicacion)
    comunidad = Comunidad.query.get(publicacion.id_comunidad)
    
    # Validar que sea Administrador, o el Líder de ESTA comunidad, o el autor del comentario
    if user_rol == 'Administrador' or comunidad.id_lider == user_id or comentario.id_autor == user_id:
        try:
            db.session.delete(comentario)
            db.session.commit()
            flash('Comentario eliminado.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al eliminar el comentario: {str(e)}', 'danger')
    else:
        flash('No tienes permiso para eliminar este comentario.', 'danger')
        
    return redirect(request.referrer)
# ==========================================
# RUTA: CONSULTAR LA BIBLIOTECA DE RECURSOS (CORREGIDA Y SINCRONIZADA)
# ==========================================
@app.route('/biblioteca')
def biblioteca():
    # 1. Obtener parámetros y limpiar espacios en blanco laterales
    buscar = request.args.get('buscar', default='').strip()
    comunidad_id = request.args.get('comunidad_id', default='').strip()

    # 2. Consulta base uniendo Publicación, Comunidad y Usuario
    query = db.session.query(
        Publicacion.id_publicacion.label('id_recurso'),
        Publicacion.contenido.label('titulo'), 
        Publicacion.documento_url.label('documento_url'),
        Publicacion.enlace_externo.label('enlace'),
        Publicacion.id_comunidad.label('id_comunidad'),
        Comunidad.nombre.label('comunidad_nombre'),
        Usuario.nombre.label('autor_nombre')
    ).join(Comunidad, Publicacion.id_comunidad == Comunidad.id_comunidad)\
     .join(Usuario, Publicacion.id_usuario == Usuario.id_usuario)\
     .filter(
         ((Publicacion.documento_url.isnot(None)) & (Publicacion.documento_url != '')) | 
         ((Publicacion.enlace_externo.isnot(None)) & (Publicacion.enlace_externo != ''))
     )

    # 3. EVALUACIÓN ESTRICTA DE FILTROS
    # Solo busca si el usuario ingresó texto real
    if buscar and buscar != '':
        query = query.filter(Publicacion.contenido.like(f"%{buscar}%"))
        
    # Validación quirúrgica para la comunidad: debe existir, no estar vacía y ser un número válido
    if comunidad_id and comunidad_id != '' and comunidad_id.lower() != 'none':
        try:
            # Forzamos conversión a entero. Si es un número real, filtra.
            id_numerico = int(comunidad_id)
            query = query.filter(Publicacion.id_comunidad == id_numerico)
        except ValueError:
            # Si es un string vacío "" o "None", ignoramos el filtro para mostrar TODO
            pass

    # 4. Ordenar cronológicamente (más recientes primero) y ejecutar
    recursos_existentes = query.order_by(Publicacion.id_publicacion.desc()).all()
    
    # 5. Listar comunidades para el selector dropdown del HTML
    lista_comunidades = Comunidad.query.all()

    return render_template('biblioteca.html', 
                           recursos=recursos_existentes, 
                           todas_comunidades=lista_comunidades)
# ==========================================
# RUTA: A PLICACIONES EN DESARROLLO (SOLO VISTA DE PRUEBA)
# ==========================================
@app.route('/aplicaciones')
def aplicaciones():
    # Renderiza la nueva vista de aplicaciones en desarrollo
    return render_template('aplicacion.html')
# ==========================================
# ENRUTADOR DE PÁGINAS ESTÁTICAS
# ==========================================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/<string:page>.html')
def serve_pages(page):
    try:
        user_id = session.get('usuario_id')

        # ==========================================================
        # CASO 1: Foro General (Carga Comunidades y Suscripciones)
        # ==========================================================
        if page == 'foro_general':
            comunidades_db = Comunidad.query.all() 
            suscritas_ids = []
            if user_id:
                # Obtenemos los IDs de las comunidades a las que el usuario actual ya se suscribió
                suscritas_ids = [s.id_comunidad for s in Suscripcion.query.filter_by(id_usuario=user_id).all()]
            
            return render_template('foro_general.html', comunidades=comunidades_db, suscritas_ids=suscritas_ids)

        # ==========================================================
        # CASO 2: Espacio del Alumno (Muestra comunidades SUSCRITAS)
        # ==========================================================
        if page in ['usuario', 'mis_comunidades']:
            if not user_id:
                return redirect('/login.html')
            
            suscripciones = Suscripcion.query.filter_by(id_usuario=user_id).all()
            mis_comunidades = [s.comunidad for s in suscripciones]
            
            return render_template(f'{page}.html', mis_comunidades=mis_comunidades)

        # ==========================================================
        # CASO 3: Panel de Administrador
        # ==========================================================
        if page == 'admin':
            if not user_id or session.get('usuario_rol') != 'Administrador':
                return redirect('/login.html')
                
            comunidades_db = Comunidad.query.all()
            usuarios_db = Usuario.query.all()
            return render_template('admin.html', comunidades=comunidades_db, usuarios=usuarios_db)

        # ==========================================================
        # CASO 4: Espacio del Líder (Muestra comunidades que LIDERA)
        # ==========================================================
        if page == 'mis_foros':
            if not user_id or session.get('usuario_rol') not in ['Lider', 'Administrador']:
                return redirect('/login.html')
            
            comunidades_lideradas = Comunidad.query.filter_by(id_lider=user_id).all()
            return render_template('mis_foros.html', mis_comunidades=comunidades_lideradas)
        
        # ==========================================================
        # CASO: Mi Inicio (usuario.html) - Lógica de Recomendaciones
        # ==========================================================
        if page == 'usuario':
            user_id = session.get('usuario_id')
            if not user_id:
                return redirect('/login.html')
            
            # 1. Obtener IDs de las comunidades a las que el usuario ya está suscrito
            suscripciones = Suscripcion.query.filter_by(id_usuario=user_id).all()
            ids_seguidas = [s.id_comunidad for s in suscripciones]
            
            # 2. Obtener las categorías de esas comunidades
            comunidades_seguidas = Comunidad.query.filter(Comunidad.id_comunidad.in_(ids_seguidas)).all()
            # Usamos un Set para eliminar categorías duplicadas
            categorias_interes = list(set([c.categoria for c in comunidades_seguidas]))
            
            recomendaciones = []
            
            # 3. Buscar comunidades de la misma categoría que el usuario NO siga
            if categorias_interes:
                recomendaciones = Comunidad.query.filter(
                    Comunidad.categoria.in_(categorias_interes),
                    ~Comunidad.id_comunidad.in_(ids_seguidas) # El símbolo ~ es "NOT IN"
                ).limit(15).all()
                
            # 4. Si es un usuario nuevo (no sigue nada) o no hay suficientes recomendaciones, rellenamos
            if len(recomendaciones) < 4:
                faltantes = 4 - len(recomendaciones)
                # Excluimos las que ya sigue y las que ya están en recomendaciones
                ids_excluir = ids_seguidas + [r.id_comunidad for r in recomendaciones]
                extra = Comunidad.query.filter(
                    ~Comunidad.id_comunidad.in_(ids_excluir)
                ).order_by(Comunidad.id_comunidad.desc()).limit(faltantes).all()
                recomendaciones.extend(extra)
                
            return render_template('usuario.html', recomendaciones=recomendaciones)   
        # CASO 5: Páginas estáticas normales (login, registro, index, etc)
        return render_template(f'{page}.html')
        
    except Exception as e:
        return f"<h3>La página '{page}.html' no se encuentra. Error: {e}</h3>", 404

if __name__ == '__main__':
    app.run(debug=True)