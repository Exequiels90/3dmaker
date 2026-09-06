import sqlite3

def migrate():
    # Ruta de la base de datos en PythonAnywhere
    db_path = '/home/Exequiels90/mysite/so.sqlite'  # Ajusta esta ruta según tu configuración
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Agregar columna material_cost si no existe
        try:
            cursor.execute('ALTER TABLE product ADD COLUMN material_cost FLOAT DEFAULT 0')
            print("Column 'material_cost' added successfully")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("Column 'material_cost' already exists")
            else:
                raise
        
        # Agregar columna power_consumption si no existe
        try:
            cursor.execute('ALTER TABLE product ADD COLUMN power_consumption FLOAT DEFAULT 0')
            print("Column 'power_consumption' added successfully")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print("Column 'power_consumption' already exists")
            else:
                raise
        
        conn.commit()
        conn.close()
        print("Migration completed successfully")
        
    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == '__main__':
    migrate()
