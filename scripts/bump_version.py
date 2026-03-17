import os
import re

CONSTANTS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'utils', 'constants.py')

def bump():
    if not os.path.exists(CONSTANTS_PATH):
        print("Error: Could not find utils/constants.py")
        return

    with open(CONSTANTS_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    match = re.search(r'APP_VERSION = "(\d+)\.(\d+)\.(\d+)"', content)
    if not match:
        print("Error: Could not parse APP_VERSION in utils/constants.py")
        return

    major, minor, patch = match.groups()
    new_version = f"{major}.{minor}.{int(patch) + 1}"
    
    new_content = re.sub(r'APP_VERSION = "[^"]+"', f'APP_VERSION = "{new_version}"', content)
    
    with open(CONSTANTS_PATH, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"Version bumped to: {new_version}")

if __name__ == "__main__":
    bump()
