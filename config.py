import os
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

class Config:
    # Flask Secret Key
    SECRET_KEY = os.getenv('SECRET_KEY', 'library-secret-key-prod-9a7f3b8c2d1e0f')
    
    # External Cloud MySQL Database Settings (Vercel standard)
    DB_HOST = os.getenv('DB_HOST') or os.getenv('MYSQL_HOST', '127.0.0.1')
    DB_PORT = int(os.getenv('DB_PORT') or os.getenv('MYSQL_PORT', 3306))
    DB_USER = os.getenv('DB_USER') or os.getenv('MYSQL_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD') or os.getenv('MYSQL_PASSWORD', '')
    DB_NAME = os.getenv('DB_NAME') or os.getenv('MYSQL_DB', 'library_book_analysis')
    
    # SSL Mode for Cloud Providers (e.g., TiDB Cloud, Aiven, Railway, AWS RDS)
    DB_SSL = os.getenv('DB_SSL', 'false').lower() in ('true', '1', 't', 'required')
    
    # Default library circulation settings
    DEFAULT_BORROW_DAYS = int(os.getenv('DEFAULT_BORROW_DAYS', 14))
    
    # Path to fallback local database if cloud credentials not yet supplied
    SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'library.db')
