import json
import uuid
import urllib.request
import websocket
import sys
import os
import yaml
import time
from datetime import datetime
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import io
from config.config_utils import config

# Configuration Constants
COMFYUI_BASE_URL = config.get('services', 'comfyui', 'base_url')
COMFYUI_WS_URL = config.get('services', 'comfyui', 'ws_url')
CLIENT_ID = str(uuid.uuid4())
TIMEOUT = config.get('services', 'comfyui', 'timeout', default=300)
# Fixed path definitions
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMFYUI_DIR = config.get('paths', 'comfyui_dir')
IMAGES_FOLDER = os.path.join(BASE_DIR, 'images')
STATIC_IMAGES_FOLDER = os.path.join(BASE_DIR, 'static', 'images')
LATEST_IMAGE_NAME = "latest_image.png"
PREVIOUS_SEED_FILE = os.path.join(BASE_DIR, 'static', 'previous_seed.txt')

# Ensure the images directories exist
os.makedirs(IMAGES_FOLDER, exist_ok=True)
os.makedirs(STATIC_IMAGES_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(PREVIOUS_SEED_FILE), exist_ok=True)

def load_characters(config_path):
    try:
        with open(config_path, 'r') as file:
            return yaml.safe_load(file)
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"Error loading characters file: {e}", file=sys.stderr)
        return {}


def get_workflow(character_name, characters):
    workflow_file = characters.get(character_name, {}).get("workflow_file")
    if not workflow_file:
        print(f"Workflow file not specified for character '{character_name}'.", file=sys.stderr)
        return None

    # Check first in temp_workflows directory
    temp_workflow_path = os.path.join(BASE_DIR, 'temp_workflows', os.path.basename(workflow_file))
    if os.path.exists(temp_workflow_path):
        try:
            with open(temp_workflow_path, "r") as file:
                workflow = json.load(file)
                print(f"Loaded temporary workflow for character '{character_name}': {temp_workflow_path}")
                return workflow
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading temporary workflow file '{temp_workflow_path}': {e}", file=sys.stderr)
            # Fall through to try the original workflow file

    # If no temporary workflow exists or failed to load, try the original workflow file
    workflow_path = os.path.join(BASE_DIR, workflow_file)
    try:
        with open(workflow_path, "r") as file:
            workflow = json.load(file)
            print(f"Loaded original workflow for character '{character_name}': {workflow_path}")
            return workflow
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading workflow file '{workflow_path}': {e}", file=sys.stderr)
        return None


def extract_seed_from_workflow(workflow_data):
    """Extract the seed value from the workflow data."""
    try:
        # Look for the Seed node (node 25) in the workflow
        if '25' in workflow_data:
            node_25 = workflow_data['25']
            if 'inputs' in node_25 and 'seed' in node_25['inputs']:
                seed = node_25['inputs']['seed']
                if isinstance(seed, (int, float)) and seed != -1:
                    print(f"Successfully extracted seed {seed} from workflow")
                    # Ensure the seed is saved as an integer
                    return int(seed)
                else:
                    print(f"Found invalid seed value: {seed}", file=sys.stderr)
            else:
                print("No seed found in node 25 inputs", file=sys.stderr)
        else:
            print("Node 25 not found in workflow", file=sys.stderr)
    except Exception as e:
        print(f"Error extracting seed from workflow: {e}", file=sys.stderr)
    return -1


def save_seed_to_file(seed):
    """Save the seed value to a file."""
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(PREVIOUS_SEED_FILE), exist_ok=True)

        # Only save valid seeds
        if seed != -1:
            with open(PREVIOUS_SEED_FILE, 'w') as f:
                f.write(str(seed))
            print(f"Successfully saved seed {seed} to {PREVIOUS_SEED_FILE}")
            return True
        else:
            print("Not saving invalid seed value (-1)")
            return False
    except Exception as e:
        print(f"Error saving seed to file {PREVIOUS_SEED_FILE}: {e}", file=sys.stderr)
        return False

def queue_prompt(prompt_text, character_name, characters):
    workflow = get_workflow(character_name, characters)
    if not workflow:
        print(f"No valid workflow found for character '{character_name}'.", file=sys.stderr)
        return None

    node_id = "6"
    if node_id not in workflow or "inputs" not in workflow[node_id] or "text" not in workflow[node_id]["inputs"]:
        print(f"Invalid workflow structure for character '{character_name}'.", file=sys.stderr)
        return None

    workflow[node_id]["inputs"]["text"] = prompt_text
    print(f"Queuing prompt '{prompt_text}' for character '{character_name}'.")

    try:
        data = json.dumps({"prompt": workflow, "client_id": CLIENT_ID}).encode('utf-8')
        req = urllib.request.Request(
            f"{COMFYUI_BASE_URL}/prompt",
            data=data,
            headers={'Content-Type': 'application/json'}
        )

        with urllib.request.urlopen(req) as response:
            resp_data = response.read()
            response_json = json.loads(resp_data)
            prompt_id = response_json.get("prompt_id")
            if not prompt_id:
                print("No prompt_id returned from ComfyUI server.", file=sys.stderr)
                return None
            print(f"Prompt ID '{prompt_id}' successfully queued.")
            return prompt_id

    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"Error queuing prompt: {e}", file=sys.stderr)
        return None


def get_character_directory(character_name):
    directory_name = character_name.replace(' ', '_')
    character_path = os.path.join(IMAGES_FOLDER, directory_name)
    os.makedirs(character_path, exist_ok=True)
    return character_path


def generate_image_filename(character_name, index=None):
    safe_name = character_name.replace(' ', '_')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if index is not None:
        return f"{safe_name}_{timestamp}_{index}.png"
    return f"{safe_name}_{timestamp}.png"


def save_image_with_metadata(image_data, output_path, workflow_data, prompt_id, original_prompt=None):
    """Save image with properly formatted workflow metadata, matching ComfyUI's exact structure."""
    try:
        # First save the basic image to ensure we don't lose it
        with open(output_path, 'wb') as f:
            f.write(image_data)
        print(f"Saved basic image: {output_path}")

        # Now open with PIL and add metadata
        image = Image.open(output_path)

        # Print LoRA information for debugging
        if '21' in workflow_data and 'inputs' in workflow_data['21']:
            print("LoRAs used in generation:")
            for key, value in workflow_data['21']['inputs'].items():
                if isinstance(value, dict) and 'lora' in value:
                    print(f"  - {value['lora']} (strength: {value.get('strength', 1.0)})")

        # Build list of links from workflow data
        links = []
        link_id = 0
        link_map = {}  # Map from (origin_node_id, origin_slot, target_node_id, target_slot) to link_id
        nodes_dict = {}  # Map node_id to node dict
        for node_id_str, node_data in workflow_data.items():
            if not node_id_str.isdigit():
                continue
            node_id = int(node_id_str)
            nodes_dict[node_id] = node_data

        # First pass: Prepare nodes with inputs and outputs
        nodes = []
        for node_id, node_data in nodes_dict.items():
            # Base node structure
            node = {
                "id": node_id,
                "type": node_data.get("class_type", ""),
                "pos": {"0": 0, "1": 0},  # Default position
                "size": {"0": 315, "1": 98},  # Default size
                "flags": {},
                "order": node_id,
                "mode": 0,
                "inputs": [],
                "outputs": [],
                "properties": {"Node name for S&R": node_data.get("class_type", "")},
                "widgets_values": node_data.get("widgets_values", [])
            }

            input_names = list(node_data.get("inputs", {}).keys())
            input_names_to_slot_index = {}
            for idx, input_name in enumerate(input_names):
                input_names_to_slot_index[input_name] = idx
                input_value = node_data["inputs"][input_name]
                node['inputs'].append({
                    'name': input_name,
                    'type': input_name.upper(),
                    'links': [],
                    'slot_index': idx
                })

            # Outputs will be determined based on links
            node['output_names_to_slot_index'] = {}

            nodes.append(node)
            node_data['node_struct'] = node  # Save reference for later

        # Second pass: Build links and update nodes
        for node_id, node_data in nodes_dict.items():
            node = node_data['node_struct']
            input_names_to_slot_index = {inp['name']: inp['slot_index'] for inp in node['inputs']}

            for input_name, input_value in node_data.get('inputs', {}).items():
                if isinstance(input_value, list) and len(input_value) == 2:
                    source_node_id = int(input_value[0])
                    source_output_slot_index = int(input_value[1])
                    target_node_id = node_id
                    target_input_slot_index = input_names_to_slot_index[input_name]

                    # Create a unique key for the link
                    link_key = (source_node_id, source_output_slot_index, target_node_id, target_input_slot_index)
                    if link_key not in link_map:
                        # Create link
                        link = [
                            link_id,
                            source_node_id,
                            source_output_slot_index,
                            target_node_id,
                            target_input_slot_index,
                            input_name.upper()
                        ]
                        links.append(link)
                        link_map[link_key] = link_id
                        link_id += 1
                    else:
                        link_id = link_map[link_key]

                    # Update target node's input
                    node['inputs'][target_input_slot_index]['links'].append(link_id)

                    # Update source node's outputs
                    source_node_data = nodes_dict[source_node_id]
                    source_node = source_node_data['node_struct']
                    output_slot_index = source_output_slot_index
                    outputs = source_node['outputs']

                    # Ensure the output slot exists
                    while len(outputs) <= output_slot_index:
                        outputs.append({
                            'name': '',  # Optionally set the output name
                            'type': '',  # Optionally set the output type
                            'links': [],
                            'slot_index': len(outputs)
                        })

                    # Update source node's output
                    source_node['outputs'][output_slot_index]['links'].append(link_id)

            # Special handling for the Power Lora Loader node
            if node_data.get("class_type") == "Power Lora Loader (rgthree)":
                node["properties"]["Show Strengths"] = "Single Strength"
                node["size"] = {"0": 340.20001220703125, "1": 166}

                widgets_values = [
                    None,
                    {"type": "PowerLoraLoaderHeaderWidget"}
                ]

                # Add active LoRAs
                inputs = node_data.get("inputs", {})
                for key in sorted([k for k in inputs.keys() if k.startswith("lora_")]):
                    lora_data = inputs[key]
                    if isinstance(lora_data, dict):
                        widgets_values.append({
                            "on": lora_data.get("on", True),
                            "lora": lora_data.get("lora", ""),
                            "strength": lora_data.get("strength", 1),
                            "strengthTwo": None
                        })

                # Add remaining required values
                widgets_values.extend([None, ""])
                node["widgets_values"] = widgets_values

        # Remove temporary mappings from nodes
        for node_data in nodes_dict.values():
            node_data['node_struct'].pop('output_names_to_slot_index', None)

        # Create complete workflow metadata
        workflow_metadata = {
            "last_node_id": max(nodes_dict.keys(), default=0),
            "last_link_id": len(links),
            "nodes": nodes,
            "links": links,
            "groups": [],
            "config": {},
            "extra": {
                "ds": {
                    "scale": 0.9849732675808478,
                    "offset": [687.2656309965016, 400.0081852783683]
                }
            },
            "version": 0.4,
            "widget_idx_map": {
                "17": {"sampler_name": 0},
                "18": {"scheduler": 0},
                "19": {"noise_seed": 0}
            },
            "seed_widgets": {"19": 0}
        }

        # Save metadata to image
        png_info = PngInfo()

        # Add prompt metadata (as per ComfyUI's format)
        prompt_text = workflow_data.get('6', {}).get('inputs', {}).get('text', '')
        png_info.add_text("prompt", prompt_text)

        # Add complete workflow metadata using add_itxt
        # This ensures that large data is properly stored
        png_info.add_itxt(
            "workflow",
            json.dumps(workflow_metadata),
            lang="en",
            tkey="workflow",
            compressed=True
        )

        # Save the image with metadata
        image.save(output_path, 'PNG', pnginfo=png_info)
        print(f"Added metadata to image: {output_path}")
        print("Saved both prompt and workflow metadata")
        print(f"Number of nodes in workflow: {len(nodes)}")
        print(f"Number of links in workflow: {len(links)}")

        return True

    except Exception as e:
        print(f"Error in save_image_with_metadata: {e}", file=sys.stderr)
        return False



def get_prompt_from_history(history):
    """Extract prompt from history data regardless of structure."""
    try:
        prompt_data = history.get('prompt', {})

        # If prompt_data is a list (array of nodes)
        if isinstance(prompt_data, list):
            for node in prompt_data:
                if isinstance(node, dict) and node.get('id') == 6:
                    return node.get('inputs', {}).get('text', '')

        # If prompt_data is a dict (map of nodes)
        elif isinstance(prompt_data, dict):
            node_6 = prompt_data.get('6', {})
            if isinstance(node_6, dict):
                return node_6.get('inputs', {}).get('text', '')

        print(f"Warning: Could not find prompt text in history data structure: {type(prompt_data)}", file=sys.stderr)
        return None

    except Exception as e:
        print(f"Error extracting prompt from history: {e}", file=sys.stderr)
        return None


def get_history(prompt_id):
    url = f"{COMFYUI_BASE_URL}/history/{prompt_id}"
    try:
        with urllib.request.urlopen(url) as response:
            history_json = json.loads(response.read())
            history = history_json.get(prompt_id, {})
            if not history:
                print(f"No history found for prompt_id: {prompt_id}", file=sys.stderr)
            return history
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"Error fetching history: {e}", file=sys.stderr)
        return None


def get_image(filename, subfolder, folder_type):
    if not filename or not folder_type:
        print("Incomplete image information.", file=sys.stderr)
        return None

    url = f"{COMFYUI_BASE_URL}/view?filename={filename}&subfolder={subfolder}&type={folder_type}"

    try:
        with urllib.request.urlopen(url) as response:
            return response.read()
    except (urllib.error.HTTPError, urllib.error.URLError) as e:
        print(f"Error fetching image: {e}", file=sys.stderr)
        return None


def get_images_via_websocket(prompt_id, timeout=TIMEOUT):
    ws_url = f"{COMFYUI_WS_URL}/ws?clientId={CLIENT_ID}"
    ws = websocket.WebSocket()
    generated_images = []

    try:
        ws.connect(ws_url)
    except websocket.WebSocketException as e:
        print(f"WebSocket connection failed: {e}", file=sys.stderr)
        return [], None

    start_time = time.time()
    try:
        while True:
            try:
                message = ws.recv()
                if isinstance(message, str):
                    message_json = json.loads(message)
                    if message_json.get('type') == 'executing' and \
                            message_json.get('data', {}).get('prompt_id') == prompt_id:
                        if message_json['data'].get('node') is None:
                            break
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON message: {e}", file=sys.stderr)
                continue

            if time.time() - start_time > timeout:
                print("Image generation timed out.", file=sys.stderr)
                break
    except websocket.WebSocketException as e:
        print(f"WebSocket error: {e}", file=sys.stderr)
    finally:
        ws.close()

    history = get_history(prompt_id)
    if not history:
        print("No history data retrieved.", file=sys.stderr)
        return [], None

    for node_id, node_output in history.get('outputs', {}).items():
        if 'images' in node_output:
            for image_info in node_output['images']:
                image_data = get_image(
                    image_info.get('filename'),
                    image_info.get('subfolder'),
                    image_info.get('type')
                )
                if image_data:
                    generated_images.append((image_data, image_info.get('filename')))
                else:
                    print("No image data found for the image.")

    return generated_images, history


def save_images(images, prompt_id, character_name, history):
    """Save generated images with metadata."""
    if not images:
        print("No images to save.", file=sys.stderr)
        return

    # Get workflow data and prompt
    workflow_data = history.get('prompt', {})
    prompt_text = get_prompt_from_history(history)

    # Extract and save seed - Enhanced logging
    print("Attempting to extract and save seed...")
    seed = extract_seed_from_workflow(workflow_data)
    if seed != -1:
        print(f"Found seed: {seed}")
        if save_seed_to_file(seed):
            print(f"Successfully saved seed {seed} to file")
        else:
            print("Failed to save seed to file", file=sys.stderr)
    else:
        print("No valid seed found in workflow", file=sys.stderr)

    print(f"Seed: {seed}")

    if prompt_text:
        print(f"Saving images with prompt: {prompt_text}")
    else:
        print("Warning: No prompt text found in history", file=sys.stderr)

    # First, save the latest image to static directory
    try:
        if images:  # Check if we have any images
            image_data, _ = images[0]  # Get the first image
            latest_image_path = os.path.join(STATIC_IMAGES_FOLDER, LATEST_IMAGE_NAME)

            # Save with metadata
            save_image_with_metadata(image_data, latest_image_path, workflow_data, prompt_id, prompt_text)
            print(f"Saved latest image with metadata: {latest_image_path}")

    except Exception as e:
        print(f"Error saving latest image: {e}", file=sys.stderr)

    # Then save images to character directory
    character_dir = get_character_directory(character_name)
    print(f"Saving to character directory: {character_dir}")

    for idx, (image_data, original_filename) in enumerate(images):
        try:
            image_filename = generate_image_filename(character_name, idx if len(images) > 1 else None)
            image_path = os.path.join(character_dir, image_filename)

            # Save with metadata
            save_image_with_metadata(image_data, image_path, workflow_data, prompt_id, prompt_text)
            print(f"Saved character image with metadata: {image_path}")

        except Exception as e:
            print(f"Error processing image {idx}: {e}", file=sys.stderr)
            print(f"Character directory: {character_dir}")
            print(f"Attempted image path: {image_path}")


def main(prompt_text, character_name):
    config_path = os.path.join(BASE_DIR, 'config', 'characters.yaml')
    characters = load_characters(config_path)

    if character_name not in characters:
        print(f"Character '{character_name}' not found in configuration.", file=sys.stderr)
        return

    prompt_id = queue_prompt(prompt_text, character_name, characters)
    if not prompt_id:
        print("Failed to queue prompt. Exiting.", file=sys.stderr)
        return

    images, history = get_images_via_websocket(prompt_id)
    if not images:
        print("No images were generated.", file=sys.stderr)
        return

    save_images(images, prompt_id, character_name, history)


if __name__ == "__main__":
    if len(sys.argv) > 2:
        prompt = sys.argv[1]
        character = sys.argv[2]
    else:
        prompt = input("Enter a prompt for image generation: ")
        character = input("Enter the character name: ")

    main(prompt, character)