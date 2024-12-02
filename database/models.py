from datetime import datetime, timedelta
import sqlite3
import os
import bcrypt
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
import secrets
import sys  
import yaml
import json

db = SQLAlchemy()


class ModelPermission(db.Model):
    __tablename__ = 'model_permissions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    model_type = db.Column(db.String(20), nullable=False)  # 'checkpoint' or 'lora'
    model_name = db.Column(db.String(255), nullable=False)
    granted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    granted_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'model_type', 'model_name', name='unique_user_model_permission'),
    )

class UserLatestContent(db.Model):
    __tablename__ = 'user_latest_content'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    prompt = db.Column(db.Text)
    image_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('latest_content', lazy=True))

class DefaultModelPermission(db.Model):
    __tablename__ = 'default_model_permissions'

    id = db.Column(db.Integer, primary_key=True)
    model_type = db.Column(db.String(20), nullable=False)
    model_name = db.Column(db.String(255), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        db.UniqueConstraint('model_type', 'model_name', name='unique_default_model_permission'),
    )


class CharacterPermission(db.Model):
    __tablename__ = 'character_permissions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    character_name = db.Column(db.String(255), nullable=False)
    can_generate = db.Column(db.Boolean, nullable=False, default=True)
    can_browse = db.Column(db.Boolean, nullable=False, default=True)
    granted_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    granted_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'character_name', name='unique_user_character_permission'),
    )


class DefaultCharacterPermission(db.Model):
    __tablename__ = 'default_character_permissions'

    id = db.Column(db.Integer, primary_key=True)
    character_name = db.Column(db.String(255), nullable=False, unique=True)
    can_generate = db.Column(db.Boolean, nullable=False, default=True)
    can_browse = db.Column(db.Boolean, nullable=False, default=True)


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    status = db.Column(db.String(20), nullable=False, default='pending')
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    can_delete_files = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    reset_token = db.Column(db.String(100), unique=True, nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    # Relationships
    model_permissions = db.relationship('ModelPermission',
                                      foreign_keys='ModelPermission.user_id',
                                      backref='user',
                                      lazy=True,
                                      cascade='all, delete-orphan')
    
    character_permissions = db.relationship('CharacterPermission',
                                         foreign_keys='CharacterPermission.user_id',
                                         backref='user',
                                         lazy=True,
                                         cascade='all, delete-orphan')

    def __init__(self, username, email, password, role='user'):
        self.username = username
        self.email = email
        self.set_password(password)
        self.role = role
        self.status = 'approved' if role == 'admin' else 'pending'
        self.is_active = (role == 'admin')
        self.can_delete_files = (role == 'admin')
        self.created_at = datetime.utcnow()

    def set_password(self, password):
        """Hash the password before storing."""
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)

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

    def get_available_models(self):
        """Get all models this user has permission to use."""
        permissions = ModelPermission.query.filter_by(user_id=self.id).all()
        return {
            'checkpoints': [p.model_name for p in permissions if p.model_type == 'checkpoint'],
            'loras': [p.model_name for p in permissions if p.model_type == 'lora']
        }

    def get_character_permissions(self):
        """Get all character permissions for the user."""
        if self.is_admin:
            return {'all': {'can_generate': True, 'can_browse': True}}
        
        permissions = CharacterPermission.query.filter_by(user_id=self.id).all()
        return {
            p.character_name: {
                'can_generate': p.can_generate,
                'can_browse': p.can_browse
            } for p in permissions
        }

    def can_access_character(self, character_name, access_type='both'):
        """
        Check if user can access a specific character.
        access_type can be 'generate', 'browse', or 'both'
        """
        if self.is_admin:
            return True

        permission = CharacterPermission.query.filter_by(
            user_id=self.id,
            character_name=character_name
        ).first()

        if not permission:
            return False

        if access_type == 'generate':
            return permission.can_generate
        elif access_type == 'browse':
            return permission.can_browse
        else:
            return permission.can_generate and permission.can_browse


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


def extract_models_from_workflow(workflow_data):
    """Extract checkpoint and LoRA models from a workflow file."""
    models = {
        'checkpoints': set(),
        'loras': set()
    }

    try:
        for node in workflow_data.values():
            # Check for checkpoint models
            if node.get('inputs', {}).get('ckpt_name'):
                models['checkpoints'].add(node['inputs']['ckpt_name'])

            # Check for LoRA models
            if node.get('class_type') == 'Power Lora Loader (rgthree)':
                for key, value in node.get('inputs', {}).items():
                    if isinstance(value, dict) and value.get('lora'):
                        models['loras'].add(value['lora'])

    except Exception as e:
        print(f"Error extracting models from workflow: {e}", file=sys.stderr)

    return models


def grant_default_model_permissions(user_id, admin_id):
    """Grant permissions for all models used in default character workflows."""
    try:
        # Load characters configuration
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'characters.yaml')
        with open(config_path, 'r') as f:
            characters = yaml.safe_load(f)

        required_models = {
            'checkpoints': set(),
            'loras': set()
        }

        # Extract models from all character workflows
        for character_data in characters.values():
            workflow_file = character_data.get('workflow_file')
            if workflow_file:
                workflow_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), workflow_file)
                if os.path.exists(workflow_path):
                    with open(workflow_path, 'r') as f:
                        workflow_data = json.load(f)
                        models = extract_models_from_workflow(workflow_data)
                        required_models['checkpoints'].update(models['checkpoints'])
                        required_models['loras'].update(models['loras'])

        # Grant permissions for all required models
        for checkpoint in required_models['checkpoints']:
            permission = ModelPermission(
                user_id=user_id,
                model_type='checkpoint',
                model_name=checkpoint,
                granted_by=admin_id
            )
            db.session.add(permission)

        for lora in required_models['loras']:
            permission = ModelPermission(
                user_id=user_id,
                model_type='lora',
                model_name=lora,
                granted_by=admin_id
            )
            db.session.add(permission)

        db.session.commit()
        return True

    except Exception as e:
        print(f"Error granting default model permissions: {e}", file=sys.stderr)
        db.session.rollback()
        return False


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

            # Check if we need to add any new columns or tables
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()

            # Check for new tables
            required_tables = ['model_permissions', 'default_model_permissions', 
                             'character_permissions', 'default_character_permissions']
            for table in required_tables:
                if table not in tables:
                    print(f"Creating new table: {table}")
                    if table == 'model_permissions':
                        ModelPermission.__table__.create(db.engine)
                    elif table == 'default_model_permissions':
                        DefaultModelPermission.__table__.create(db.engine)
                    elif table == 'character_permissions':
                        CharacterPermission.__table__.create(db.engine)
                    elif table == 'default_character_permissions':
                        DefaultCharacterPermission.__table__.create(db.engine)

            db.session.commit()
            print("Database schema updated successfully")