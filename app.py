# app.py
import subprocess
import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from main import load_characters
import glob
import json
from PIL import Image
import sys
from datetime import timedelta

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


def get_latest_prompt():
    """Read the latest prompt from the file with enhanced error handling and logging."""
    try:
        if not os.path.exists(LATEST_PROMPT_FILE):
            print(f"Latest prompt file not found at: {LATEST_PROMPT_FILE}")
            return None

        with open(LATEST_PROMPT_FILE, 'r') as prompt_file:
            prompt = prompt_file.read().strip()
            if not prompt:
                print("Latest prompt file is empty")
                return None
            print(f"Successfully retrieved latest prompt: {prompt[:50]}...")
            return prompt

    except Exception as e:
        print(f"Error reading latest prompt file: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_prompt(prompt):
    """Save prompt to file and session with enhanced error handling and logging."""
    if not prompt:
        print("Error: Attempting to save empty prompt")
        return False

    try:
        os.makedirs(os.path.dirname(LATEST_PROMPT_FILE), exist_ok=True)
        with open(LATEST_PROMPT_FILE, 'w') as prompt_file:
            prompt_file.write(prompt)
            print(f"Successfully saved prompt to file: {prompt[:50]}...")

        session['prompt'] = prompt
        return True

    except Exception as e:
        print(f"Error saving prompt: {e}")
        import traceback
        traceback.print_exc()
        return False

@app.route('/test-session')
def test_session():
    return jsonify({
        'session': dict(session),
        'user_id_in_session': 'user_id' in session,
        'is_admin_in_session': 'is_admin' in session,
        'all_cookies': dict(request.cookies)
    })


@app.route('/')
@login_required
def index():
    characters = load_characters(CONFIG_PATH)
    character_names = list(characters.keys())

    if 'selected_character' not in session and character_names:
        session['selected_character'] = character_names[0]
    selected_character = session.get('selected_character')

    prompt = get_latest_prompt()
    if prompt:
        session['prompt'] = prompt

    image_url = None
    image_path = os.path.join(GENERATED_IMAGE_FOLDER, LATEST_IMAGE_NAME)
    if os.path.exists(image_path):
        image_url = url_for('static', filename=f'images/{LATEST_IMAGE_NAME}')

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

    # Use IMAGES_FOLDER as the base path instead of static/images
    base_path = IMAGES_FOLDER

    # Ensure the path doesn't go above the base directory
    full_path = os.path.normpath(os.path.join(base_path, requested_path.lstrip('/')))
    if not full_path.startswith(base_path):
        return jsonify({'error': 'Invalid path'}), 403

    try:
        items = []
        for item in os.listdir(full_path):
            item_path = os.path.join(full_path, item)
            is_dir = os.path.isdir(item_path)

            if is_dir:
                items.append({
                    'name': item,
                    'type': 'folder'
                })
            elif item.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                # Create a URL using a new route specifically for serving images from the images directory
                items.append({
                    'name': item,
                    'type': 'file',
                    'url': url_for('serve_image_file', path=os.path.relpath(item_path, IMAGES_FOLDER))
                })

        return jsonify(sorted(items, key=lambda x: (x['type'] != 'folder', x['name'])))

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/js/<path:filename>')
@login_required
def serve_js(filename):
    return send_from_directory(os.path.join(app.root_path, 'templates', 'js'),
                             filename,
                             mimetype='application/javascript')

@app.route('/images/<path:path>')
@login_required
def serve_image_file(path):
    """Serve images from the main images directory."""
    return send_from_directory(IMAGES_FOLDER, path)

@app.route('/api/delete-files', methods=['POST'])
@login_required
def delete_files():
    """API endpoint to delete selected files."""
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
    """Get lists of available checkpoint models and LoRAs."""
    try:
        # Get checkpoint models
        checkpoint_models = []
        checkpoints_path = os.path.join(COMFYUI_DIR, 'checkpoints')
        print(f"Scanning for checkpoints in: {checkpoints_path}")
        for file in glob.glob(os.path.join(checkpoints_path, '*.safetensors')):
            checkpoint_models.append(os.path.basename(file))

        # Get LoRAs
        loras = []
        loras_path = os.path.join(COMFYUI_DIR, 'loras')
        print(f"Scanning for LoRAs in: {loras_path}")
        for file in glob.glob(os.path.join(loras_path, '**/*.safetensors'), recursive=True):
            rel_path = os.path.relpath(file, loras_path)
            loras.append(rel_path)

        print(f"Found {len(checkpoint_models)} checkpoints and {len(loras)} LoRAs")
        return jsonify({
            'checkpoints': sorted(checkpoint_models),
            'loras': sorted(loras)
        })
    except Exception as e:
        print(f"Error in get_available_models: {str(e)}", file=sys.stderr)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow-options', methods=['POST'])
@login_required
def update_workflow_options():
    """Update workflow options while preserving character-specific settings."""
    try:
        data = request.json
        if not data:
            raise ValueError("No JSON data received")

        print(f"Received workflow options update: {data}")

        character = data.get('character')
        options = data.get('options')

        if not character or not options:
            raise ValueError("Missing character or options")

        # Load character data
        characters = load_characters(CONFIG_PATH)
        if character not in characters:
            raise ValueError(f"Character '{character}' not found")

        # Get workflow file path
        workflow_file = characters[character].get('workflow_file')
        if not workflow_file:
            raise ValueError(f"No workflow file specified for character '{character}'")

        workflow_path = os.path.join(BASE_DIR, workflow_file)
        if not os.path.exists(workflow_path):
            raise ValueError(f"Workflow file not found: {workflow_path}")

        # Load existing workflow
        with open(workflow_path, 'r') as f:
            base_workflow = json.load(f)

        # Create a working copy of the workflow
        workflow = json.loads(json.dumps(base_workflow))

        # Update basic workflow options
        workflow['4']['inputs']['ckpt_name'] = options['checkpointModel']
        workflow['5']['inputs']['width'] = options['width']
        workflow['5']['inputs']['height'] = options['height']
        workflow['16']['inputs']['guidance'] = options['guidance']

        # Handle seed
        if '25' in workflow:
            seed_value = -1  # Default value

            if options.get('useLastSeed', False):
                try:
                    # Read seed from file if Use Last Seed is enabled
                    seed_file_path = os.path.join(BASE_DIR, 'static', 'previous_seed.txt')
                    if os.path.exists(seed_file_path):
                        with open(seed_file_path, 'r') as f:
                            saved_seed = f.read().strip()
                            if saved_seed and saved_seed.isdigit():
                                seed_value = int(saved_seed)
                                print(f"Using previous seed: {seed_value}")
                            else:
                                print(f"Invalid seed value in file: {saved_seed}")
                    else:
                        print("No previous seed file found")
                except Exception as e:
                    print(f"Error reading previous seed: {e}")
            else:
                # Use specified seed or -1 for random
                seed_value = options.get('seed', -1)

            # Update the seed in the workflow
            workflow['25']['inputs']['seed'] = seed_value
            print(f"Setting seed to: {seed_value}")

        # Handle LoRAs in node 21 (Power Lora Loader)
        if '21' in workflow:
            node_21 = workflow['21']

            # Store the existing model and clip connections
            model_connection = node_21['inputs'].get('model')
            clip_connection = node_21['inputs'].get('clip')

            # Initialize the node with its basic structure
            node_21['inputs'] = {
                "PowerLoraLoaderHeaderWidget": {"type": "PowerLoraLoaderHeaderWidget"},
                "model": model_connection,
                "clip": clip_connection,
                "➕ Add Lora": ""
            }

            # First, add any default LoRAs from the base workflow
            base_loras = {k: v for k, v in base_workflow['21']['inputs'].items()
                          if k.startswith('lora_') and isinstance(v, dict)}

            print(f"Base LoRAs found: {json.dumps(base_loras, indent=2)}")

            # Add the base LoRAs first
            for key, value in base_loras.items():
                node_21['inputs'][key] = value
                print(f"Added base LoRA: {value.get('lora')} with strength {value.get('strength')}")

            # Then add the user-selected LoRAs
            lora_count = len(base_loras)
            for lora in options['loras']:
                if lora['name']:  # Only add LoRAs that have a name selected
                    lora_count += 1
                    lora_key = f'lora_{lora_count}'
                    node_21['inputs'][lora_key] = {
                        "on": True,
                        "lora": lora['name'],
                        "strength": lora['strength']
                    }
                    print(f"Adding additional LoRA {lora_key}: {lora['name']} with strength {lora['strength']}")

        # Create temp directory if it doesn't exist
        temp_dir = os.path.join(BASE_DIR, 'temp_workflows')
        os.makedirs(temp_dir, exist_ok=True)

        # Create a temporary workflow file for this generation
        temp_workflow_name = os.path.basename(workflow_file)
        temp_workflow_path = os.path.join(temp_dir, temp_workflow_name)

        # Save the temporary workflow
        with open(temp_workflow_path, 'w') as f:
            json.dump(workflow, f, indent=2)

        print(f"Saved temporary workflow to: {temp_workflow_path}")
        print(f"Final workflow LoRAs: {json.dumps(workflow['21']['inputs'], indent=2)}")

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

        return jsonify(workflow)

    except Exception as e:
        error_msg = f"Error getting default workflow: {str(e)}"
        print(error_msg, file=sys.stderr)
        return jsonify({'error': error_msg}), 500



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
    if not prompt:
        print("Cannot generate images without a prompt.", file=sys.stderr)
        return False

    if not character_name:
        print("Cannot generate images without a character name.", file=sys.stderr)
        return False

    queue_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate", "queue_and_retrieve_images.py")

    if not os.path.exists(queue_script):
        print(f"Queue script not found at: {queue_script}", file=sys.stderr)
        return False

    try:
        result = subprocess.run(
            ["python3", queue_script, prompt, character_name],
            capture_output=True,
            text=True,
            check=True
        )

        # Try to extract and save the seed from the output
        try:
            output_lines = result.stdout.split('\n')
            for line in output_lines:
                if line.startswith('Seed:'):
                    seed = int(line.split(':')[1].strip())
                    save_last_seed(seed)
                    break
        except:
            pass

        return True
    except subprocess.CalledProcessError as e:
        print(f"Error generating images: {e.stderr.strip()}", file=sys.stderr)
        return False

@app.route('/generate_new_image', methods=['POST'])
@login_required
def generate_new_image():
    selected_character = request.form.get('character')
    if not selected_character:
        return "No character selected.", 400

    # Update the session with the selected character
    session['selected_character'] = selected_character

    main_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')

    try:
        result = subprocess.run(
            ["python3", main_py_path, "auto", "--character", selected_character],
            capture_output=True,
            text=True,
            check=True
        )

        # Extract prompt from the output (last non-empty line)
        output_lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
        if output_lines:
            prompt = output_lines[-1]
            save_prompt(prompt)

        return jsonify({"success": True})

    except subprocess.CalledProcessError as e:
        return f"Error generating image: {e.stderr.strip()}", 400


@app.route('/regenerate_image', methods=['POST'])
@login_required
def regenerate_image():
    """Handle image regeneration requests with detailed error logging."""
    try:
        # Log the incoming request data
        print("Regenerate Image Request Data:", request.form)

        selected_character = request.form.get('character')
        if not selected_character:
            error_msg = "No character selected."
            print(f"Error in regenerate_image: {error_msg}")
            return jsonify({"error": error_msg}), 400

        # Update the session with the selected character
        session['selected_character'] = selected_character

        prompt = get_latest_prompt()
        if not prompt:
            error_msg = "No previously saved prompt to regenerate."
            print(f"Error in regenerate_image: {error_msg}")
            return jsonify({"error": error_msg}), 400

        # Get workflow options from the session
        temp_workflow_path = session.get('temp_workflow_path')
        if temp_workflow_path:
            print(f"Using temporary workflow: {temp_workflow_path}")

        main_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')
        print(f"Using main.py path: {main_py_path}")
        print(f"Regenerating with character: {selected_character}")
        print(f"Using prompt: {prompt}")

        try:
            # Run the generation command
            result = subprocess.run(
                ["python3", main_py_path, "manual", "--character", selected_character],
                input=prompt,
                text=True,
                capture_output=True,
                check=True
            )

            # Log the command output
            if result.stdout:
                print("Command stdout:", result.stdout)
            if result.stderr:
                print("Command stderr:", result.stderr)

            # Keep using the same prompt since we're regenerating
            save_prompt(prompt)
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
    manual_prompt = request.form.get('manual_prompt')
    selected_character = request.form.get('character')

    if not manual_prompt or not selected_character:
        return "Character and manual prompt are required.", 400

    # Update the session with the selected character
    session['selected_character'] = selected_character

    main_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')

    try:
        result = subprocess.run(
            ["python3", main_py_path, "manual", "--character", selected_character],
            input=manual_prompt,
            capture_output=True,
            text=True,
            check=True
        )

        save_prompt(manual_prompt)
        return jsonify({"success": True})

    except subprocess.CalledProcessError as e:
        return f"Error with manual image generation: {e.stderr.strip()}", 400


@app.route('/enhanced_generation', methods=['POST'])
@login_required
def enhanced_generation():
    manual_prompt = request.form.get('manual_prompt')
    selected_character = request.form.get('character')

    if not manual_prompt or not selected_character:
        return "Character and manual prompt are required.", 400

    # Update the session with the selected character
    session['selected_character'] = selected_character

    # Update workflow options before generating
    try:
        # Get the current advanced options from the frontend
        advanced_options = request.form.get('advancedOptions')
        if advanced_options:
            advanced_options = json.loads(advanced_options)
            # Update the workflow with current options
            update_workflow_options_sync(selected_character, advanced_options)
    except Exception as e:
        print(f"Error updating workflow options: {e}", file=sys.stderr)
        return f"Error updating workflow options: {str(e)}", 400

    main_py_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')

    try:
        result = subprocess.run(
            ["python3", main_py_path, "enhanced", "--character", selected_character],
            input=manual_prompt,
            capture_output=True,
            text=True,
            check=True
        )

        # Extract prompt from the output (last non-empty line)
        output_lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
        if output_lines:
            prompt = output_lines[-1]
            save_prompt(prompt)

        return jsonify({"success": True})

    except subprocess.CalledProcessError as e:
        return f"Error with enhanced image generation: {e.stderr.strip()}", 400


if __name__ == '__main__':
    app.run(
        host=config.get('server', 'host', default='0.0.0.0'),
        port=config.get('server', 'port', default=4567),
        debug=config.get('server', 'debug', default=True)
    )
