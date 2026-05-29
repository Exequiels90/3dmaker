#!/usr/bin/env python3
"""
Script para limpiar la base de datos corrompida
Ejecutar ANTES de iniciar la aplicación
"""
import os
import sys
import time

db_path = r'c:\Users\PC-001-8325\Pictures\so\so.sqlite'

print("=" * 60)
print("DATABASE CLEANUP UTILITY")
print("=" * 60)

if os.path.exists(db_path):
    print(f"\n📦 Found database file: {db_path}")
    print(f"📊 File size: {os.path.getsize(db_path)} bytes")
    
    try:
        print("\n🔄 Attempting to delete corrupted database...")
        os.remove(db_path)
        time.sleep(0.5)
        
        if not os.path.exists(db_path):
            print("✅ Database successfully deleted!")
            print("\n✨ The next time you run 'python app.py', a new clean database will be created automatically.")
        else:
            print("❌ Could not verify deletion. File still exists.")
            sys.exit(1)
    
    except PermissionError:
        print("❌ Permission denied - database file is in use.")
        print("   Please close Flask (Ctrl+C) and try again.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
else:
    print(f"\n✓ No database file found at {db_path}")
    print("  (This is fine - it will be created on first run)")

print("\n" + "=" * 60)
print("Cleanup complete! Ready to start the application.")
print("=" * 60)
