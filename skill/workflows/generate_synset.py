#!/usr/bin/env python3
"""
Synset Generation Driver - Invokes Hermes Agent for single synset completion

Usage:
    python generate_synset.py <ili_number>
    
This script:
1. Picks an ILI (or uses provided)
2. Invokes Hermes Agent with isolated context
3. Hermes generates complete synset (EN + CZ + annotation)
4. Saves all 4 files
5. Exits cleanly
"""

import argparse
import json
import os
import random
import subprocess
import sys
import tempfile

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
    
    # Pick random from 1-117480 that's not done
    attempts = 0
    while attempts < 1000:
        ili = random.randint(1, 117480)
        if ili not in existing:
            return ili
        attempts += 1
    
    # Fallback: find any gap
    for i in range(1, 117481):
        if i not in existing:
            return i
    return None

def invoke_hermes(ili_num: int):
    """Invoke Hermes Agent to generate one complete synset."""
    
    prompt = f"""Generate complete synset data for ILI i{ili_num}

MISSION: Create Wikipedia-quality synset entry with full ILI annotation.

STEPS:
1. RESEARCH: Use mcp_wordnet_get_synset(ili="i{ili_num}") to understand the concept
   - Get definition, lemmas, hypernyms, hyponyms
   - Explore related synsets if needed
   
2. WRITE ENGLISH: Create ili_{ili_num}_def_en.txt
   - Comprehensive Wikipedia-quality definition
   - 3-5 sentences minimum
   - Include context, usage, relationships
   
3. WRITE CHINESE: Create ili_{ili_num}_def_zh.txt  
   - Accurate translation of English
   - Maintain technical precision
   
4. ANNOTATE ENGLISH: Create ili_{ili_num}_def_en_annotated.txt
   - Use mcp_wordnet_lookup_word for EVERY content word
   - Format: <|ILI_NNNNNN|>word
   - Skip: the, a, an, is, of, in, and, or, to, etc.
   
5. ANNOTATE CHINESE: Create ili_{ili_num}_def_zh_annotated.txt
   - Same ILI IDs (language-neutral)
   - Skip Chinese function words

OUTPUT LOCATION: /home/ubt18/synsets/data/synsets/ili_{ili_num}/

RULES:
- You have 200 tool calls available - use them wisely
- Process sentence by sentence
- Write files using write_file tool
- Commit with git when done
- This is ONE synset - complete it fully before exiting

Begin research now with mcp_wordnet_get_synset(ili="i{ili_num}")"""

    # Create temp file for prompt
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(prompt)
        prompt_file = f.name
    
    try:
        # Invoke Hermes Agent
        result = subprocess.run(
            ['python3', '-m', 'hermes', 'agent', '--prompt-file', prompt_file, '--max-turns', '200'],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes max per synset
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr, file=sys.stderr)
        return result.returncode == 0
    finally:
        os.unlink(prompt_file)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ili', type=int, help='Specific ILI number to process')
    parser.add_argument('--count', type=int, default=1, help='Number of synsets to generate')
    args = parser.parse_args()
    
    for i in range(args.count):
        if args.ili:
            ili = args.ili
        else:
            ili = get_next_ili()
        
        if not ili:
            print("All ILIs processed!")
            break
        
        print(f"\n{'='*60}")
        print(f"Processing ILI {ili} ({i+1}/{args.count})")
        print(f"{'='*60}")
        
        success = invoke_hermes(ili)
        if success:
            print(f"✓ Completed ILI {ili}")
        else:
            print(f"✗ Failed ILI {ili}")
            break

if __name__ == "__main__":
    main()
