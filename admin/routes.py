from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from datetime import datetime, timedelta
from database.models import (
    User, LoginAttempt, PasswordResetRequest, db, ModelPermission, 
    DefaultModelPermission, CharacterPermission, DefaultCharacterPermission
)
from auth.utils import admin_required
from sqlalchemy import func
import os
from config.config_utils import config
import json
import glob
import yaml
import sys

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def calculate_storage_usage():
    """Calculate total storage used by generated images."""
    total_size = 0
    image_dirs = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'images'),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'images')
    ]

    for directory in image_dirs:
        if os.path.exists(directory):
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        file_path = os.path.join(root, file)
                        total_size += os.path.getsize(file_path)

    # Convert to appropriate unit
    if total_size > 1024 * 1024 * 1024:  # GB
        return f"{total_size / (1024 * 1024 * 1024):.2f} GB"
    elif total_size > 1024 * 1024:  # MB
        return f"{total_size / (1024 * 1024):.2f} MB"
    elif total_size > 1024:  # KB
        return f"{total_size / 1024:.2f} KB"
    else:
        return f"{total_size} B"


def get_total_images():
    """Count total generated images."""
    total_images = 0
    image_dirs = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'images'),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), 'images')
    ]

    for directory in image_dirs:
        if os.path.exists(directory):
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        total_images += 1

    return total_images


@admin_bp.route('/')
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard showing system statistics and recent activity."""
    # Get user statistics
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()

    # Get recent login count (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_logins = LoginAttempt.query.filter(
        LoginAttempt.timestamp >= yesterday,
        LoginAttempt.success == True
    ).count()

    # Get recent activity (last 50 events)
    recent_activity = LoginAttempt.query \
        .order_by(LoginAttempt.timestamp.desc()) \
        .limit(50) \
        .all()

    activity_list = [{
        'username': activity.username,
        'action': 'Successful login' if activity.success else 'Failed login attempt',
        'ip_address': activity.ip_address,
        'timestamp': activity.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    } for activity in recent_activity]

    return render_template('admin/dashboard.html',
                        total_users=total_users,
                        active_users=active_users,
                        recent_logins=recent_logins,
                        recent_activity=activity_list)


@admin_bp.route('/users')
@admin_required
def users():
    """User management page."""
    pending_users = User.query.filter_by(status='pending').all()
    approved_users = User.query.filter_by(status='approved').all()
    rejected_users = User.query.filter_by(status='rejected').all()
    return render_template('admin/users.html',
                         pending_users=pending_users,
                         approved_users=approved_users,
                         rejected_users=rejected_users)


@admin_bp.route('/user/<int:user_id>/approve', methods=['POST'])
@admin_required
def approve_user(user_id):
    """Approve a pending user."""
    user = User.query.get_or_404(user_id)
    if user.status == 'pending':
        try:
            # Start transaction
            db.session.begin_nested()

            user.status = 'approved'
            user.is_active = True

            # Grant all model permissions by default
            comfyui_dir = config.get('paths', 'comfyui_dir')

            # Grant checkpoint permissions
            checkpoint_path = os.path.join(comfyui_dir, 'checkpoints')
            if os.path.exists(checkpoint_path):
                for checkpoint in glob.glob(os.path.join(checkpoint_path, '*.safetensors')):
                    permission = ModelPermission(
                        user_id=user_id,
                        model_type='checkpoint',
                        model_name=os.path.basename(checkpoint),
                        granted_by=session['user_id']
                    )
                    db.session.add(permission)

            # Grant LoRA permissions
            loras_path = os.path.join(comfyui_dir, 'loras')
            if os.path.exists(loras_path):
                for lora in glob.glob(os.path.join(loras_path, '**/*.safetensors'), recursive=True):
                    permission = ModelPermission(
                        user_id=user_id,
                        model_type='lora',
                        model_name=os.path.relpath(lora, loras_path),
                        granted_by=session['user_id']
                    )
                    db.session.add(permission)

            # Grant character permissions
            try:
                # Load characters configuration
                config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'characters.yaml')
                with open(config_path, 'r') as f:
                    characters = yaml.safe_load(f)

                # Get default permissions
                default_permissions = DefaultCharacterPermission.query.all()
                disabled_permissions = {
                    p.character_name: {'can_generate': p.can_generate, 'can_browse': p.can_browse}
                    for p in default_permissions
                }

                # Grant permissions for all characters
                for char_name in characters.keys():
                    # Use default permissions if they exist, otherwise grant full access
                    permissions = disabled_permissions.get(char_name, {'can_generate': True, 'can_browse': True})
                    permission = CharacterPermission(
                        user_id=user_id,
                        character_name=char_name,
                        can_generate=permissions['can_generate'],
                        can_browse=permissions['can_browse'],
                        granted_by=session['user_id']
                    )
                    db.session.add(permission)

            except Exception as e:
                print(f"Error granting character permissions: {e}", file=sys.stderr)
                raise

            db.session.commit()
            return jsonify({'message': f'User {user.username} has been approved'})

        except Exception as e:
            db.session.rollback()
            error_msg = f"Error approving user: {str(e)}"
            print(error_msg, file=sys.stderr)
            return jsonify({'error': error_msg}), 500

    return jsonify({'error': 'Invalid user status'}), 400


@admin_bp.route('/user/<int:user_id>/reject', methods=['POST'])
@admin_required
def reject_user(user_id):
    """Reject a pending user."""
    user = User.query.get_or_404(user_id)
    if user.status == 'pending':
        user.status = 'rejected'
        user.is_active = False
        db.session.commit()
        # You could send an email notification here
        return jsonify({'message': f'User {user.username} has been rejected'})
    return jsonify({'error': 'Invalid user status'}), 400


@admin_bp.route('/user/<int:user_id>', methods=['POST', 'DELETE'])
@admin_required
def manage_user(user_id):
    """Handle user management operations (update and delete)."""
    current_user_id = session.get('user_id')

    if request.method == 'DELETE':
        if user_id == current_user_id:
            return jsonify({'error': 'Cannot delete your own account'}), 403

        user = User.query.get_or_404(user_id)
        try:
            db.session.delete(user)
            db.session.commit()
            return jsonify({'message': f'User {user.username} deleted successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    elif request.method == 'POST':
        user = User.query.get_or_404(user_id)
        action = request.form.get('action')

        if action == 'toggle_active':
            user.is_active = not user.is_active
            message = f"User {user.username} {'activated' if user.is_active else 'deactivated'}"
        elif action == 'toggle_admin':
            if user_id != current_user_id:  # Prevent self-demotion
                user.role = 'admin' if user.role == 'user' else 'user'
                message = f"User {user.username} role changed to {user.role}"
            else:
                return jsonify({'error': 'Cannot modify your own admin status'}), 403
        elif action == 'toggle_delete_permission':
            if user_id != current_user_id:  # Prevent self-modification
                user.can_delete_files = not user.can_delete_files
                message = f"File deletion permission {'granted to' if user.can_delete_files else 'revoked from'} {user.username}"
                print(f"Toggled delete permission for user {user.username}. New value: {user.can_delete_files}")  # Debug line
            else:
                return jsonify({'error': 'Cannot modify your own permissions'}), 403
        else:
            return jsonify({'error': 'Invalid action'}), 400

        try:
            db.session.commit()
            return jsonify({'message': message, 'status': 'success'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    return jsonify({'error': 'Invalid method'}), 405


@admin_bp.route('/api/user/<int:user_id>/characters', methods=['GET'])
@admin_required
def get_user_characters(user_id):
    """Get all characters and their permission status for a user."""
    try:
        print(f"Loading characters for user {user_id}")
        user = User.query.get_or_404(user_id)

        # Load all available characters from config
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'characters.yaml')
        print(f"Loading characters from: {config_path}")
        
        try:
            with open(config_path, 'r') as f:
                characters = yaml.safe_load(f)
            print(f"Found characters: {list(characters.keys())}")
        except Exception as e:
            print(f"Error loading characters config: {e}")
            return jsonify({'error': 'Failed to load characters'}), 500

        # Get user's character permissions
        user_permissions = CharacterPermission.query.filter_by(user_id=user_id).all()
        permissions_dict = {
            p.character_name: {'can_generate': p.can_generate, 'can_browse': p.can_browse}
            for p in user_permissions
        }
        print(f"User permissions: {permissions_dict}")

        # Create response with all characters and their permissions
        character_list = []
        for char_name in characters.keys():
            permissions = permissions_dict.get(char_name, {'can_generate': False, 'can_browse': False})
            character_list.append({
                'name': char_name,
                'can_generate': permissions['can_generate'],
                'can_browse': permissions['can_browse']
            })

        print(f"Sending response: {character_list}")
        return jsonify(character_list)

    except Exception as e:
        print(f"Error in get_user_characters: {str(e)}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/user/<int:user_id>/characters', methods=['POST'])
@admin_required
def update_user_characters(user_id):
    """Update character permissions for a user."""
    user = User.query.get_or_404(user_id)
    data = request.json

    try:
        # Start transaction
        db.session.begin_nested()

        # Remove all existing character permissions
        CharacterPermission.query.filter_by(user_id=user_id).delete()

        # Add new permissions
        admin_id = session['user_id']
        
        for character in data:
            if character['can_generate'] or character['can_browse']:
                permission = CharacterPermission(
                    user_id=user_id,
                    character_name=character['name'],
                    can_generate=character['can_generate'],
                    can_browse=character['can_browse'],
                    granted_by=admin_id
                )
                db.session.add(permission)

        db.session.commit()
        return jsonify({'message': 'Character permissions updated successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/stats')
@admin_required
def get_stats():
    """Get detailed system statistics."""
    # User statistics
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    admin_users = User.query.filter_by(role='admin').count()

    # Login statistics (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    login_attempts = LoginAttempt.query.filter(LoginAttempt.timestamp >= yesterday).count()
    successful_logins = LoginAttempt.query.filter(
        LoginAttempt.timestamp >= yesterday,
        LoginAttempt.success == True
    ).count()

    # Get hourly login attempts for the last 24 hours
    # Using strftime for SQLite compatibility
    hourly_stats = db.session.query(
        db.func.strftime('%Y-%m-%d %H:00:00', LoginAttempt.timestamp).label('hour'),
        db.func.count(LoginAttempt.id).label('count')
    ).filter(
        LoginAttempt.timestamp >= yesterday
    ).group_by(
        db.func.strftime('%Y-%m-%d %H:00:00', LoginAttempt.timestamp)
    ).order_by(
        db.func.strftime('%Y-%m-%d %H:00:00', LoginAttempt.timestamp)
    ).all()

    hourly_data = [{
        'hour': stat.hour,
        'count': stat.count
    } for stat in hourly_stats]

    # Get storage statistics
    storage_used = calculate_storage_usage()
    total_images = get_total_images()

    return jsonify({
        'user_stats': {
            'total': total_users,
            'active': active_users,
            'admin': admin_users,
            'inactive': total_users - active_users
        },
        'login_stats': {
            'total_attempts': login_attempts,
            'successful': successful_logins,
            'failed': login_attempts - successful_logins
        },
        'storage_stats': {
            'used': storage_used,
            'total_images': total_images
        },
        'hourly_activity': hourly_data
    })


@admin_bp.route('/settings')
@admin_required
def settings():
    """System settings page."""
    return render_template('admin/settings.html')


@admin_bp.route('/settings/security', methods=['GET', 'POST'])
@admin_required
def security_settings():
    """Handle security settings updates."""
    if request.method == 'POST':
        try:
            data = request.get_json()

            # Validate settings
            max_attempts = int(data.get('maxLoginAttempts', 5))
            session_timeout = int(data.get('sessionTimeout', 60))
            min_password_length = int(data.get('passwordMinLength', 8))

            if not (1 <= max_attempts <= 10):
                return jsonify({'error': 'Max login attempts must be between 1 and 10'}), 400
            if not (5 <= session_timeout <= 1440):
                return jsonify({'error': 'Session timeout must be between 5 and 1440 minutes'}), 400
            if not (8 <= min_password_length <= 32):
                return jsonify({'error': 'Password minimum length must be between 8 and 32'}), 400

            # Update configuration
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'config',
                'app_config.yaml'
            )

            try:
                with open(config_path, 'r') as f:
                    settings = yaml.safe_load(f)

                if 'security' not in settings:
                    settings['security'] = {}

                settings['security']['max_login_attempts'] = max_attempts
                settings['security']['session_lifetime'] = session_timeout * 60  # Convert to seconds
                settings['security']['password_min_length'] = min_password_length

                with open(config_path, 'w') as f:
                    yaml.safe_dump(settings, f, default_flow_style=False)

                return jsonify({'message': 'Security settings updated successfully'})
            except Exception as e:
                return jsonify({'error': f'Error updating config file: {str(e)}'}), 500

        except ValueError as e:
            return jsonify({'error': f'Invalid value provided: {str(e)}'}), 400
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # GET request - return current settings
    return jsonify({
        'maxLoginAttempts': config.get('security', 'max_login_attempts', default=5),
        'sessionTimeout': config.get('security', 'session_lifetime', default=3600) // 60,  # Convert to minutes
        'passwordMinLength': config.get('security', 'password_min_length', default=8)
    })


@admin_bp.route('/password-resets')
@admin_required
def password_resets():
    """View pending password reset requests."""
    pending_requests = PasswordResetRequest.query.filter_by(status='pending')\
        .order_by(PasswordResetRequest.created_at.desc()).all()
    recent_requests = PasswordResetRequest.query.filter(
        PasswordResetRequest.status != 'pending'
    ).order_by(PasswordResetRequest.created_at.desc()).limit(50).all()
    
    return render_template('admin/password_resets.html',
                         pending_requests=pending_requests,
                         recent_requests=recent_requests)

@admin_bp.route('/password-reset/<int:request_id>/approve', methods=['POST'])
@admin_required
def approve_reset(request_id):
    """Approve a password reset request."""
    reset_request = PasswordResetRequest.query.get_or_404(request_id)
    if reset_request.status == 'pending':
        reset_request.status = 'approved'
        reset_request.approved_at = datetime.utcnow()
        db.session.commit()
        # In a real application, you would send an email to the user here
        flash(f'Password reset approved for user {reset_request.user.username}')
    return redirect(url_for('admin.password_resets'))

@admin_bp.route('/password-reset/<int:request_id>/reject', methods=['POST'])
@admin_required
def reject_reset(request_id):
    """Reject a password reset request."""
    reset_request = PasswordResetRequest.query.get_or_404(request_id)
    if reset_request.status == 'pending':
        reset_request.status = 'rejected'
        db.session.commit()
        # In a real application, you would send an email to the user here
        flash(f'Password reset rejected for user {reset_request.user.username}')
    return redirect(url_for('admin.password_resets'))


@admin_bp.route('/api/user/<int:user_id>/models', methods=['GET'])
@admin_required
def get_user_models(user_id):
    """Get all models and their permission status for a user."""
    try:
        print(f"Loading models for user {user_id}")
        user = User.query.get_or_404(user_id)

        # Get all available models from the filesystem
        comfyui_dir = config.get('paths', 'comfyui_dir')
        print(f"ComfyUI directory: {comfyui_dir}")
        
        checkpoints = []
        loras = []

        # Get checkpoints
        checkpoint_path = os.path.join(comfyui_dir, 'checkpoints')
        if os.path.exists(checkpoint_path):
            checkpoints = [os.path.basename(f) for f in glob.glob(os.path.join(checkpoint_path, '*.safetensors'))]
        print(f"Found checkpoints: {checkpoints}")

        # Get LoRAs
        loras_path = os.path.join(comfyui_dir, 'loras')
        if os.path.exists(loras_path):
            loras = [os.path.relpath(f, loras_path) for f in
                     glob.glob(os.path.join(loras_path, '**/*.safetensors'), recursive=True)]
        print(f"Found LoRAs: {loras}")

        # Get user's permissions
        user_permissions = user.get_available_models()
        print(f"User permissions: {user_permissions}")

        response_data = {
            'checkpoints': [{'name': cp, 'enabled': cp in user_permissions['checkpoints']} for cp in checkpoints],
            'loras': [{'name': lora, 'enabled': lora in user_permissions['loras']} for lora in loras]
        }
        print(f"Sending response: {response_data}")
        return jsonify(response_data)

    except Exception as e:
        print(f"Error in get_user_models: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/user/<int:user_id>/models', methods=['POST'])
@admin_required
def update_user_models(user_id):
    """Update model permissions for a user."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Start transaction
        db.session.begin_nested()

        # Remove existing permissions
        ModelPermission.query.filter_by(user_id=user_id).delete()

        # Add new permissions
        for model_type in ['checkpoints', 'loras']:
            for model in data.get(model_type, []):
                if model['enabled']:
                    permission = ModelPermission(
                        user_id=user_id,
                        model_type=model_type[:-1],  # Remove 's' to get singular form
                        model_name=model['name'],
                        granted_by=session['user_id']
                    )
                    db.session.add(permission)

        db.session.commit()
        return jsonify({'message': 'Model permissions updated successfully'})

    except Exception as e:
        db.session.rollback()
        print(f"Error updating model permissions: {str(e)}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/default-models', methods=['GET'])
@admin_required
def get_default_models():
    """Get default model permissions for new users."""
    default_permissions = DefaultModelPermission.query.all()
    return jsonify({
        'checkpoints': [{'name': p.model_name, 'enabled': p.enabled}
                        for p in default_permissions if p.model_type == 'checkpoint'],
        'loras': [{'name': p.model_name, 'enabled': p.enabled}
                  for p in default_permissions if p.model_type == 'lora']
    })


@admin_bp.route('/api/default-models', methods=['POST'])
@admin_required
def update_default_models():
    """Update default model permissions for new users."""
    data = request.json

    try:
        # Start transaction
        db.session.begin_nested()

        # Remove all existing default permissions
        DefaultModelPermression.query.delete()

        # Add new default permissions
        for model_type in ['checkpoints', 'loras']:
            for model in data.get(model_type, []):
                permission = DefaultModelPermission(
                    model_type=model_type[:-1],  # Remove 's' to get singular form
                    model_name=model['name'],
                    enabled=model['enabled']
                )
                db.session.add(permission)

        db.session.commit()
        return jsonify({'message': 'Default permissions updated successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/default-characters', methods=['GET'])
@admin_required
def get_default_characters():
    """Get default character permissions for new users."""
    # Load all available characters
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'characters.yaml')
    try:
        with open(config_path, 'r') as f:
            characters = yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading characters config: {e}", file=sys.stderr)
        return jsonify({'error': 'Failed to load characters'}), 500

    # Get default permissions
    default_permissions = DefaultCharacterPermission.query.all()
    permissions_dict = {
        p.character_name: {'can_generate': p.can_generate, 'can_browse': p.can_browse}
        for p in default_permissions
    }

    # Create response with all characters and their default permissions
    character_list = []
    for char_name in characters.keys():
        permissions = permissions_dict.get(char_name, {'can_generate': True, 'can_browse': True})
        character_list.append({
            'name': char_name,
            'can_generate': permissions['can_generate'],
            'can_browse': permissions['can_browse']
        })

    return jsonify(character_list)


@admin_bp.route('/api/default-characters', methods=['POST'])
@admin_required
def update_default_characters():
    """Update default character permissions for new users."""
    data = request.json

    try:
        # Start transaction
        db.session.begin_nested()

        # Remove all existing default permissions
        DefaultCharacterPermission.query.delete()

        # Add new default permissions
        for character in data:
            if not character['can_generate'] or not character['can_browse']:
                # Only store explicitly disabled permissions
                permission = DefaultCharacterPermission(
                    character_name=character['name'],
                    can_generate=character['can_generate'],
                    can_browse=character['can_browse']
                )
                db.session.add(permission)

        db.session.commit()
        return jsonify({'message': 'Default character permissions updated successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def grant_default_character_permissions(user_id, admin_id):
    """Grant default character permissions to a new user."""
    try:
        # Load characters configuration
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'characters.yaml')
        with open(config_path, 'r') as f:
            characters = yaml.safe_load(f)

        # Get default permissions
        default_permissions = DefaultCharacterPermission.query.all()
        disabled_permissions = {
            p.character_name: {'can_generate': p.can_generate, 'can_browse': p.can_browse}
            for p in default_permissions
        }

        # Grant permissions for all characters except those explicitly disabled
        for char_name in characters.keys():
            permissions = disabled_permissions.get(char_name, {'can_generate': True, 'can_browse': True})
            if permissions['can_generate'] or permissions['can_browse']:
                permission = CharacterPermission(
                    user_id=user_id,
                    character_name=char_name,
                    can_generate=permissions['can_generate'],
                    can_browse=permissions['can_browse'],
                    granted_by=admin_id
                )
                db.session.add(permission)

        db.session.commit()
        return True

    except Exception as e:
        print(f"Error granting default character permissions: {e}", file=sys.stderr)
        db.session.rollback()
        return False    