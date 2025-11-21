from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt

# ======================================================================
# Inicialización de las Extensiones
# Se instancian las clases, pero NO se enlazan aún a la aplicación (app).
# Esto se hace después en app.py (db.init_app(app)).
# ======================================================================

db = SQLAlchemy()
# Comentario clave: Instancia principal para la gestión de la base de datos (SQLAlchemy).

bcrypt = Bcrypt()
# Comentario clave: Instancia para el hashing seguro de contraseñas.

login_manager = LoginManager()
# Comentario clave: Instancia para la gestión de sesiones de usuario (Flask-Login).

login_manager.login_view = "auth.login"
# Comentario clave: Redirige a esta ruta (Blueprint 'auth', función 'login') 
# cuando se intenta acceder a una ruta protegida sin haber iniciado sesión.