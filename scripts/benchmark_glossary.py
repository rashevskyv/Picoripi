import time
import re
from typing import List

# Fake data
lines = [
    "You got the Master{Color:Red} Sword!",
    "This is a test line with no glossary match.",
    "Be careful, the Tri-Force is dangerous.",
    "Hero of Time, please save us!",
    "I have 100 Rupees in my wallet."
] * 1000  # 5000 lines

terms = [
    "Master Sword", "Tri-Force", "Hero of Time", "Rupee", "Zelda", "Ganon", "Hyrule", "Potion", "Bow", "Arrow"
] * 10 # 100 terms

compiled_patterns = []
separator_pattern = r"(?:\s+|[\u2028\u2029\u200B\u200C\u200D]|<[^>]+>|\{[^}]+\}|\[[^\]]+\])+"

for term in terms:
    parts = [re.escape(p) for p in re.split(r'\s+', term) if p]
    pattern_body = separator_pattern.join(parts)
    prefix = r'(?<!\w)' if term[0].isalnum() else ''
    suffix = r'(?!\w)' if term[-1].isalnum() else ''
    compiled_patterns.append((term, re.compile(f"{prefix}{pattern_body}{suffix}", re.IGNORECASE)))

def baseline():
    count = 0
    for line in lines:
        for term, pattern in compiled_patterns:
            for match in pattern.finditer(line):
                count += 1
    return count

def pre_filter_regex():
    # Only run regex if first word matches
    # Extract first words
    first_words = {}
    for term, pattern in compiled_patterns:
        words = re.findall(r'\w+', term)
        if words:
            fw = words[0].lower()
            first_words.setdefault(fw, []).append((term, pattern))
        else:
            first_words.setdefault('', []).append((term, pattern))
            
    word_finder = re.compile(r'\w+')
    
    count = 0
    for line in lines:
        matched_fws = set(m.group(0).lower() for m in word_finder.finditer(line))
        for fw in matched_fws:
            if fw in first_words:
                for term, pattern in first_words[fw]:
                    for match in pattern.finditer(line):
                        count += 1
        # Also run non-word terms
        if '' in first_words:
            for term, pattern in first_words['']:
                for match in pattern.finditer(line):
                    count += 1
    return count

# Method 3: Mega Regex
def mega_regex():    
    # regex supports 100 groups in older CPython, but we don't need groups if we just pre-filter!
    count = 0
    
    # Just a giant OR regex to check IF the line contains ANY term's basic text?
    # No, tags make it hard.
    return 0

t0 = time.time()
r1 = baseline()
t1 = time.time()
print(f"Baseline: {t1-t0:.4f}s, matches: {r1}")

t0 = time.time()
r2 = pre_filter_regex()
t1 = time.time()
print(f"First-word Regex: {t1-t0:.4f}s, matches: {r2}")
