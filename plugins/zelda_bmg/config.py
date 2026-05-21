import os
import json

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')

PROBLEM_TAG_WARNING = "PROBLEM_TAG_WARNING"
PROBLEM_WIDTH_EXCEEDED = "PROBLEM_WIDTH_EXCEEDED"

PROBLEM_DEFINITIONS = {}
CONTROL_CODES = []

if os.path.exists(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            PROBLEM_DEFINITIONS = config_data.get("PROBLEM_DEFINITIONS", {})
            CONTROL_CODES = config_data.get("CONTROL_CODES", [])
    except Exception as e:
        print(f"Error loading zelda_bmg/config.json: {e}")
