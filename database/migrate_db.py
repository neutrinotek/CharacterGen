import sqlite3
import os


def migrate_database():
    """
    Migrate the database to add the status column and update existing records.
    """
    # Get the database path
    db_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(db_dir, 'app.db')

    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Start a transaction
        cursor.execute("BEGIN TRANSACTION")

        # Check if status column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = cursor.fetchall()
        status_exists = any(column[1] == 'status' for column in columns)

        if not status_exists:
            print("Starting migration process...")

            # Create new table with correct schema
            cursor.execute("""
                CREATE TABLE users_new (
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

            # Get existing columns from old table
            cursor.execute("PRAGMA table_info(users)")
            old_columns = [column[1] for column in cursor.fetchall()]

            # Copy data from old table to new table
            old_columns_str = ', '.join(col for col in old_columns if col != 'status')
            cursor.execute(f"""
                INSERT INTO users_new ({old_columns_str}, status)
                SELECT {old_columns_str},
                    CASE 
                        WHEN role = 'admin' THEN 'approved'
                        ELSE 'pending'
                    END as status
                FROM users
            """)

            # Drop old table
            cursor.execute("DROP TABLE users")

            # Rename new table to users
            cursor.execute("ALTER TABLE users_new RENAME TO users")

            # Recreate indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")

            print("Migration completed successfully")
        else:
            print("Status column already exists")

        # Commit the transaction
        cursor.execute("COMMIT")
        conn.commit()

    except Exception as e:
        cursor.execute("ROLLBACK")
        conn.rollback()
        print(f"Error during migration: {e}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()