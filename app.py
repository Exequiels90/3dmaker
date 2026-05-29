from flask import Flask
from models import db, GlobalConfig
from routes import main as main_blueprint
import os
import time


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
