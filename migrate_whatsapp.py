import sqlite3

def migrate():
    conn = sqlite3.connect('so.sqlite')
    cursor = conn.cursor()
    
    try:
        # Add whatsapp_url column
        cursor.execute('ALTER TABLE global_config ADD COLUMN whatsapp_url TEXT')
        print("Column 'whatsapp_url' added successfully to global_config table")
    except Exception as e:
        print(f"Error adding whatsapp_url: {e}")
    
    conn.commit()
    conn.close()
    print("Migration completed")

if __name__ == '__main__':
    migrate()
