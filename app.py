from flask import Flask, session, request, g
from flask_login import LoginManager
from flask_babel import Babel, gettext
from models import db, GlobalConfig, User
from routes import main as main_blueprint
from extensions import limiter
import os
import time
import sqlite3
from datetime import datetime


def _ensure_new_columns(db_path):
    """Migración liviana y no destructiva: agrega columnas nuevas a tablas
    existentes sin borrar datos. Se ejecuta en cada arranque; si la columna
    ya existe, no hace nada. Si la base de datos todavía no existe,
    db.create_all() la va a crear completa (con estas columnas incluidas)."""
    if not os.path.exists(db_path):
        return

    # tabla -> [(columna, definición SQL)]
    required_columns = {
        'global_config': [
            ('telegram_bot_token', 'VARCHAR(200)'),
            ('telegram_chat_id', 'VARCHAR(100)'),
            ('telegram_notify_enabled', 'BOOLEAN DEFAULT 0'),
            ('backup_email_to', 'VARCHAR(200)'),
            ('backup_smtp_user', 'VARCHAR(200)'),
            ('backup_smtp_password', 'VARCHAR(200)'),
            ('backup_enabled', 'BOOLEAN DEFAULT 0'),
            ('backup_last_sent_at', 'DATETIME'),
        ],
        'product': [
            ('video_url', 'VARCHAR(500)'),
        ],
        'customer_order': [
            ('tracking_code', 'VARCHAR(20)'),
            ("tracking_status", "VARCHAR(30) DEFAULT 'Recibido'"),
        ],
    }

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for table, columns in required_columns.items():
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            )
            if not cursor.fetchone():
                continue  # La tabla se creará desde cero con create_all()

            cursor.execute(f"PRAGMA table_info({table})")
            existing = {row[1] for row in cursor.fetchall()}

            for col_name, col_def in columns:
                if col_name not in existing:
                    try:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                        print(f"✓ Columna agregada: {table}.{col_name}")
                    except Exception as col_err:
                        print(f"⚠️ No se pudo agregar {table}.{col_name}: {col_err}")

        # Backfill: asignar tracking_code a pedidos de catálogo que todavía no tengan uno
        # (pedidos creados antes de que existiera esta funcionalidad).
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customer_order'")
            if cursor.fetchone():
                cursor.execute("SELECT id FROM customer_order WHERE tracking_code IS NULL OR tracking_code = ''")
                rows_missing_code = cursor.fetchall()
                if rows_missing_code:
                    import uuid
                    cursor.execute("SELECT tracking_code FROM customer_order WHERE tracking_code IS NOT NULL")
                    used_codes = {r[0] for r in cursor.fetchall()}
                    for (order_id,) in rows_missing_code:
                        code = uuid.uuid4().hex[:10].upper()
                        while code in used_codes:
                            code = uuid.uuid4().hex[:10].upper()
                        used_codes.add(code)
                        cursor.execute("UPDATE customer_order SET tracking_code = ? WHERE id = ?", (code, order_id))
                    print(f"✓ tracking_code asignado a {len(rows_missing_code)} pedido(s) existentes")
        except Exception as backfill_err:
            print(f"⚠️ No se pudo hacer backfill de tracking_code: {backfill_err}")

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Migración liviana omitida: {e}")


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
    
    # Migración liviana no destructiva (agrega columnas nuevas si faltan)
    _ensure_new_columns(db_path)

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

    # Agregar el año actual al contexto (para el footer del catálogo, etc.)
    @app.context_processor
    def inject_current_year():
        return dict(current_year=datetime.utcnow().year)

    # Configure Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder.'
    
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    db.init_app(app)
    limiter.init_app(app)
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
