# app.py
import subprocess
import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from main import load_characters
import glob
import json
from PIL import Image
import sys
from datetime import timedelta, datetime
from database.models import db, User, init_db, ModelPermission, UserLatestContent
from auth.routes import auth_bp
from auth.utils import login_required, admin_required


project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

from config.config_utils import config
from database.models import db, init_db
from auth.routes import auth_bp
from admin.routes import admin_bp
from auth.utils import login_required, admin_required

# Use configuration for paths
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'characters.yaml')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COMFYUI_DIR = config.get('paths', 'comfyui_dir')
GENERATED_IMAGE_FOLDER = os.path.join(BASE_DIR, 'static', 'images')
LATEST_IMAGE_NAME = 'latest_image.png'
LATEST_PROMPT_FILE = os.path.join(BASE_DIR, 'static', 'latest_prompt.txt')
PREVIOUS_SEED_FILE = os.path.join(BASE_DIR, 'static', 'previous_seed.txt')

IMAGES_FOLDER = os.path.join(BASE_DIR, 'images')  # Main images directory
STATIC_IMAGES_FOLDER = os.path.join(BASE_DIR, 'static', 'images')  # For latest generated image

os.makedirs(GENERATED_IMAGE_FOLDER, exist_ok=True)
os.makedirs(IMAGES_FOLDER, exist_ok=True)
os.makedirs(STATIC_IMAGES_FOLDER, exist_ok=True)

def create_app():

    app = Flask(__name__)

    # Ensure database directory exists
    db_dir = os.path.join(project_root, 'database')
    os.makedirs(db_dir, exist_ok=True)

    # Set the absolute path for the SQLite database
    db_path = os.path.join(db_dir, 'app.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = config.get('database', 'track_modifications', default=False)

    # Security and Session configuration
    app.secret_key = os.urandom(24)  # Generate a random secret key
    app.config.update(
        SESSION_COOKIE_SECURE=False,  # Set to True in production with HTTPS
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
        SESSION_COOKIE_NAME='charactergen_session'
    )

    # Initialize extensions
    db.init_app(app)

    with app.app_context():
        # Initialize database
        init_db(app)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    
    return app

app = create_app()

def get_user_content_paths(user_id):
    """Get paths for user-specific content storage."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create user-specific prompt directory
    prompt_dir = os.path.join(base_dir, 'static', 'prompts', str(user_id))
    os.makedirs(prompt_dir, exist_ok=True)
    
    # Create user-specific image directory
    image_dir = os.path.join(base_dir, 'static', 'images', str(user_id))
    os.makedirs(image_dir, exist_ok=True)
    
    return {
        'prompt_file': os.path.join(prompt_dir, 'latest_prompt.txt'),
        'image_file': os.path.join(image_dir, 'latest_image.png'),
        'prompt_dir': prompt_dir,
        'image_dir': image_dir
    }

def save_prompt(prompt, user_id=None):
    """Save prompt to user-specific file with detailed logging."""
    print(f"\nAttempting to save prompt: '{prompt}'")
    print(f"User ID: {user_id}")

    if not prompt:
        print("Error: Attempting to save empty prompt")
        return False

    try:
        if user_id is None:
            user_id = session.get('user_id')
            if not user_id:
                print("Error: No user ID available")
                return False

        print(f"Using user_id: {user_id}")

        # Get paths for this user
        paths = get_user_content_paths(user_id)
        print(f"Prompt will be saved to: {paths['prompt_file']}")
        
        # Save to file
        try:
            with open(paths['prompt_file'], 'w') as f:
                f.write(prompt)
            print(f"Successfully saved prompt to file: {paths['prompt_file']}")
        except Exception as file_error:
            print(f"Error saving prompt to file: {file_error}")
            raise

        # Update database
        try:
            content_entry = UserLatestContent.query.filter_by(user_id=user_id).first()
            if not content_entry:
                print("Creating new UserLatestContent entry")
                content_entry = UserLatestContent(user_id=user_id)
                db.session.add(content_entry)
            
            content_entry.prompt = prompt
            content_entry.created_at = datetime.utcnow()
            db.session.commit()
            print("Successfully updated database")
        except Exception as db_error:
            print(f"Error updating database: {db_error}")
            db.session.rollback()
            raise

        session['prompt'] = prompt
        print("Successfully saved prompt to session")
        return True

    except Exception as e:
        print(f"Error in save_prompt: {str(e)}")
        print("Full traceback:")
        import traceback
        traceback.print_exc()
        return False

def get_latest_prompt(user_id=None):
    """Read the latest prompt from the user-specific file."""
    try:
        if user_id is None:
            user_id = session.get('user_id')
            if not user_id:
                print("Error: No user ID available")
                return None

        paths = get_user_content_paths(user_id)
        prompt_file = paths['prompt_file']

        if not os.path.exists(prompt_file):
            print(f"Latest prompt file not found at: {prompt_file}")
            return None

        with open(prompt_file, 'r') as f:
            prompt = f.read().strip()
            if not prompt:
                print("Latest prompt file is empty")
                return None
            print(f"Successfully retrieved latest prompt for user {user_id}")
            return prompt

    except Exception as e:
        print(f"Error reading latest prompt file: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_image_url(user_id=None):
    """Get the URL for the user's latest generated image."""
    if user_id is None:
        user_id = session.get('user_id')
        if not user_id:
            return None

    # Check if user's latest image exists
    paths = get_user_content_paths(user_id)
    relative_path = os.path.relpath(paths['image_file'], os.path.join(BASE_DIR, 'static'))
    
    if os.path.exists(paths['image_file']):
        return url_for('static', filename=relative_path)
    return None

def save_user_content(user_id, prompt=None, image_data=None):
    """Save user-specific content and update database."""
    paths = get_user_content_paths(user_id)
    
    try:
        # Start database transaction
        db.session.begin_nested()
        
        content_entry = UserLatestContent.query.filter_by(user_id=user_id).first()
        if not content_entry:
            content_entry = UserLatestContent(user_id=user_id)
            db.session.add(content_entry)
        
        # Save prompt if provided
        if prompt:
            with open(paths['prompt_file'], 'w') as f:
                f.write(prompt)
            content_entry.prompt = prompt
        
        # Save image if provided
        if image_data:
            with open(paths['image_file'], 'wb') as f:
                f.write(image_data)
            content_entry.image_path = f"images/{user_id}/latest_image.png"
        
        content_entry.created_at = datetime.utcnow()
        db.session.commit()
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error saving user content: {e}", file=sys.stderr)
        return False

def get_user_latest_content(user_id):
    """Retrieve user's latest content."""
    try:
        content = UserLatestContent.query.filter_by(user_id=user_id).first()
        if not content:
            return None, None
            
        paths = get_user_content_paths(user_id)
        
        # Get prompt if exists
        prompt = None
        if os.path.exists(paths['prompt_file']):
            with open(paths['prompt_file'], 'r') as f:
                prompt = f.read().strip()
        
        # Get image path if exists
        image_url = None
        if content.image_path:
            image_url = url_for('static', filename=content.image_path)
            
        return prompt, image_url
        
    except Exception as e:
        print(f"Error getting user content: {e}", file=sys.stderr)
        return None, None


def sanitize_character_name(character_name):
    """Convert a character display name to its folder name format."""
    return character_name.replace(' ', '_')

def desanitize_character_name(folder_name):
    """Convert a folder name back to character display name format."""
    return folder_name.replace('_', ' ')

@app.route('/')
@login_required
def index():
    """Main page route with character permission filtering."""
    characters = load_characters(CONFIG_PATH)
    user = User.query.get(session['user_id'])
    
    if not user.is_admin:
        # Filter characters based on generate permission
        permissions = user.get_character_permissions()
        characters = {
            name: data for name, data in characters.items() 
            if name in permissions and permissions[name]['can_generate']
        }
    
    character_names = list(characters.keys())

    if not character_names:
        flash('No characters available. Please contact an administrator.', 'error')
        return redirect(url_for('auth.logout'))

    if 'selected_character' not in session or session['selected_character'] not in character_names:
        session['selected_character'] = character_names[0]
    selected_character = session.get('selected_character')

    # Get user-specific prompt and image
    prompt = get_latest_prompt(user.id)
    if prompt:
        session['prompt'] = prompt

    image_url = get_image_url(user.id)

    return render_template('index.html',
                         characters=character_names,
                         selected_character=selected_character,
                         prompt=prompt,
                         image_url=image_url)


@app.route('/images/')
@login_required
def browse_images():
    """Render the image browser page."""
    return render_template('browse.html')


@app.route('/api/files')
@login_required
def list_files():
    """API endpoint to list files and folders."""
    requested_path = request.args.get('path', '/')
    user = User.query.get(session['user_id'])

    # Use IMAGES_FOLDER as the base path
    base_path = IMAGES_FOLDER

    # Ensure the path doesn't go above the base directory
    full_path = os.path.normpath(os.path.join(base_path, requested_path.lstrip('/')))
    if not full_path.startswith(base_path):
        return jsonify({'error': 'Invalid path'}), 403

    try:
        items = []
        # Check if this is a character directory
        rel_path = os.path.relpath(full_path, base_path)
        current_character = rel_path.split(os.sep)[0] if rel_path != '.' else None

        # If we're in a character directory, check permission using desanitized name
        if current_character and not user.is_admin:
            character_display_name = desanitize_character_name(current_character)
            permissions = user.get_character_permissions()
            if character_display_name not in permissions or not permissions[character_display_name]['can_browse']:
                return jsonify({'error': 'Access denied'}), 403

        for item in os.listdir(full_path):
            item_path = os.path.join(full_path, item)
            is_dir = os.path.isdir(item_path)

            # For root directory, only show characters user has browse permission for
            if requested_path == '/' and is_dir and not user.is_admin:
                character_display_name = desanitize_character_name(item)
                permissions = user.get_character_permissions()
                if character_display_name not in permissions or not permissions[character_display_name]['can_browse']:
                    continue

            if is_dir:
                items.append({
                    'name': item,
                    'type': 'folder'
                })
            elif item.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                items.append({
                    'name': item,
                    'type': 'file',
                    'url': url_for('serve_image_file', path=os.path.relpath(item_path, IMAGES_FOLDER))
                })

        return jsonify(sorted(items, key=lambda x: (x['type'] != 'folder', x['name'])))

    except Exception as e:
        print(f"Error in list_files: {str(e)}", file=sys.stderr)
        return jsonify({'error': str(e)}), 500


@app.route('/js/<path:filename>')
@login_required
def serve_js(filename):
    """Serve JavaScript files from the templates/js directory."""
    try:
        # Get the absolute path to the js directory
        js_directory = os.path.join(app.root_path, 'templates', 'js')

        # Ensure the requested file exists
        file_path = os.path.join(js_directory, filename)
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return f"File not found: {filename}", 404

        # Make sure we're not allowing directory traversal
        if not os.path.abspath(file_path).startswith(os.path.abspath(js_directory)):
            return "Access denied", 403

        # Serve the file with the correct MIME type
        response = send_from_directory(
            js_directory,
            filename,
            mimetype='application/javascript',
            as_attachment=False
        )

        # Add CORS headers if needed
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'

        # Add caching headers
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

        return response

    except Exception as e:
        print(f"Error serving JS file: {str(e)}")
        return str(e), 500


@app.route('/images/<path:path>')
@login_required
def serve_image_file(path):
    """Serve images from the main images directory."""
    user = User.query.get(session['user_id'])

    # Check character permission for the requested image
    folder_name = path.split(os.sep)[0]
    character_name = desanitize_character_name(folder_name)

    if not user.is_admin:
        permissions = user.get_character_permissions()
        if character_name not in permissions or not permissions[character_name]['can_browse']:
            return "Access denied", 403

    return send_from_directory(IMAGES_FOLDER, path)


@app.route('/api/user/latest-content')
@login_required
def get_user_content():
    """API endpoint to get user's latest content."""
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401

        # Get paths for this user
        paths = get_user_content_paths(user_id)
        
        # Get prompt if exists
        prompt = None
        if os.path.exists(paths['prompt_file']):
            with open(paths['prompt_file'], 'r') as f:
                prompt = f.read().strip()

        # Get image URL if exists
        image_url = None
        if os.path.exists(paths['image_file']):
            image_url = url_for('static', 
                              filename=f"images/{user_id}/latest_image.png")

        return jsonify({
            'prompt': prompt,
            'image_url': image_url
        })
        
    except Exception as e:
        print(f"Error in get_user_content: {e}", file=sys.stderr)
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete-files', methods=['POST'])
@login_required
def delete_files():
    """API endpoint to delete selected files."""
    # Get the current user
    user = User.query.get(session.get('user_id'))
    if not user.is_admin and not user.can_delete_files:
        return jsonify({'error': 'You do not have permission to delete files'}), 403

    data = request.json
    base_path = IMAGES_FOLDER
    current_path = data.get('path', '/')
    files_to_delete = data.get('files', [])

    # Ensure the path doesn't go above the base directory
    full_path = os.path.normpath(os.path.join(base_path, current_path.lstrip('/')))
    if not full_path.startswith(base_path):
        return jsonify({'error': 'Invalid path'}), 403

    try:
        for filename in files_to_delete:
            file_path = os.path.join(full_path, filename)
            # Additional security check
            if os.path.normpath(file_path).startswith(base_path) and os.path.isfile(file_path):
                os.remove(file_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/available-models')
@login_required
def get_available_models():
    """Get lists of available checkpoint models and LoRAs based on user permissions."""
    try:
        # Get the current user from session
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Not authenticated'}), 401

        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Get all available models from filesystem
        checkpoints_path = os.path.join(COMFYUI_DIR, 'checkpoints')
        checkpoints = []
        if os.path.exists(checkpoints_path):
            checkpoints = [os.path.basename(f) for f in glob.glob(os.path.join(checkpoints_path, '*.safetensors'))]

        loras_path = os.path.join(COMFYUI_DIR, 'loras')
        loras = []
        if os.path.exists(loras_path):
            loras = [os.path.relpath(f, loras_path)
                     for f in glob.glob(os.path.join(loras_path, '**/*.safetensors'), recursive=True)]

        # For regular users, filter based on permissions
        if not user.is_admin:
            permitted_models = user.get_available_models()
            if permitted_models['checkpoints']:
                checkpoints = [model for model in checkpoints if model in permitted_models['checkpoints']]
            if permitted_models['loras']:
                loras = [model for model in loras if model in permitted_models['loras']]

        return jsonify({
            'checkpoints': checkpoints,
            'loras': loras
        })

    except Exception as e:
        print(f"Error in get_available_models: {str(e)}", file=sys.stderr)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow-options', methods=['POST'])
@login_required
def update_workflow_options():
    """Update workflow options while preserving default model when selected."""
    try:
        data = request.json
        if not data:
            raise ValueError("No JSON data received")

        character = data.get('character')
        options = data.get('options')

        if not character or not options:
            raise ValueError("Missing character or options")

        # Load character data and original workflow
        characters = load_characters(CONFIG_PATH)
        if character not in characters:
            raise ValueError(f"Character '{character}' not found")

        workflow_file = characters[character].get('workflow_file')
        if not workflow_file:
            raise ValueError(f"No workflow file specified for character '{character}'")

        workflow_path = os.path.join(BASE_DIR, workflow_file)
        if not os.path.exists(workflow_path):
            raise ValueError(f"Workflow file not found: {workflow_path}")

        # Load original workflow to get default values
        with open(workflow_path, 'r') as f:
            workflow = json.load(f)

        # Handle model selection
        model_node = next((node for node in workflow.values() if 'ckpt_name' in node.get('inputs', {})), None)
        if model_node:
            if options['checkpointModel'] == 'default':
                # Keep the default model from the original workflow
                pass
            else:
                # Verify user has permission for the selected model
                user = User.query.get(session.get('user_id'))
                if not user.is_admin:
                    permitted_models = user.get_available_models()
                    if permitted_models['checkpoints'] and options['checkpointModel'] not in permitted_models['checkpoints']:
                        return jsonify({'error': 'Access denied to selected checkpoint model'}), 403
                # Update to the selected model
                model_node['inputs']['ckpt_name'] = options['checkpointModel']

        # Store original LoRA configuration
        original_loras = {}
        lora_node = next((node for node in workflow.values() if node.get('class_type') == 'Power Lora Loader (rgthree)'), None)
        if lora_node:
            original_loras = {k: v for k, v in lora_node.get('inputs', {}).items() if k.startswith('lora_')}

        # Update basic workflow options
        model_node = next((node for node in workflow.values() if 'ckpt_name' in node.get('inputs', {})), None)
        if model_node:
            model_node['inputs']['ckpt_name'] = options['checkpointModel']

        latent_node = next((node for node in workflow.values() if all(k in node.get('inputs', {}) for k in ['width', 'height'])), None)
        if latent_node:
            latent_node['inputs']['width'] = options['width']
            latent_node['inputs']['height'] = options['height']

        guidance_node = next((node for node in workflow.values() if 'guidance' in node.get('inputs', {})), None)
        if guidance_node:
            guidance_node['inputs']['guidance'] = options['guidance']

        seed_node = next((node for node in workflow.values() if 'seed' in node.get('inputs', {})), None)
        if seed_node:
            seed_value = -1  # Default value
            if options.get('useLastSeed', False):
                try:
                    seed_file_path = os.path.join(BASE_DIR, 'static', 'previous_seed.txt')
                    if os.path.exists(seed_file_path):
                        with open(seed_file_path, 'r') as f:
                            saved_seed = f.read().strip()
                            if saved_seed and saved_seed.isdigit():
                                seed_value = int(saved_seed)
                except Exception as e:
                    print(f"Error reading previous seed: {e}")
            else:
                seed_value = options.get('seed', -1)
            seed_node['inputs']['seed'] = seed_value

        # Handle LoRAs while preserving character-specific ones
        lora_node = next((node for node in workflow.values() if node.get('class_type') == 'Power Lora Loader (rgthree)'), None)
        if lora_node:
            # Store the existing model and clip connections
            model_connection = lora_node['inputs'].get('model')
            clip_connection = lora_node['inputs'].get('clip')

            # Initialize the node with its basic structure
            lora_node['inputs'] = {
                "PowerLoraLoaderHeaderWidget": {"type": "PowerLoraLoaderHeaderWidget"},
                "model": model_connection,
                "clip": clip_connection,
                "➕ Add Lora": ""
            }

            # First, add back the original character-specific LoRAs
            next_lora_index = 1
            for lora_key, lora_value in original_loras.items():
                if isinstance(lora_value, dict) and lora_value.get('lora'):
                    lora_node['inputs'][f'lora_{next_lora_index}'] = lora_value
                    next_lora_index += 1

            # Then add the user-selected LoRAs if they're not already present
            for lora in options.get('loras', []):
                if lora['name'] and not any(v.get('lora') == lora['name'] for v in lora_node['inputs'].values() if isinstance(v, dict)):
                    lora_key = f'lora_{next_lora_index}'
                    lora_node['inputs'][lora_key] = {
                        "on": True,
                        "lora": lora['name'],
                        "strength": lora['strength']
                    }
                    next_lora_index += 1

        # Create temp directory if it doesn't exist
        temp_dir = os.path.join(BASE_DIR, 'temp_workflows')
        os.makedirs(temp_dir, exist_ok=True)

        # Create a temporary workflow file for this generation
        temp_workflow_name = os.path.basename(workflow_file)
        temp_workflow_path = os.path.join(temp_dir, temp_workflow_name)

        # Save the temporary workflow
        with open(temp_workflow_path, 'w') as f:
            json.dump(workflow, f, indent=2)

        # Store the temporary workflow path in the session
        session['temp_workflow_path'] = os.path.join('temp_workflows', temp_workflow_name)

        return jsonify({'success': True})

    except Exception as e:
        error_msg = f"Error updating workflow options: {str(e)}"
        print(error_msg, file=sys.stderr)
        return jsonify({'error': error_msg}), 500


@app.route('/api/get-default-workflow')
@login_required
def get_default_workflow():
    """Get the default workflow for a character."""
    try:
        character = request.args.get('character')
        if not character:
            raise ValueError("No character specified")

        characters = load_characters(CONFIG_PATH)
        if character not in characters:
            raise ValueError(f"Character '{character}' not found")

        workflow_file = characters[character].get('workflow_file')
        if not workflow_file:
            raise ValueError(f"No workflow file specified for character '{character}'")

        workflow_path = os.path.join(BASE_DIR, workflow_file)
        if not os.path.exists(workflow_path):
            raise ValueError(f"Workflow file not found: {workflow_path}")

        with open(workflow_path, 'r') as f:
            workflow = json.load(f)

        # Print workflow information for debugging
        print(f"Loading workflow for character: {character}")
        print(f"Workflow file: {workflow_file}")

        # Print LoRA information
        lora_node = next(
            (node for node in workflow.values() if node.get('class_type') == 'Power Lora Loader (rgthree)'), None)
        if lora_node:
            print("Default LoRAs found in workflow:")
            for key, value in lora_node.get('inputs', {}).items():
                if isinstance(value, dict) and value.get('lora'):
                    print(f"  - {value['lora']} (strength: {value.get('strength', 1.0)})")
        else:
            print("No LoRA node found in workflow")

        # If user is not admin, verify their model permissions
        user = User.query.get(session.get('user_id'))
        if not user.is_admin:
            permitted_models = user.get_available_models()

            # If user has specific permissions, enforce them
            if permitted_models['checkpoints'] or permitted_models['loras']:
                # Find the checkpoint node and verify access
                for node in workflow.values():
                    if node.get('inputs', {}).get('ckpt_name'):
                        if permitted_models['checkpoints'] and node['inputs']['ckpt_name'] not in permitted_models[
                            'checkpoints']:
                            # Set to first permitted model or empty if none available
                            node['inputs']['ckpt_name'] = permitted_models['checkpoints'][0] if permitted_models[
                                'checkpoints'] else ''

        return jsonify(workflow)

    except Exception as e:
        error_msg = f"Error getting default workflow: {str(e)}"
        print(error_msg, file=sys.stderr)
        return jsonify({'error': error_msg}), 500


@app.route('/api/user/permissions')
@login_required
def get_user_permissions():
    """Get the current user's permissions."""
    user = User.query.get(session.get('user_id'))
    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'can_delete_files': user.can_delete_files or user.is_admin
    })

@app.route('/api/last-seed')
@login_required
def get_last_seed():
    """Get the last used seed from the saved file."""
    try:
        if os.path.exists(PREVIOUS_SEED_FILE):
            with open(PREVIOUS_SEED_FILE, 'r') as f:
                seed = int(f.read().strip())
                print(f"Retrieved saved seed: {seed}")
                return jsonify({'seed': seed})
        return jsonify({'seed': -1})
    except Exception as e:
        print(f"Error reading seed from file: {e}", file=sys.stderr)
        return jsonify({'seed': -1})


# Modify the existing generate_images function to save the seed
def generate_images(prompt, character_name=None):
    """Handle image generation with user-specific paths."""
    if not prompt or not character_name:
        return False

    queue_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate", "queue_and_retrieve_images.py")
    if not os.path.exists(queue_script):
        print(f"Queue script not found at: {queue_script}", file=sys.stderr)
        return False

    try:
        # Pass user_id to the script through environment variable
        env = os.environ.copy()
        env['user_id'] = str(session.get('user_id'))

        result = subprocess.run(
            ["python3", queue_script, prompt, character_name],
            capture_output=True,
            text=True,
            check=True,
            env=env  # Pass the environment with user_id
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error generating images: {e.stderr.strip()}", file=sys.stderr)
        return False


@app.route('/generate_new_image', methods=['POST'])
@login_required
def generate_new_image():
    """Handle new image generation with detailed logging."""
    try:
        print("\nStarting generate_new_image")
        user_id = session.get('user_id')
        print(f"User ID from session: {user_id}")
        
        selected_character = request.form.get('character')
        print(f"Selected character: {selected_character}")
        
        if not selected_character:
            return jsonify({"error": "No character selected."}), 400

        user = db.session.get(User, user_id)
        if not user.is_admin:
            permissions = user.get_character_permissions()
            if selected_character not in permissions or not permissions[selected_character]['can_generate']:
                return jsonify({"error": "Access denied for this character."}), 403

        session['selected_character'] = selected_character
        main_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')
        print(f"Using main.py path: {main_py_path}")

        # Set environment with user_id
        env = os.environ.copy()
        env['user_id'] = str(user_id)
        print(f"Set user_id in environment: {env['user_id']}")

        print("Running main.py...")
        result = subprocess.run(
            ["python3", main_py_path, "auto", "--character", selected_character],
            capture_output=True,
            text=True,
            check=True,
            env=env
        )

        print("main.py output:")
        print(result.stdout)
        if result.stderr:
            print("main.py stderr:")
            print(result.stderr)

        # Get the last non-empty line as the prompt
        output_lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
        if output_lines:
            prompt = output_lines[-1]
            print(f"Generated prompt: {prompt}")
            
            if save_prompt(prompt, user_id):
                print("Successfully saved prompt")
                return jsonify({"success": True})
            else:
                print("Failed to save prompt")
                return jsonify({"error": "Failed to save prompt"}), 500
        else:
            print("No prompt in output")
            return jsonify({"error": "No prompt generated"}), 500

    except subprocess.CalledProcessError as e:
        error_msg = f"Error running main.py: {e.stderr.strip()}"
        print(error_msg)
        return jsonify({"error": error_msg}), 400
    except Exception as e:
        error_msg = f"Unexpected error in generate_new_image: {str(e)}"
        print(error_msg)
        print("Full traceback:")
        import traceback
        traceback.print_exc()
        return jsonify({"error": error_msg}), 500


@app.route('/regenerate_image', methods=['POST'])
@login_required
def regenerate_image():
    """Handle image regeneration with permission checks."""
    try:
        selected_character = request.form.get('character')
        user_id = session['user_id']

        if not selected_character:
            return jsonify({"error": "No character selected"}), 400

        # Permission check
        user = User.query.get(user_id)
        if not user.is_admin:
            permissions = user.get_character_permissions()
            if selected_character not in permissions or not permissions[selected_character]['can_generate']:
                return jsonify({"error": "Access denied for this character"}), 403

        session['selected_character'] = selected_character

        # Get user-specific prompt
        prompt = get_latest_prompt(user_id)
        if not prompt:
            return jsonify({"error": "No previously saved prompt to regenerate"}), 400

        # Get workflow options from the session
        temp_workflow_path = session.get('temp_workflow_path')
        if temp_workflow_path:
            print(f"Using temporary workflow: {temp_workflow_path}")

        # Set environment with user_id
        env = os.environ.copy()
        env['user_id'] = str(user_id)

        # Run generation
        main_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')
        result = subprocess.run(
            ["python3", main_py_path, "manual", "--character", selected_character],
            input=prompt,
            text=True,
            capture_output=True,
            check=True,
            env=env
        )

        return jsonify({"success": True})

    except subprocess.CalledProcessError as e:
        error_msg = f"Process error: {e.stderr}"
        print(f"Error in subprocess: {error_msg}")
        return jsonify({"error": error_msg}), 400
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"Error in regenerate_image: {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": error_msg}), 400


@app.route('/manual_generation', methods=['POST'])
@login_required
def manual_generation():
    """Handle manual prompt generation with permission checks."""
    try:
        manual_prompt = request.form.get('manual_prompt')
        selected_character = request.form.get('character')
        user_id = session['user_id']

        if not manual_prompt or not selected_character:
            return jsonify({"error": "Character and manual prompt are required"}), 400

        # Permission check
        user = User.query.get(user_id)
        if not user.is_admin:
            permissions = user.get_character_permissions()
            if selected_character not in permissions or not permissions[selected_character]['can_generate']:
                return jsonify({"error": "Access denied for this character"}), 403

        session['selected_character'] = selected_character

        # Save the prompt
        if not save_prompt(manual_prompt, user_id):
            return jsonify({"error": "Failed to save prompt"}), 500

        # Set environment with user_id
        env = os.environ.copy()
        env['user_id'] = str(user_id)

        # Run generation
        main_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')
        result = subprocess.run(
            ["python3", main_py_path, "manual", "--character", selected_character],
            input=manual_prompt,
            text=True,
            capture_output=True,
            check=True,
            env=env
        )

        return jsonify({"success": True})

    except subprocess.CalledProcessError as e:
        error_msg = f"Process error: {e.stderr}"
        print(f"Error in subprocess: {error_msg}")
        return jsonify({"error": error_msg}), 400
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"Error in manual_generation: {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": error_msg}), 400


@app.route('/enhanced_generation', methods=['POST'])
@login_required
def enhanced_generation():
    """Handle enhanced prompt generation with permission checks."""
    try:
        manual_prompt = request.form.get('manual_prompt')
        selected_character = request.form.get('character')
        user_id = session['user_id']

        if not manual_prompt or not selected_character:
            return jsonify({"error": "Character and manual prompt are required"}), 400

        # Permission check
        user = User.query.get(user_id)
        if not user.is_admin:
            permissions = user.get_character_permissions()
            if selected_character not in permissions or not permissions[selected_character]['can_generate']:
                return jsonify({"error": "Access denied for this character"}), 403

        session['selected_character'] = selected_character

        # Update workflow options before generating
        try:
            advanced_options = request.form.get('advancedOptions')
            if advanced_options:
                advanced_options = json.loads(advanced_options)
                update_workflow_options_sync(selected_character, advanced_options)
        except Exception as e:
            print(f"Error updating workflow options: {e}", file=sys.stderr)
            return jsonify({"error": f"Error updating workflow options: {str(e)}"}), 400

        # Set environment with user_id
        env = os.environ.copy()
        env['user_id'] = str(user_id)

        # Run generation
        main_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')
        result = subprocess.run(
            ["python3", main_py_path, "enhanced", "--character", selected_character],
            input=manual_prompt,
            text=True,
            capture_output=True,
            check=True,
            env=env
        )

        # Extract prompt from the output (last non-empty line)
        output_lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
        if output_lines:
            prompt = output_lines[-1]
            if not save_prompt(prompt, user_id):
                return jsonify({"error": "Failed to save prompt"}), 500

        return jsonify({"success": True})

    except subprocess.CalledProcessError as e:
        error_msg = f"Process error: {e.stderr}"
        print(f"Error in subprocess: {error_msg}")
        return jsonify({"error": error_msg}), 400
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"Error in enhanced_generation: {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": error_msg}), 400


if __name__ == '__main__':
    app.run(
        host=config.get('server', 'host', default='0.0.0.0'),
        port=config.get('server', 'port', default=4567),
        debug=config.get('server', 'debug', default=True)
    )
