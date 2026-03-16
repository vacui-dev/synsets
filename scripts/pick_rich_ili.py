#!/usr/bin/env python3
"""Pick a rich ILI with many relationships for better definitions."""
import wn
import random
import os

data_dir = "/home/ubt18/synsets/data/synsets"
existing = set()
if os.path.exists(data_dir):
    for d in os.listdir(data_dir):
        if d.startswith("ili_"):
            try:
                existing.add(int(d.split("_")[1]))
            except:
                pass

# Find synsets with rich relationships
candidates = []
for ss in wn.synsets():
    ili = ss.ili
    if not ili:
        continue
    try:
        num = int(str(ili).replace("ILI('i", "").replace("')", ""))
    except:
        continue
    if num in existing:
        continue
    
    # Score by richness
    score = 0
    score += len(ss.hypernyms()) * 2
    score += len(ss.hyponyms())
    score += len(ss.meronyms())
    score += len(ss.holonyms())
    score += len(ss.examples())
    words = ss.words()
    
    # Must have at least 1 word and definition
    if not words or not ss.definition():
        continue
    
    # Skip very short definitions
    if len(ss.definition()) < 20:
        continue
    
    # Skip overly simple synsets (single common words can be ambiguous)
    word_strs = [w.lemma() for w in words]
    
    candidates.append((score, num, ss, word_strs))

candidates.sort(reverse=True)

# Show top 10
print("Top candidates by richness:")
for i, (score, num, ss, words) in enumerate(candidates[:10]):
    print(f'{i+1}. ILI {num} [{ss.pos}] = {words} (score={score})')
    print(f'   Def: {ss.definition()[:100]}')

# Pick the top one
if candidates:
    score, num, ss, words = candidates[0]
    print(f'\n=== SELECTED: ILI {num} ===')
    print(f'Words: {words}')
    print(f'Definition: {ss.definition()}')
    print(f'USE_ILI={num}')
