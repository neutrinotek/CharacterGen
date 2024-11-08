import subprocess
import os
import argparse
import sys
import yaml

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

def load_characters(config_path):
    try:
        with open(config_path, 'r') as file:
            characters = yaml.safe_load(file)
            if not characters:
                print(f"Warning: No characters found in {config_path}", file=sys.stderr)
            return characters or {}
    except FileNotFoundError:
        print(f"Configuration file not found at {config_path}.", file=sys.stderr)
        return {}
    except yaml.YAMLError as exc:
        print(f"Error parsing YAML file: {exc}", file=sys.stderr)
        return {}


def get_prompt_auto(characters, character_name=None):
    if not characters:
        print("No characters available to generate a prompt.", file=sys.stderr)
        return None

    if not character_name:
        print("No character name provided.", file=sys.stderr)
        return None

    if character_name not in characters:
        print(f"Character '{character_name}' not found in the configuration file.", file=sys.stderr)
        return None

    generate_prompt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate", "generate_prompt.py")

    if not os.path.exists(generate_prompt_path):
        print(f"Generate prompt script not found at: {generate_prompt_path}", file=sys.stderr)
        return None

    try:
        env = os.environ.copy()
        env['PYTHONPATH'] = project_root  # Add project root to PYTHONPATH

        result = subprocess.run(
            ["python3", generate_prompt_path, character_name, "--mode", "auto"],
            capture_output=True,
            text=True,
            check=True,
            env=env
        )

        # Get the last non-empty line as the prompt
        prompt_lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
        if prompt_lines:
            return prompt_lines[-1]
        else:
            print("No prompt generated (empty output)", file=sys.stderr)
            return None

    except subprocess.CalledProcessError as e:
        print(f"Error running generate_prompt.py: {e.stderr.strip()}", file=sys.stderr)
        return None


def get_prompt_enhanced(characters, character_name=None, user_prompt=None):
    if not characters or not character_name or not user_prompt:
        print("Missing required information for enhanced prompt generation.", file=sys.stderr)
        return None

    if character_name not in characters:
        print(f"Character '{character_name}' not found in the configuration file.", file=sys.stderr)
        return None

    generate_prompt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate", "generate_prompt.py")

    if not os.path.exists(generate_prompt_path):
        print(f"Generate prompt script not found at: {generate_prompt_path}", file=sys.stderr)
        return None

    try:
        env = os.environ.copy()
        env['PYTHONPATH'] = project_root  # Add project root to PYTHONPATH

        result = subprocess.run(
            ["python3", generate_prompt_path, character_name, "--mode", "enhanced"],
            input=user_prompt,
            capture_output=True,
            text=True,
            check=True,
            env=env
        )

        prompt_lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
        if prompt_lines:
            return prompt_lines[-1]
        else:
            print("No prompt generated (empty output)", file=sys.stderr)
            return None

    except subprocess.CalledProcessError as e:
        print(f"Error running generate_prompt.py: {e.stderr.strip()}", file=sys.stderr)
        return None


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
        env = os.environ.copy()
        env['PYTHONPATH'] = project_root  # Add project root to PYTHONPATH

        result = subprocess.run(
            ["python3", queue_script, prompt, character_name],
            capture_output=True,
            text=True,
            check=True,
            env=env
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error generating images: {e.stderr.strip()}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Generate images based on prompts.")
    parser.add_argument("mode", choices=["auto", "manual", "enhanced"],
                        help="Choose 'auto' for random generation, 'manual' for direct prompt, or 'enhanced' for combined generation.")
    parser.add_argument("--character", type=str, help="Name of the character.")
    args = parser.parse_args()

    if not args.character:
        print("Character name is required.", file=sys.stderr)
        sys.exit(1)

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'characters.yaml')
    characters = load_characters(config_path)

    if not characters:
        print("No characters loaded from configuration.", file=sys.stderr)
        sys.exit(1)

    if args.character not in characters:
        print(f"Character '{args.character}' not found in configuration.", file=sys.stderr)
        sys.exit(1)

    if args.mode == "auto":
        prompt = get_prompt_auto(characters, args.character)
    elif args.mode == "enhanced":
        user_prompt = sys.stdin.read().strip()
        prompt = get_prompt_enhanced(characters, args.character, user_prompt)
    else:  # manual mode
        prompt = sys.stdin.read().strip()

    if not prompt:
        print("No prompt was generated or entered.", file=sys.stderr)
        sys.exit(1)

    if not generate_images(prompt, args.character):
        print("Failed to generate images.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()