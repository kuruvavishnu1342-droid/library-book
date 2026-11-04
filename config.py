import os
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'library-secret-key-prod-9a7f3b8c2d1e0f')
    
    # MySQL Database Settings
    MYSQL_HOST = os.getenv('MYSQL_HOST', '127.0.0.1')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
    MYSQL_DB = os.getenv('MYSQL_DB', 'library_book_analysis')
    
    # Preferred DB Mode: 'auto' (tries MySQL, falls back to SQLite), 'mysql', or 'sqlite'
    DB_TYPE = os.getenv('DB_TYPE', 'auto')
    
    # Path to fallback SQLite database
    SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'library.db')
    
    # Default library settings
    DEFAULT_BORROW_DAYS = int(os.getenv('DEFAULT_BORROW_DAYS', 14))
    
    # Static paths
    CHARTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'images', 'generated')
