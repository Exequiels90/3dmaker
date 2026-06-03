from app import create_app
from models import db, User

app = create_app()

with app.app_context():
    # Verificar si ya existe el usuario admin
    existing_user = User.query.filter_by(username='admin').first()
    if existing_user:
        print(f"Usuario admin ya existe: {existing_user.username}")
    else:
        # Crear usuario admin
        user = User(username='admin', role='admin', is_first_login=True)
        user.set_password('1234')
        db.session.add(user)
        db.session.commit()
        print("Usuario admin creado exitosamente")
        print("Usuario: admin")
        print("Contraseña: 1234")
