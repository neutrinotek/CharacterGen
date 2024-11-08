import sqlite3
import os

def recreate_database():
    """
    Completely recreate the database with the correct schema.
    """
    # Get the database path
    db_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(db_dir, 'app.db')

    # Remove existing database if it exists
    if os.path.exists(db_path):
        print("Removing existing database...")
        os.remove(db_path)

    # Connect to create new database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("Creating new database schema...")
        
        # Create users table
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(80) UNIQUE NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password_hash VARCHAR(128) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                is_active BOOLEAN NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                reset_token VARCHAR(100) UNIQUE,
                reset_token_expiry TIMESTAMP
            )
        """)

        # Create login_attempts table
        cursor.execute("""
            CREATE TABLE login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(80) NOT NULL,
                ip_address VARCHAR(45) NOT NULL,
                success BOOLEAN NOT NULL,
                timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX idx_users_username ON users(username)")
        cursor.execute("CREATE INDEX idx_users_email ON users(email)")
        cursor.execute("CREATE INDEX idx_login_attempts_username ON login_attempts(username)")
        cursor.execute("CREATE INDEX idx_login_attempts_ip ON login_attempts(ip_address)")

        conn.commit()
        print("Database recreation completed successfully")

    except Exception as e:
        conn.rollback()
        print(f"Error recreating database: {e}")
        raise

    finally:
        conn.close()

if __name__ == "__main__":
    recreate_database()
