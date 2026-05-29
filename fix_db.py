import os
import sys

# Add directory to path
sys.path.insert(0, r'c:\Users\PC-001-8325\Pictures\so')

# Delete old database
db_path = r'c:\Users\PC-001-8325\Pictures\so\so.sqlite'
if os.path.exists(db_path):
    try:
        os.remove(db_path)
        print(f'✓ Deleted old database')
    except Exception as e:
        print(f'Error deleting database: {e}')

# Import after potential deletion
from app import create_app

# Create new app with fresh database
app = create_app()
print('✓ Database recreated with new schema!')
print('✓ Ready to start Flask application')
