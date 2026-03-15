#!/usr/bin/env python3
"""
Synset Generation Driver v3 - Multilingual Grammar-Preserving Edition

Creates properly aligned multilingual synset data with:
- Natural grammar preserved in all languages
- Function words/particles untagged
- ILI sequence identical across languages

Usage:
    python generate_synset_v3.py [--ili N] [--langs en,cz,ja]
"""

import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
from datetime import datetime

LANGUAGES = ['en', 'cz', 'ja']  # Expandable

def get_model_info():
    """Get current model from Hermes config."""
    try:
        result = subprocess.run(
            ['grep', 'default:', '/home/ubt18/.hermes/config.yaml'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip().split(':')[-1].strip()
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

def invoke_hermes(ili_num: int, model: str, langs: list):
    """Invoke Hermes with full multilingual grammar-preserving workflow."""
    
    lang_list = ','.join(langs)
    
    prompt = f"""Generate multilingual synset ILI {ili_num} with model {model}

OUTPUT STRUCTURE: data/synsets/ili_{ili_num}/
  {model}/
    natural/      # Wikipedia quality, proper grammar
      en.txt
      cz.txt  
      ja.txt
    ili/          # ILI annotations (function words untagged)
      en.txt
      cz.txt
      ja.txt      # Particles bare: は、を、が
    merged/       # Grammar-correct, ILI-aligned (CRITICAL)
      en.txt      # Same ILI sequence as ja.txt
      cz.txt      # Same ILI sequence as ja.txt
      ja.txt      # Same ILI sequence as en.txt
  meta.json       # Model, timestamp, validation

PHASE 1 - RESEARCH:
1. mcp_wordnet_get_synset(ili="i{ili_num}")
2. Explore 2-3 related synsets (hypernyms/hyponyms)

PHASE 2 - WRITE NATURAL:
For each language in {lang_list}:
  Write natural/{{lang}}.txt
  - Wikipedia quality definition
  - Proper grammar for that language
  - 3-5 sentences
  - Cover: what, context, relationships

PHASE 3 - ANNOTATE:
For each language in {lang_list}:
  Write ili/{{lang}}.txt
  - Tag EVERY content word with ILI
  - Format: <|ILI_NNNNN|>word
  - DO NOT tag function words:
    * EN: the, a, an, is, of, in, and, or, to, etc.
    * CZ: 的，了，在，和，或，等
    * JA: は、を、が、に、で、と、等

PHASE 4 - MERGE (CRITICAL CONSTRAINT):
Write merged/{{lang}}.txt for each language:

CONSTRAINTS:
1. All languages MUST have EXACT same ILI sequence
2. Grammar must be correct (not stubbed)
3. Preserve: tense, quantity, gender where applicable
4. Function words untagged
5. Japanese particles untagged

EXAMPLE of correct merged/ structure:

merged/en.txt:
<|ILI_73081|>Thraco-Phrygian <|ILI_025997|>was proposed as an 
<|ILI_005091|>extinct <|ILI_081247|>branch of the ...

merged/ja.txt:
<|ILI_73081|>トラキア・フリギア語族は<|ILI_025997|>提案された
<|ILI_005091|>死滅した<|ILI_081247|>分枝で、...

Both have SAME ILI count (15 each) and SAME ILI order.

PHASE 5 - VALIDATE:
Run: python /home/ubt18/synsets/skill/scripts/verify_alignment.py data/synsets/ili_{ili_num}

If validation fails, revise merged/ files until aligned.

PHASE 6 - METADATA:
Write meta.json with:
- ili: {ili_num}
- model: "{model}"
- timestamp: ISO8601
- languages: {langs}
- ilis_per_lang: {{"en": N, "cz": N, "ja": N}}
- alignment_verified: true/false

RULES:
- 250 tool call budget
- Grammar must be NATURAL, not SVO-stubbed
- Function words stay untagged
- ILI sequence must match across all languages
- Validation must pass before commit

Start with research."""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(prompt)
        prompt_file = f.name
    
    try:
        result = subprocess.run(
            ['python3', '-m', 'hermes', 'agent', '--prompt-file', prompt_file,
             '--max-turns', '250'],
            capture_output=True,
            text=True,
            timeout=600
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr, file=sys.stderr)
        return result.returncode == 0
    finally:
        os.unlink(prompt_file)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ili', type=int, help='Specific ILI')
    parser.add_argument('--langs', default='en,cz,ja', help='Languages (comma-separated)')
    parser.add_argument('--model', help='Model override')
    args = parser.parse_args()
    
    model = args.model or get_model_info()
    langs = args.langs.split(',')
    
    if args.ili:
        ili = args.ili
    else:
        ili = get_next_ili()
    
    if not ili:
        print("All ILIs processed!")
        return
    
    print(f"Processing ILI {ili} with model {model}, languages: {langs}")
    
    success = invoke_hermes(ili, model, langs)
    
    if success:
        # Validate
        ili_dir = f"/home/ubt18/synsets/data/synsets/ili_{ili}"
        result = subprocess.run(
            ['python3', '/home/ubt18/synsets/skill/scripts/verify_alignment.py', ili_dir],
            capture_output=True, text=True
        )
        print(result.stdout)
        
        if result.returncode == 0:
            # Commit
            subprocess.run(['git', '-C', '/home/ubt18/synsets', 'add', ili_dir])
            subprocess.run(['git', '-C', '/home/ubt18/synsets', 'commit', '-m',
                          f'Add synset ILI {ili} [{model}] v3'])
            print(f"✓ Completed ILI {ili}")
        else:
            print(f"⚠ ILI {ili} needs alignment fixes")
    else:
        print(f"✗ Failed ILI {ili}")

if __name__ == "__main__":
    main()
