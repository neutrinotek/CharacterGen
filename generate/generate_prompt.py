import os
import json
import requests
import yaml
import argparse
import sys
from config.config_utils import config

OLLAMA_API_URL = config.get('services', 'llm', 'url')


def load_characters(config_path):
    """
    Load characters from a YAML configuration file.
    """
    try:
        with open(config_path, 'r') as file:
            characters = yaml.safe_load(file)
            if not characters:
                print("Warning: Characters file is empty", file=sys.stderr)
            return characters or {}
    except FileNotFoundError:
        print(f"Configuration file not found at {config_path}.", file=sys.stderr)
        return {}
    except yaml.YAMLError as exc:
        print(f"Error parsing YAML file: {exc}", file=sys.stderr)
        return {}


def generate_ollama_prompt(character, prompt_type="auto", user_prompt=None):
    """
    Generate a prompt for Ollama based on the character and generation type.
    """
    if not character:
        print("Error: Character data is empty", file=sys.stderr)
        return None

    character_name = character.get("name")
    if not character_name:
        print("Error: Character name is missing", file=sys.stderr)
        return None

    # Get physical description and personality separately
    physical_description = character.get("physical_description", "")
    personality = character.get("personality", "")

    # For backwards compatibility, check for combined description
    if not physical_description and not personality:
        description = character.get("description", "")
        if description:
            physical_description = description

    if prompt_type == "auto":
        prompt = (
            f"Generate a descriptive text-to-image prompt for the character {character_name}.\n"
            f"Physical Description: {physical_description}\n"
            f"Personality and Style: {personality}\n"
        )
    elif prompt_type == "enhanced":
        if not user_prompt:
            print("Error: User prompt is required for enhanced generation", file=sys.stderr)
            return None
        prompt = (
            f"Use the following information to generate an optimized prompt for the character {character_name}:\n"
            f"Physical Description: {physical_description}\n"
            f"Personality and Style: {personality}\n"
            f"User's Input: {user_prompt}\n"
        )
    else:
        print(f"Invalid prompt type: {prompt_type}", file=sys.stderr)
        return None

    return prompt


def ollama(character, prompt_type="auto", user_prompt=None):
    """
    Generate a descriptive text-to-image prompt using Ollama API.
    """
    prompt = generate_ollama_prompt(character, prompt_type, user_prompt)
    if not prompt:
        return None

    payload = {
        "model": "dolphin-llama3.1-8b:latest",
        "prompt": prompt,
        "system": """ You are an AI assistant that writes prompts for text to image AI models, specifically for generating images of characters. 
                      You will be provided with two types of character information:
                      1. Physical Description: These are mandatory attributes that must be included exactly as specified
                      2. Personality and Style: These should influence the scene, pose, and mood but not override physical traits

                      You must strictly adhere to all physical descriptions provided, ensuring every physical attribute is included.
                      Personality and Style traits are partially optional: They should inspire the setting, pose, and mood of the image without contradicting physical traits, but can be modified and should not hinder creativity.
                      If you are given any specific details labeled as "User Input" those elements must be strictly included in the prompt.
                      If a word or phrase in the User Input is placed in quotes, those exact words must be included in the prompt.
		              If any information in the User Input contradicts other information provided, the user input overrides other information. 

                      Prompts should be written in plain speaking language (i.e. no headers, or titles), and use full sentence format. 
                      Write the prompts as if you are describing the scene to someone. Do not create titles or additional writing that is not directly describing the image. 
                      Prompts must include the character's name, as well as a description of their physical appearance, the clothing they are wearing (or lack thereof), and their pose, an action they are taking, or their body position within the scene. 
                      It should also include a description of their location, including the lighting. 
                      Include additional details such as camera effects (i.e. film grain, bokeh, etc), camera type, or mood. 
                      Keep prompts relatively brief: 2 to 3 sentences, maximum. 
                      Make sure your description of the character and scene makes sense. Do not include things that could contradict something else in the description.
                      If the scene calls for the character to have a particular expression on their face, such as being frightened, happy, angry, etc. Describe how that expression appears in their facial features. 
                      Be definitive and decisive with your statements: do not make comments that could involve an either/or situation, or leave things up to interpretation. 
                      Be sure to keep the photos interesting: use new and/or interesting locations locations, varying backdrops, camera angles, and dynamic poses. """
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, stream=True)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Ollama API request failed: {e}", file=sys.stderr)
        return None

    generated_prompt = ""
    try:
        for line in response.iter_lines():
            if line:
                line_json = json.loads(line.decode('utf-8'))
                generated_prompt += line_json.get("response", "")
                if line_json.get("done", False):
                    break

        # Check if we actually got a prompt
        if not generated_prompt.strip():
            print("Error: Empty prompt generated", file=sys.stderr)
            return None

        return generated_prompt.strip()
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}", file=sys.stderr)
        return None


def save_prompt_to_file(prompt):
    """
    Save the generated prompt to a text file.
    """
    if not prompt:
        print("Error: Cannot save empty prompt", file=sys.stderr)
        return False

    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static')
    os.makedirs(static_dir, exist_ok=True)  # Ensure static directory exists
    output_path = os.path.join(static_dir, 'latest_prompt.txt')

    try:
        with open(output_path, 'w') as file:
            file.write(prompt)
        return True
    except IOError as e:
        print(f"Failed to save prompt to file: {e}", file=sys.stderr)
        return False


def main():
    """
    Main function to parse arguments and generate the prompt.
    """
    parser = argparse.ArgumentParser(
        description="Generate a text-to-image prompt for a character."
    )
    parser.add_argument(
        "character",
        type=str,
        help="Name of the character to generate the prompt for."
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["auto", "enhanced"],
        default="auto",
        help="Generation mode: 'auto' for random generation, 'enhanced' for combining with user input"
    )
    args = parser.parse_args()

    # Define paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_dir = os.path.join(script_dir, '..', 'config')
    config_path = os.path.join(config_dir, 'characters.yaml')

    # Load characters
    characters = load_characters(config_path)
    if not characters:
        sys.exit(1)

    character_key = args.character
    if character_key not in characters:
        print(f"Character '{character_key}' not found in the configuration file.", file=sys.stderr)
        sys.exit(1)

    character_data = characters[character_key]
    if not isinstance(character_data, dict):
        print(f"Invalid character data format for '{character_key}'", file=sys.stderr)
        sys.exit(1)

    # Add the character's name to the character data
    character_data["name"] = character_key

    # Handle different generation modes
    if args.mode == "enhanced":
        # Read user prompt from stdin
        user_prompt = sys.stdin.read().strip()
        if not user_prompt:
            print("No user prompt provided for enhanced generation.", file=sys.stderr)
            sys.exit(1)
        prompt = ollama(character_data, "enhanced", user_prompt)
    else:
        prompt = ollama(character_data, "auto")

    if prompt:
        # Print to stdout for capturing by main.py
        print(prompt)
        # Save to file
        if save_prompt_to_file(prompt):
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        print("Failed to generate prompt.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()