"""
Script standalone para enviar un backup semanal de la base de datos por email.

Este script NO corre solo: hay que programarlo desde la pestaña "Tasks" de
PythonAnywhere para que se ejecute automáticamente (por ejemplo, una vez por
semana). Ver GUIA_USO.md para el paso a paso.

Uso manual (para probarlo a mano por consola):
    python3 backup.py

Requiere que en Configuración > Backup automático estén cargados:
    - Email de destino
    - Cuenta de Gmail remitente
    - Contraseña de aplicación de Gmail (no la contraseña normal de la cuenta)
    - El interruptor "Backup automático activado"
"""
import sys
from app import create_app
from routes import send_backup_email

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        ok, message = send_backup_email(force=False)
        if ok:
            print(f"✅ {message}")
            sys.exit(0)
        else:
            print(f"⚠️ Backup no enviado: {message}")
            # Salimos con código 0 igual: si el backup está desactivado no es un
            # error real, y no queremos que PythonAnywhere marque el Task como fallido
            # por eso. Si querés que sí falle cuando hay error real, cambiá a sys.exit(1).
            sys.exit(0)
