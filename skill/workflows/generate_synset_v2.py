#!/usr/bin/env python3
"""
Synset Generation Driver v2 - Multilingual Aligned Edition

Usage:
    python generate_synset_v2.py [--ili N]
    
Generates:
    ili_XXXXXX/
      MODEL_NAME/
        def_en.txt          - English definition
        def_zh.txt          - Chinese definition  
        def_en_ili.txt      - English with ILI tokens
        def_zh_ili.txt      - Chinese with ILI tokens
        aligned.txt         - Constrained multilingual (same ILIs, SVO grammar)
      meta.json             - Model info, timestamp, validation results
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from datetime import datetime

# Get model info from Hermes env or config
def get_model_info():
    """Get current model info from Hermes."""
    # Try to get from environment or run hermes config
    try:
        result = subprocess.run(
            ['grep', 'default:', '/home/ubt18/.hermes/config.yaml'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            model = result.stdout.strip().split(':')[-1].strip()
            return model
    except:
        pass
    return "unknown"

def get_next_ili():
    """Get next unprocessed ILI."""
    data_dir = "/home/ubt18/synsets/data/synsets"
    existing = set()
    if os.path.exists(data_dir):
        for d in os.listdir(data_dir):
            if d.startswith("ili_"):
                try:
                    existing.add(int(d.split("_")[1]))
                except:
                    pass
    
    attempts = 0
    while attempts < 1000:
        ili = random.randint(1, 117480)
        if ili not in existing:
            return ili
        attempts += 1
    
    for i in range(1, 117481):
        if i not in existing:
            return i
    return None

def invoke_hermes(ili_num: int, model: str):
    """Invoke Hermes Agent with full multilingual workflow."""
    
    prompt = f"""Generate multilingual synset ILI {ili_num} using model {model}

STRUCTURE: data/synsets/ili_{ili_num}/{model}/

PHASE 1 - RESEARCH:
1. mcp_wordnet_get_synset(ili="i{ili_num}") - get definition, lemmas, relations
2. Explore 2-3 hypernyms/hyponyms for context

PHASE 2 - WRITE INDEPENDENT DEFINITIONS:
Write: {model}/def_en.txt and {model}/def_zh.txt
- Wikipedia quality, 3-5 sentences each
- Natural grammar in each language
- Cover: what, context, usage, relationships

PHASE 3 - ANNOTATE:
Write: {model}/def_en_ili.txt and {model}/def_zh_ili.txt
- Use mcp_wordnet_lookup_word for EVERY content word
- Format: <|ILI_NNNNNN|>word
- Skip function words

PHASE 4 - ALIGNMENT PASS (CRITICAL):
Compare def_en_ili.txt and def_zh_ili.txt:
- Count ILI occurrences in each
- If counts differ: REVISE to match

Write: {model}/aligned.txt
- Constrained SVO grammar (Subject-Verb-Object)
- Same ILI IDs appear in same positions
- Grammatically correct but slightly awkward
- Both EN and CZ readable
- Example: "<|ILI_12345|>cat <|ILI_67890|>chase <|ILI_11111|>mouse"

PHASE 5 - METADATA:
Write: meta.json
{{"ili": {ili_num}, "model": "{model}", "timestamp": "ISO8601", 
  "en_word_count": N, "zh_word_count": N, "aligned_ili_count": N,
  "validation": "passed|failed", "notes": "..."}}

RULES:
- 200 tool call budget
- EN and CZ must have EXACT same ILI set
- Use constrained SVO for alignment
- Commit when done

Start with research."""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(prompt)
        prompt_file = f.name
    
    try:
        result = subprocess.run(
            ['python3', '-m', 'hermes', 'agent', '--prompt-file', prompt_file, 
             '--max-turns', '200', '--model', model],
            capture_output=True,
            text=True,
            timeout=300
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr, file=sys.stderr)
        return result.returncode == 0
    finally:
        os.unlink(prompt_file)

def validate_alignment(ili_num: int, model: str) -> dict:
    """Validate that EN and CZ have same ILIs."""
    base_dir = f"/home/ubt18/synsets/data/synsets/ili_{ili_num}/{model}"
    
    def extract_ilis(filepath):
        if not os.path.exists(filepath):
            return []
        with open(filepath) as f:
            content = f.read()
        return re.findall(r'<\|ILI_(\d+)\|>', content)
    
    enilis = extract_ilis(f"{base_dir}/def_en_ili.txt")
    zh_ilis = extract_ilis(f"{base_dir}/def_zh_ili.txt")
    
    en_set = set(enilis)
    zh_set = set(zh_ilis)
    
    return {
        "en_ili_count": len(enilis),
        "zh_ili_count": len(zh_ilis),
        "en_unique": len(en_set),
        "zh_unique": len(zh_set),
        "common": len(en_set & zh_set),
        "en_only": list(en_set - zh_set),
        "zh_only": list(zh_set - en_set),
        "aligned": en_set == zh_set and len(enilis) == len(zh_ilis)
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ili', type=int, help='Specific ILI')
    parser.add_argument('--model', help='Model override')
    args = parser.parse_args()
    
    model = args.model or get_model_info()
    
    if args.ili:
        ili = args.ili
    else:
        ili = get_next_ili()
    
    if not ili:
        print("All ILIs processed!")
        return
    
    print(f"Processing ILI {ili} with model {model}")
    
    success = invoke_hermes(ili, model)
    
    if success:
        # Validate
        validation = validate_alignment(ili, model)
        print(f"Validation: {validation}")
        
        # Update meta.json with validation
        meta_path = f"/home/ubt18/synsets/data/synsets/ili_{ili}/meta.json"
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            meta["validation"] = validation
            with open(meta_path, 'w') as f:
                json.dump(meta, f, indent=2)
        
        # Commit
        subprocess.run([
            'git', '-C', '/home/ubt18/synsets', 
            'add', f'data/synsets/ili_{ili}/'
        ])
        subprocess.run([
            'git', '-C', '/home/ubt18/synsets',
            'commit', '-m', f'Add synset ILI {ili} [{model}]'
        ])
        
        print(f"✓ Completed ILI {ili}")
    else:
        print(f"✗ Failed ILI {ili}")

if __name__ == "__main__":
    main()
