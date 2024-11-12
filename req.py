import os
import subprocess
import sys
import yaml

def read_env_name_from_yaml(yaml_file):
    """Reads the environment name from a YAML file."""
    if not os.path.exists(yaml_file):
        print(f"{yaml_file} not found. Exiting...")
        exit(1)
    with open(yaml_file, 'r') as file:
        data = yaml.safe_load(file)
        return data.get('name', None)

def check_environment_exists(env_name):
    """Checks if the specified Conda environment exists."""
    result = subprocess.run(["conda", "env", "list"], capture_output=True, text=True)
    if env_name in result.stdout:
        return True
    return False

def is_running_in_env(env_name):
    """Checks if the current Python executable is running within the specified environment."""
    python_exec_path = sys.executable
    expected_path_segment = os.path.join("envs", env_name)
    if expected_path_segment in python_exec_path:
        return True
    return False

def run_pip_install(env_name):
    """Runs pip install from requirements.txt within a specified Conda environment."""
    if not os.path.exists("requirements.txt"):
        print("requirements.txt not found. Exiting...")
        exit(1)

    if not is_running_in_env(env_name):
        print(f"Not running in the {env_name} environment. Please activate the environment and try again.")
        exit(1)

    print("Found requirements.txt. Installing dependencies...")
    command = f"conda run -n {env_name} pip install -r requirements.txt --upgrade"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print("Dependencies installed/updated successfully.")
        print(result.stdout)
    else:
        print("Failed to install/update dependencies.")
        print(result.stderr)

# Main script starts here
if __name__ == "__main__":
    yaml_file = 'environment.yml'
    env_name = read_env_name_from_yaml(yaml_file)
    if env_name and check_environment_exists(env_name):
        run_pip_install(env_name)
    else:
        print(f"Environment {env_name} does not exist or the name could not be determined. Exiting...")
