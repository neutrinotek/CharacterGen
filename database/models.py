from datetime import datetime, timedelta
import sqlite3
import os
import bcrypt
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
import secrets

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    status = db.Column(db.String(20), nullable=False, default='pending')
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    reset_token = db.Column(db.String(100), unique=True, nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    def __init__(self, username, email, password, role='user'):
        self.username = username
        self.email = email
        self.set_password(password)
        self.role = role
        self.status = 'approved' if role == 'admin' else 'pending'
        self.is_active = (role == 'admin')
        self.created_at = datetime.utcnow()

    def set_password(self, password):
        """Hash the password before storing."""
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)

    def check_password(self, password):
        """Verify the password."""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash)

    def generate_reset_token(self):
        """Generate a password reset token."""
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=24)
        return self.reset_token

    def is_reset_token_valid(self, token):
        """Check if the reset token is valid and not expired."""
        return (self.reset_token == token and 
                self.reset_token_expiry and 
                self.reset_token_expiry > datetime.utcnow())

    @property
    def is_admin(self):
        """Check if user has admin role."""
        return self.role == 'admin'

    @property
    def is_pending(self):
        """Check if user is pending approval."""
        return self.status == 'pending'

class LoginAttempt(db.Model):
    __tablename__ = 'login_attempts'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False)
    success = db.Column(db.Boolean, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class PasswordResetRequest(db.Model):
    __tablename__ = 'password_reset_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, approved, rejected, completed
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime, nullable=True)
    
    user = db.relationship('User', backref=db.backref('reset_requests', lazy=True))
    
    def is_valid(self):
        """Check if the reset request is still valid (not expired)."""
        if self.status != 'approved':
            return False
        expiry_time = self.approved_at + timedelta(hours=24) if self.approved_at else None
        return expiry_time and expiry_time > datetime.utcnow()

def init_db(app):
    """Initialize the database and create an admin user if none exists."""
    db_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(db_dir, 'app.db')
    
    with app.app_context():
        # Check if database exists
        if not os.path.exists(db_path):
            print("Database not found. Creating new database...")
            # Create all tables
            db.create_all()
            
            # Create admin user
            admin_username = os.getenv('ADMIN_USERNAME', 'admin')
            admin_password = os.getenv('ADMIN_PASSWORD', 'changeme')
            admin_email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
            
            admin = User(
                username=admin_username,
                email=admin_email,
                password=admin_password,
                role='admin'
            )
            
            try:
                db.session.add(admin)
                db.session.commit()
                print("Admin user created successfully")
            except SQLAlchemyError as e:
                db.session.rollback()
                print(f"Error creating admin user: {str(e)}")
        else:
            # Database exists, just ensure all tables are created
            db.create_all()
            
            # Check if we need to add the status column
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = [column['name'] for column in inspector.get_columns('users')]
            
            if 'status' not in columns:
                print("Adding status column to existing database...")
                with db.engine.connect() as connection:
                    connection.execute(db.text(
                        "ALTER TABLE users ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'approved'"
                    ))
                    # Update existing users: admin users are approved, others are pending
                    connection.execute(db.text("""
                        UPDATE users 
                        SET status = CASE 
                            WHEN role = 'admin' THEN 'approved' 
                            ELSE 'pending' 
                        END
                        WHERE status = 'approved'
                    """))
                    connection.commit()
                print("Status column added successfully")

def check_password(self, password):
    """Verify the password."""
    try:
        stored_hash = self.password_hash
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode('utf-8')

        password_bytes = password.encode('utf-8')
        result = bcrypt.checkpw(password_bytes, stored_hash)
        return result
    except Exception as e:
        print(f"Error checking password: {str(e)}")
        return False