from app import create_app, db
from models import User

app = create_app()

with app.app_context():
    # Verificar si ya existe un usuario admin
    existing_admin = User.query.filter_by(username='admin').first()
    if existing_admin:
        print('El usuario admin ya existe')
    else:
        # Crear usuario admin
        admin = User(username='admin', role='admin', is_first_login=True)
        admin.set_password('1234')
        db.session.add(admin)
        db.session.commit()
        print('Usuario admin creado exitosamente')
        print('Usuario: admin')
        print('Contraseña: 1234')
