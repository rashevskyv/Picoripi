import os
import re
import subprocess
import sys
from datetime import datetime

# Налаштування шляхів
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSTANTS_PATH = os.path.join(ROOT_DIR, 'utils', 'constants.py')
README_PATH = os.path.join(ROOT_DIR, 'README.md')
CHANGELOG_PATH = os.path.join(ROOT_DIR, 'CHANGELOG.md')

def log(message, color="\033[94m"):
    print(f"{color}{message}\033[0m")

def run_command(command, shell=True, capture=True):
    try:
        result = subprocess.run(command, shell=shell, check=True, capture_output=capture, text=True)
        return result.stdout.strip() if capture else True
    except subprocess.CalledProcessError as e:
        log(f"Error running command: {command}", "\033[91m")
        if capture:
            log(e.stderr, "\033[91m")
        return None

def get_current_version():
    if not os.path.exists(CONSTANTS_PATH):
        return None
    with open(CONSTANTS_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.search(r'APP_VERSION = "([^"]+)"', content)
    if match:
        return match.group(1)
    return None

def bump_version(version):
    parts = version.split('.')
    if len(parts) == 3:
        parts[2] = str(int(parts[2]) + 1)
        return '.'.join(parts)
    return version

def update_file(path, pattern, replacement):
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    new_content = re.sub(pattern, replacement, content)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)

def get_recent_commits():
    # Attempt to get last tag for commit range
    last_tag = run_command("git describe --tags --abbrev=0")
    if not last_tag:
        return run_command("git log --oneline -n 10")
    return run_command(f"git log {last_tag}..HEAD --oneline")

def update_changelog(new_version, added, fixed, improved):
    date_str = datetime.now().strftime("%Y-%m-%d")
    new_entry = f"## [{new_version}] - {date_str}\n\n"
    
    if added:
        new_entry += "### Added\n"
        for item in added:
            new_entry += f"- {item}\n"
        new_entry += "\n"
    
    if fixed:
        new_entry += "### Fixed\n"
        for item in fixed:
            new_entry += f"- {item}\n"
        new_entry += "\n"
        
    if improved:
        new_entry += "### Improvements\n"
        for item in improved:
            new_entry += f"- {item}\n"
        new_entry += "\n"

    try:
        with open(CHANGELOG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        content = "# Changelog\n\nAll notable changes to the **Picoripi** project will be documented in this file.\n"
    
    header_pattern = r'(# Changelog\s+All notable changes to the \*\*Picoripi\*\* project[^\n]*\n)'
    if not re.search(header_pattern, content):
        new_content = "# Changelog\n\n" + new_entry + content
    else:
        new_content = re.sub(header_pattern, f'\\1\n{new_entry}', content, count=1)
    
    with open(CHANGELOG_PATH, 'w', encoding='utf-8') as f:
        f.write(new_content)
    return new_entry

def deploy():
    log("\n🚀 Starting Picoripi Deployment Process", "\033[1;92m")
    
    current_version = get_current_version()
    if not current_version:
        log("❌ Could not find current version in utils/constants.py", "\033[91m")
        return

    new_version = bump_version(current_version)
    log(f"📦 Version bump: {current_version} -> {new_version}")

    commits = get_recent_commits()
    if commits:
        log("\n📝 Recent commits since last tag:", "\033[93m")
        print(commits)

    log("\n--- Generate Changelog ---", "\033[96m")
    
    def get_items(category):
        items = []
        log(f"Enter {category} (empty line to finish):", "\033[95m")
        while True:
            item = input("> ").strip()
            if not item: break
            items.append(item)
        return items

    added = get_items("New Features")
    fixed = get_items("Bug Fixes")
    improved = get_items("Improvements/Refactoring")

    if not (added or fixed or improved):
        log("⚠️ No changes entered. Proceeding with simple version bump and commit.", "\033[93m")

    log("\n💾 Updating files...", "\033[94m")
    update_file(CONSTANTS_PATH, r'APP_VERSION = "[^"]+"', f'APP_VERSION = "{new_version}"')
    update_file(README_PATH, r'# Picoripi v[\d\.]+', f'# Picoripi v{new_version}')
    release_body = update_changelog(new_version, added, fixed, improved)

    log("🔧 Git operations...", "\033[94m")
    run_command("git add .")
    run_command(f'git commit -m "Release v{new_version}"')
    run_command(f'git tag -a v{new_version} -m "Release v{new_version}"')

    confirm = input("\nPush to GitHub? (y/n): ").lower()
    if confirm == 'y':
        log("📤 Pushing to GitHub...", "\033[94m")
        run_command("git push")
        run_command("git push --tags")

        with open('release_notes.tmp', 'w', encoding='utf-8') as f:
            f.write(release_body)
        
        release_cmd = f'gh release create v{new_version} -F release_notes.tmp --title "v{new_version}"'
        if run_command(release_cmd):
            log(f"✨ GitHub Release v{new_version} created!", "\033[92m")
        else:
            log("🚫 'gh' CLI not found or failed. Please create release manually.", "\033[93m")
        
        if os.path.exists('release_notes.tmp'):
            os.remove('release_notes.tmp')
    else:
        log("⚠️ Changes committed and tagged locally, but not pushed.", "\033[93m")

    log(f"\n✅ Deployment v{new_version} finished!", "\033[1;92m")

if __name__ == "__main__":
    try:
        deploy()
    except KeyboardInterrupt:
        log("\n❌ Deployment cancelled by user.", "\033[91m")
    except Exception as e:
        log(f"\n💥 Critical error: {e}", "\033[91m")
