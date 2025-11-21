from flask import Blueprint, request, send_from_directory, jsonify, render_template, abort # type: ignore
from flask_login import login_required, current_user  # type: ignore
from werkzeug.utils import secure_filename 
import os
from datetime import datetime
import json

# Importamos SQLAlchemy y los modelos
from extensions import db
from models import Archivo, Materia, Curso, Docente # Aseguramos los modelos necesarios
from sqlalchemy.exc import IntegrityError, OperationalError 

# Definición del Blueprint para las rutas de archivos
files_bp = Blueprint("files", __name__, url_prefix="/files")

# --- Configuración ---
UPLOAD_FOLDER = 'uploads'
# La creación de la carpeta 'uploads' se maneja en app.py, pero la mantenemos aquí para robustez
os.makedirs(UPLOAD_FOLDER, exist_ok=True) 

# --- Rutas de Vistas y Gestión ---

@files_bp.route("/")
@login_required
def manage_files():
    """Ruta para mostrar la página de gestión de archivos (files.html)."""
    return render_template("files.html")

# =======================================================================
# Provee la data para el autocompletado de Materia y Periodo
# =======================================================================
@files_bp.route("/data_for_upload")
@login_required
def data_for_upload():
    """Ruta (API) para obtener la lista de nombres de materias y periodos existentes para autocompletar."""
    try:
        # Obtener todos los nombres de las Materias existentes
        # Solo necesitamos los nombres como strings para el datalist
        materias_nombres = db.session.query(Materia.nombre).distinct().all()
        materias_list = [m[0] for m in materias_nombres] 

        # Obtener todos los periodos únicos de la tabla Curso
        periodos_unicos = db.session.query(Curso.periodo).distinct().all()
        periodos_list = [p[0] for p in periodos_unicos]

        return jsonify({
            "materias": materias_list,
            "periodos": periodos_list
        })
    except Exception as e:
        print(f"Error al cargar datos para subida: {e}")
        return jsonify({"error": "Error al cargar datos de materias/periodos."}), 500

# =======================================================================
# Recibe Materia y Periodo, y gestiona la creación del Curso si es necesario.
# =======================================================================
@files_bp.route("/upload_pdf", methods=["POST"])
@login_required
def upload_pdf():
    # 1. Obtener datos del formulario
    file = request.files.get("pdfFile")
    materia_name = request.form.get("materia_name", "").strip()
    periodo = request.form.get("periodo", "").strip()

    # Validaciones básicas
    if not file or not file.filename or not materia_name or not periodo:
        return "Faltan el archivo, nombre de materia o periodo.", 400
    
    if not file.filename.lower().endswith('.pdf'):
        return "Formato de archivo no permitido. Solo se aceptan PDFs.", 400

    # Generar un nombre de archivo descriptivo y seguro
    filename_raw = os.path.splitext(file.filename)[0]
    filename = secure_filename(f"{materia_name}_{periodo}_{filename_raw}.pdf")
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    # 2. Asegurar Materia y Curso
    try:
        # A. Buscar/Crear Materia
        materia = Materia.query.filter_by(nombre=materia_name).first()
        if not materia:
            materia = Materia(nombre=materia_name)
            db.session.add(materia)
            db.session.flush() # Para obtener el ID si es nueva

        # B. Buscar/Crear Curso (Docente, Materia, Periodo deben ser únicos)
        curso = Curso.query.filter_by(
            docente_id=current_user.id, 
            materia_id=materia.id, 
            periodo=periodo
        ).first()

        if not curso:
            curso = Curso(
                docente_id=current_user.id, 
                materia_id=materia.id, 
                periodo=periodo
            )
            db.session.add(curso)
            db.session.flush() # Para obtener el ID si es nuevo

        # C. Verificar si el Archivo ya existe en la DB
        if Archivo.query.filter_by(nombre=filename).first():
            return f"El archivo '{filename}' ya existe en la base de datos. Por favor, renombre el archivo a subir.", 409

        # D. Guardar el archivo físicamente
        file.save(filepath)

        # E. Registrar en la base de datos
        archivo = Archivo(
            nombre=filename,
            docente_id=current_user.id,
            curso_id=curso.id,
            fecha_subida=datetime.utcnow()
        )
        db.session.add(archivo)
        db.session.commit()
        
        return "Archivo PDF subido y registrado con éxito.", 200

    except IntegrityError:
        db.session.rollback()
        # Este error es genérico, pero el más común es por nombre de archivo duplicado.
        return f"Error de integridad. El archivo '{filename}' ya existe en la base de datos.", 409
    except Exception as e:
        db.session.rollback()
        print(f"Error al subir el archivo: {e}")
        # Intentar limpiar el archivo si se grabó pero la DB falló
        if os.path.exists(filepath):
             os.remove(filepath)
        return f"Ocurrió un error inesperado al procesar la subida: {str(e)}", 500


# =======================================================================
# RUTAS DE ACCIONES (VISUALIZACIÓN, DESCARGA, ELIMINACIÓN)
# =======================================================================

@files_bp.route("/view/<filename>")
@login_required
def view_file(filename):
    """Permite visualizar el archivo, verificando si el docente tiene acceso."""
    # Buscar el archivo y verificar que pertenezca al docente actual
    archivo = Archivo.query.filter_by(nombre=filename, docente_id=current_user.id).first()
    if not archivo:
        # Usamos abort(404) para archivos que no existen o a los que no tiene acceso
        return abort(404) 
        
    # Usar X-Sendfile o un método similar para servir archivos grandes
    # En Flask, send_from_directory es la forma estándar
    # Configurar el tipo de contenido para visualización directa en el navegador
    return send_from_directory(UPLOAD_FOLDER, filename, mimetype='application/pdf')

@files_bp.route("/downloads/<filename>")
@login_required
def download_file(filename):
    """Permite descargar el archivo, verificando si el docente tiene acceso."""
    # Buscar el archivo y verificar que pertenezca al docente actual
    archivo = Archivo.query.filter_by(nombre=filename, docente_id=current_user.id).first()
    if not archivo:
        return abort(404)
        
    # 'as_attachment=True' fuerza la descarga
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)


@files_bp.route("/delete/<filename>", methods=["DELETE"])
@login_required
def delete_file(filename):
    """Permite eliminar un archivo, verificando si el docente es el propietario."""
    # 1. Buscar y verificar propiedad
    archivo_db = Archivo.query.filter_by(nombre=filename, docente_id=current_user.id).first()
    if not archivo_db:
        return "Error: El archivo no se encontró o no tienes permiso para eliminarlo.", 404
        
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        # 2. Eliminar de la base de datos
        db.session.delete(archivo_db)
        db.session.commit()
        
        # 3. Eliminar del sistema de archivos (físico)
        if os.path.exists(filepath):
            os.remove(filepath)
            
        return f"Archivo '{filename}' eliminado con éxito.", 200
    except Exception as e:
        db.session.rollback()
        print(f"Error al eliminar archivo: {e}")
        return f"Error al eliminar el archivo: {str(e)}", 500

# =======================================================================
# Resuelve el error 'Could not build url for endpoint files.rename'
# =======================================================================
@files_bp.route("/rename", methods=["PUT"])
@login_required
def rename_file():
    """Permite renombrar un archivo, resolviendo el BuildError de files.rename_file."""
    data = request.get_json()
    old_name = data.get('old_name')
    new_name_raw = data.get('new_name')

    if not old_name or not new_name_raw:
        return "Se requiere el nombre antiguo y el nuevo nombre.", 400
        
    # Limpiar y asegurar el nuevo nombre
    clean_new_name = secure_filename(new_name_raw)

    # Asegurar que el nuevo nombre tenga la extensión .pdf
    if not clean_new_name.lower().endswith('.pdf'):
        final_new_name = clean_new_name + ".pdf"
    else:
        final_new_name = clean_new_name

    old_path = os.path.join(UPLOAD_FOLDER, old_name)
    new_path = os.path.join(UPLOAD_FOLDER, final_new_name)
    
    # 1. Buscar y validar en la DB, verificando propiedad
    archivo_db = Archivo.query.filter_by(nombre=old_name, docente_id=current_user.id).first()
    if not archivo_db:
        return "Error: El archivo no se encontró en la base de datos o no tienes permiso.", 404
        
    # 2. Verificar que el nuevo nombre no exista ya en la DB para este u otro usuario
    if Archivo.query.filter_by(nombre=final_new_name).first():
        return "Ya existe un registro en la DB con ese nuevo nombre.", 400

    # 3. Renombrar en el sistema de archivos (Físico)
    try:
        if os.path.exists(old_path):
            os.rename(old_path, new_path)
        else:
            # Si el archivo físico no existe, solo actualizamos la DB (corrupción leve)
            print(f"Advertencia: Archivo físico {old_path} no encontrado, solo se actualizará la DB.")

    except Exception as e:
        return f"Error en el sistema de archivos: {str(e)}", 500
    
    # 4. Actualizar en la base de datos (Lógico)
    try:
        archivo_db.nombre = final_new_name
        db.session.commit()
        return f"Archivo renombrado a '{final_new_name}' con éxito.", 200
    except Exception as e:
        db.session.rollback()
        # Si la DB falla después de renombrar el archivo físico, intentamos revertir el cambio físico
        try:
            os.rename(new_path, old_path)
        except Exception as rollback_e:
            print(f"CRÍTICO: No se pudo revertir el renombrado físico: {rollback_e}")

        print(f"Error al actualizar la DB con el nuevo nombre: {e}")
        return f"Error al renombrar en la base de datos: {str(e)}", 500


# =======================================================================
# Asegura el endpoint 'files.list_files' y la correcta devolución de datos.
# =======================================================================
@files_bp.route("/list_files")
@login_required
def list_files():
    """Ruta (API) para listar los archivos del docente actual, con filtro de búsqueda."""
    search_term = request.args.get('search', '')
    
    try:
        # Consulta base: Archivos del docente actual
        query = Archivo.query.filter_by(docente_id=current_user.id)
        
        # Aplicar filtro si existe un término de búsqueda
        if search_term:
            # Filtra por nombre de archivo, o por Materia o Periodo del Curso asociado
            # Es necesario hacer un JOIN (o usar las relaciones)
            query = query.join(Curso).join(Materia).filter(
                (Archivo.nombre.ilike(f'%{search_term}%')) | # Busca en nombre de archivo
                (Materia.nombre.ilike(f'%{search_term}%')) | # Busca en nombre de materia
                (Curso.periodo.ilike(f'%{search_term}%'))    # Busca en periodo
            )
        
        # Ejecutar la consulta
        archivos = query.order_by(Archivo.fecha_subida.desc()).all()

        files_list = []
        for archivo in archivos:
            # Cargar la relación 'curso' (y a través de ella 'materia') si no está cargada
            curso = archivo.curso
            materia = curso.materia if curso and curso.materia else None

            files_list.append({
                "id": archivo.id,
                "name": archivo.nombre,
                # Combinar Materia y Periodo para la columna Curso
                "course": f"{materia.nombre} ({curso.periodo})" if materia and curso else "Sin Curso",
                # Formato de fecha para el frontend
                "date": archivo.fecha_subida.strftime("%d/%m/%Y %H:%M")
            })
            
        return jsonify({"files": files_list})
        
    except Exception as e:
        print(f"Error al listar archivos: {e}")
        return jsonify({"error": "Error al cargar la lista de archivos."}), 500