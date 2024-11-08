# CharacterGen
A web app that acts as a pipeline between Ollama and ComfyUI for quick, and easy generation of character images.

This project started as a simple tool to allow me to quickly, and semi-automatically generate enhanced prompts and images for Character Loras based on my ComfyUI workflows.

ComfyUI is great, but sometimes I just need a quick and easy way of generating an image, especially for some characters I tinker with.  
This also makes it much easier to generate new images from a mobile device.

After creating the basics, I kind of got caught up in the project and started adding more features here and there.
It's still very much a work in progress, but I felt like it was in a good enough state that I could upload it. 

## How it Works:
### Image Generation
- The app links to an instance of Ollama to generate either "random" or enhanced prompts of specific characters. 
- Characters are set up in a characters.yaml file, where their physical description, personality and/or other defining traits, and a workflow file can be defined.
![image](https://github.com/user-attachments/assets/1c98e810-2db8-4a94-a035-22297cd8fe8c)


- When a character is selected from the dropdown menu, and image generation is triggered, Ollama will use the information in characters.yaml to create a random or enhanced prompt for that character.
- Enhanced prompts are done through adding input in the prompt section, and clicking "Enhanced Generation."
- Clicking Manual Generation with only send the text in the prompt box to ComfyUI without engaging with Ollama (keep in mind, if a character is selected, their Lora will still be active.)
- If you like the prompt, clicking Regenerate Image will bypass Ollama and send the exact same prompt back to ComfyUI. 
![image](https://github.com/user-attachments/assets/36296782-56a9-46b4-8827-b8202465a314)


### Advanced Options
The Advanced Options allow you to temporarily tweak certain aspects of the workflow (Checkpoint model, dimensions, guidance, seed, and additional Loras), but this part still needs a little work:
- The reuse seed checkbox does not seem to work properly, although manually entering a seed does.
- These settings are based on the generic-workflow.json file. I have not tested this on other workflows, so changing the default workflow too much could break something.
- Also, if changes are made here and the character is changed, the settings will be applied to the new character's workflow unless you click Reset to Default (I'm not sure whether I like this or not).
  
 ![image](https://github.com/user-attachments/assets/7aaaa8e7-460f-4ed4-b7db-12aee1d1d9e2)

### Browsing
Images are automatically saved in a directory with the character name within the Images/ folder. The browse feature allows you to view images directly in the browser and delete them manually if you want. 


## Setup:
- Clone the repo, set up a python virtual environment, and install dependencies in requirements.txt
- **Set up your character info:**
  - The workflows/ directory contains the default character workflows for ComfyUI. The one labeled generic-workflow.json is a very simple, checkpoint based workflow, and what most of the app was developed using. You should be able to upload other workflows, but I can't guarantee whether any of the "Advanced Options" will work with them.
  - Enter your Character Names and descriptions in the config/characters.yaml file, as well as the name of the workflow for that character.
- **App Configuration:**
  - config/app_config.yaml
  - Change to your desired host/port (optional)
  - Enter the appropriate URLs for your Ollama and ComfyUI Instances
  - Enter the path for your ComfyUI installation (this assumes it is running on the same machine as CharacterGen - if not... idk what it will break).

## **Running the App + Current Security Features**
  - While I don't necessarily plan on personally running this in production, I did want to add some security features in case I ever wanted to let my friends get on and tinker. Right now it is not optimal, and I cannot guarantee it is the most secure setup possible, so **expose this service at your own risk!**
  - On the first run, the app should create a new SQL database and give you default login credentials:
    - username: admin
    - password: changeme
  - The default user can be deleted once you register a new account and make that account an admin.
  - Registering a new account requires the admin to manually approve the new account.
  - Currently, password reset is done by providing the user with a reset link that can only be used once an admin approves the reset. This isn't ideal and still a WIP, but some of the framework for implementing e-mail reset should be in the code. 
 
## **Things To Do/Current Issues**
  - I am still tinkering with the Ollama system prompt. It does pretty good, but anything put in the "personality" section of the character file gets weighted too heavily for my liking. This could be great if you want someone to always wear a certain style, or be in a certain location, but personally I would like to give it a bit more room for creativity. 
  - I'm considering working in a way to adjust the Character descriptions directly in the UI, but we'll see.
  - Fix the Reuse Seed checkbox
  - Set up e-mail password reset functionality
  - Make the Advanced Options more robust to handle different types of workflows
  - Add more functionality in the Browse page for easier file management. 
