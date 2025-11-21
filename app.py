# app.py (Modificación clave para Render/Producción)

from flask import Flask, redirect, url_for # type: ignore
from extensions import db, login_manager, bcrypt
from auth import auth_bp
from dashboard import dashboard_bp
from files import files_bp
from models import Docente, Carrera, Materia, Alumno, Curso, Reporte
from datetime import datetime
from sqlalchemy.exc import IntegrityError # Para manejo de errores en DB
import os 

def create_app():
    app = Flask(__name__)
    
    # Configuración básica
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'clave-secreta-de-desarrollo-fallback')
    
    # Mantiene SQLite para pruebas rápidas (Recuerda: los datos se perderán)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db' 
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Inicializar extensiones
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # Configuración de Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return Docente.query.get(int(user_id))

    # Registrar blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(files_bp) 
    
    # Inicializar la base de datos y añadir carreras
    with app.app_context():
        db.create_all()
        
     # app.py (dentro de create_app(), en el bloque db.create_all())

        # Inicialización de Carreras
        if Carrera.query.count() == 0:
            carreras = [
                # --- CAMPUS JUCHITÁN ---
                {"nombre": "Licenciatura en Nutrición", "campus": "Juchitán"},
                {"nombre": "Licenciatura en Enfermería", "campus": "Juchitán"},

                # --- CAMPUS IXTEPEC ---
                {"nombre": "Lic. en Ciencias Empresariales", "campus": "Ixtepec"},
                {"nombre": "Lic. en Derecho", "campus": "Ixtepec"},
                {"nombre": "Ing. en Desarrollo de Software y Sistemas Inteligentes", "campus": "Ixtepec"},
                {"nombre": "Ing. en Logística y Cadenas de suministros", "campus": "Ixtepec"},
                {"nombre": "Lic. en Comercio Exterior y Gestión de Aduanas", "campus": "Ixtepec"},
                {"nombre": "Lic. en Administración Pública", "campus": "Ixtepec"},
                {"nombre": "Lic. en Informática", "campus": "Ixtepec"},
                
                # --- CAMPUS TEHUANTEPEC (Confirmado como correcto) ---
                {"nombre": "Ingeniería Química", "campus": "Tehuantepec"},
                {"nombre": "Ingeniería de Petróleos", "campus": "Tehuantepec"},
                {"nombre": "Ingeniería en Diseño", "campus": "Tehuantepec"},
                {"nombre": "Ingeniería en Computación", "campus": "Tehuantepec"},
                {"nombre": "Ingeniería Industrial", "campus": "Tehuantepec"},
                {"nombre": "Licenciatura en Matemáticas Aplicadas", "campus": "Tehuantepec"},
                {"nombre": "Ingeniería en Energías Renovables", "campus": "Tehuantepec"}
            ]
            for carrera_data in carreras:
                nueva_carrera = Carrera(nombre=carrera_data["nombre"], campus=carrera_data["campus"])
                db.session.add(nueva_carrera)
            db.session.commit()

    
    # app.py

# ... (código existente)

def create_app():
    app = Flask(__name__)
    
    # ... (Configuraciones e inicialización de extensiones)
    
    # Registrar blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(files_bp) 
    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))
    # ==========================================================
    
    # Inicializar la base de datos y añadir carreras
    with app.app_context():
        # ... (código de inicialización de DB)



        return app

if __name__ == '__main__':
    # Creación de la carpeta 'uploads' si no existe
    upload_dir = 'uploads'
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        
    app = create_app()
    app.run(debug=True)