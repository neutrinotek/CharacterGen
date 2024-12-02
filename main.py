import subprocess
import os
import argparse
import sys
import yaml
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

def load_characters(config_path):
    try:
        with open(config_path, 'r') as file:
            characters = yaml.safe_load(file)
            if not characters:
                logger.warning(f"No characters found in {config_path}")
            return characters or {}
    except FileNotFoundError:
        logger.error(f"Configuration file not found at {config_path}.")
        return {}
    except yaml.YAMLError as exc:
        logger.error(f"Error parsing YAML file: {exc}")
        return {}

def get_prompt_auto(characters, character_name=None):
    if not characters:
        logger.error("No characters available to generate a prompt.")
        return None

    if not character_name:
        logger.error("No character name provided.")
        return None

    if character_name not in characters:
        logger.error(f"Character '{character_name}' not found in the configuration file.")
        return None

    generate_prompt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate", "generate_prompt.py")

    if not os.path.exists(generate_prompt_path):
        logger.error(f"Generate prompt script not found at: {generate_prompt_path}")
        return None

    try:
        env = os.environ.copy()
        env['PYTHONPATH'] = project_root

        logger.debug(f"Running generate_prompt.py for character: {character_name}")
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
            prompt = prompt_lines[-1]
            logger.info(f"Generated prompt: {prompt}")
            return prompt
        else:
            logger.error("No prompt generated (empty output)")
            return None

    except subprocess.CalledProcessError as e:
        logger.error(f"Error running generate_prompt.py: {e.stderr.strip()}")
        return None

def get_prompt_enhanced(characters, character_name=None, user_prompt=None):
    if not characters or not character_name or not user_prompt:
        logger.error("Missing required information for enhanced prompt generation.")
        return None

    if character_name not in characters:
        logger.error(f"Character '{character_name}' not found in the configuration file.")
        return None

    generate_prompt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate", "generate_prompt.py")

    if not os.path.exists(generate_prompt_path):
        logger.error(f"Generate prompt script not found at: {generate_prompt_path}")
        return None

    try:
        env = os.environ.copy()
        env['PYTHONPATH'] = project_root

        logger.debug(f"Running enhanced prompt generation for character: {character_name}")
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
            prompt = prompt_lines[-1]
            logger.info(f"Generated enhanced prompt: {prompt}")
            return prompt
        else:
            logger.error("No prompt generated (empty output)")
            return None

    except subprocess.CalledProcessError as e:
        logger.error(f"Error running generate_prompt.py: {e.stderr.strip()}")
        return None

def generate_images(prompt, character_name=None):
    if not prompt:
        logger.error("Cannot generate images without a prompt.")
        return False

    if not character_name:
        logger.error("Cannot generate images without a character name.")
        return False

    queue_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate", "queue_and_retrieve_images.py")

    if not os.path.exists(queue_script):
        logger.error(f"Queue script not found at: {queue_script}")
        return False

    try:
        env = os.environ.copy()
        env['PYTHONPATH'] = project_root

        logger.debug(f"Generating images for character {character_name} with prompt: {prompt}")
        result = subprocess.run(
            ["python3", queue_script, prompt, character_name],
            capture_output=True,
            text=True,
            check=True,
            env=env
        )
        logger.info("Image generation completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error generating images: {e.stderr.strip()}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Generate images based on prompts.")
    parser.add_argument("mode", choices=["auto", "manual", "enhanced"],
                      help="Choose 'auto' for random generation, 'manual' for direct prompt, or 'enhanced' for combined generation.")
    parser.add_argument("--character", type=str, help="Name of the character.")
    args = parser.parse_args()

    if not args.character:
        logger.error("Character name is required.")
        sys.exit(1)

    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'characters.yaml')
    characters = load_characters(config_path)

    if not characters:
        logger.error("No characters loaded from configuration.")
        sys.exit(1)

    if args.character not in characters:
        logger.error(f"Character '{args.character}' not found in configuration.")
        sys.exit(1)

    if args.mode == "auto":
        prompt = get_prompt_auto(characters, args.character)
    elif args.mode == "enhanced":
        user_prompt = sys.stdin.read().strip()
        prompt = get_prompt_enhanced(characters, args.character, user_prompt)
    else:  # manual mode
        prompt = sys.stdin.read().strip()
        logger.info(f"Using manual prompt: {prompt}")

    if not prompt:
        logger.error("No prompt was generated or entered.")
        sys.exit(1)

    # Always print the prompt to stdout for capture by the calling process
    print(prompt)

    if not generate_images(prompt, args.character):
        logger.error("Failed to generate images.")
        sys.exit(1)

if __name__ == "__main__":
    main()