import os
import subprocess
import yaml

def create_default_yml(env_name):
    """Creates an environment.yml file with the environment setup if it doesn't exist."""
    if not os.path.exists("environment.yml"):
        environment_data = {
            'name': env_name,
            'channels': ['defaults'],
            'dependencies': [
                'python=3.10',
                'pip',
                'pyyaml'
            ]
        }
        with open("environment.yml", 'w') as file:
            yaml.dump(environment_data, file, default_flow_style=False)
        print("Environment YAML file created with local settings.")
    else:
        print("Environment YAML file already exists.")

def create_env_directly(env_name):
    """Create the Conda environment directly using conda create without specifying a prefix."""
    print(f"Attempting to create Conda environment '{env_name}' in the default Conda location")
    result = subprocess.run(
        ["conda", "create", "--name", env_name, "-y", "python=3.10", "pip", "pyyaml"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("Local environment created successfully.")
        print(result.stdout)
    else:
        print("Failed to create environment.")
        print(result.stderr)

def check_env_exists(env_name):
    """Check if the Conda environment exists."""
    result = subprocess.run(
        ["conda", "env", "list"],
        capture_output=True, text=True
    )
    return env_name in result.stdout

if __name__ == "__main__":
    project_directory = os.getcwd()
    folder_name = os.path.basename(project_directory)
    env_name = folder_name + "_env"

    # Create the environment.yml file if it doesn't exist
    create_default_yml(env_name)

    # Check if environment exists, create if not
    if not check_env_exists(env_name):
        create_env_directly(env_name)
    else:
        print(f"Conda environment '{env_name}' already exists.")
