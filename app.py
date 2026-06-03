from flask import Flask, session, request, g
from flask_login import LoginManager
from flask_babel import Babel, gettext
from models import db, GlobalConfig, User
from routes import main as main_blueprint
import os
import time


def get_locale():
    """Obtener el idioma preferido del usuario"""
    # 1. Verificar si el usuario seleccionó un idioma en la sesión
    if 'language' in session:
        return session['language']
    # 2. Verificar el idioma del navegador
    return request.accept_languages.best_match(['es', 'en']) or 'es'


def create_app(database_path=None):
    app = Flask(__name__)
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = database_path or os.path.join(basedir, 'so.sqlite')
    
    # Force delete old database if it exists to avoid schema conflicts
    force_delete_db = os.environ.get('FORCE_RESET_DB', 'false').lower() == 'true'
    if os.path.exists(db_path) and force_delete_db:
        try:
            os.remove(db_path)
            print(f"✓ Deleted old database: {db_path}")
            time.sleep(0.5)  # Brief pause to ensure file is released
        except Exception as e:
            print(f"⚠️ Could not delete database: {e}")
    
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = 'dev-secret-key-change-in-production'
    
    # Configurar Flask-Babel
    app.config['BABEL_DEFAULT_LOCALE'] = 'es'
    app.config['BABEL_SUPPORTED_LOCALES'] = ['es', 'en']
    app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'
    babel = Babel(app)
    babel.init_app(app, locale_selector=get_locale)
    
    # Agregar función de traducción al contexto global
    @app.context_processor
    def inject_babel():
        return dict(_=gettext)

    # Agregar configuración global al contexto
    @app.context_processor
    def inject_config():
        try:
            config = GlobalConfig.get_singleton()
            return dict(config=config)
        except:
            return dict(config=None)

    # Configure Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder.'
    
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    db.init_app(app)
    app.register_blueprint(main_blueprint)

    with app.app_context():
        try:
            db.create_all()
            # Ensure GlobalConfig singleton exists
            config = GlobalConfig.get_singleton()
            print("✅ Database initialized successfully!")
        except Exception as e:
            # If there's a schema mismatch error
            if 'no such column' in str(e).lower() or 'operational error' in str(e).lower():
                print(f"⚠️ Database schema error detected")
                print("🔄 Attempting to recover by deleting and recreating database...")
                db.session.rollback()
                
                try:
                    # Try to close all connections first
                    db.engine.dispose()
                    time.sleep(0.5)
                    
                    # Delete the physical file
                    if os.path.exists(db_path):
                        os.remove(db_path)
                        print(f"✓ Deleted corrupted database")
                        time.sleep(0.5)
                    
                    # Reinitialize everything
                    db.create_all()
                    config = GlobalConfig.get_singleton()
                    print("✅ Database successfully recreated!")
                except Exception as recovery_error:
                    print(f"❌ Recovery failed: {recovery_error}")
                    raise
            else:
                raise

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
