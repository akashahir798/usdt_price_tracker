import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # Database -- set DB_TYPE=mysql to use MySQL, sqlite for local dev
    DB_TYPE = os.environ.get('DB_TYPE', 'sqlite')

    # MySQL settings
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DB = os.environ.get('MYSQL_DB', 'usdt_tracker')

    # SQLite settings (local dev fallback)
    SQLITE_PATH = os.environ.get('SQLITE_PATH', 'usdt_tracker.db')

    # Crypto API
    COIN_API_URL = os.environ.get(
        'COIN_API_URL',
        'https://api.coingecko.com/api/v3'
    )

    # Flask
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
