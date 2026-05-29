#!/usr/bin/env python3
"""
Script para recrear la base de datos con el esquema correcto
"""
import os
import sys

# Agregar el directorio actual al path
sys.path.insert(0, 'c:\\Users\\PC-001-8325\\Pictures\\so')

from app import create_app
from models import db

# Ruta de la base de datos
db_path = 'c:\\Users\\PC-001-8325\\Pictures\\so\\so.sqlite'

# Eliminar la base de datos antigua si existe
if os.path.exists(db_path):
    os.remove(db_path)
    print(f"✓ Deleted old database: {db_path}")

# Crear la aplicación y la nueva base de datos
app = create_app(db_path)

print(f"✓ Created new database at: {db_path}")
print("✓ All tables created successfully!")
print("\nDatabase schema is now up-to-date with all required tables:")
print("  - Supplier, Material, Printer, MaintenanceLog")
print("  - Product, Customer, Order, OrderItem")
print("  - WasteLog, GlobalConfig")
print("\nYou can now start the application with: python app.py")
