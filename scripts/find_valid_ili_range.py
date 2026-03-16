#!/usr/bin/env python3
import wn
import random

# Collect all ILI numbers
ili_nums = []
for ss in wn.synsets():
    ili = ss.ili
    if ili:
        try:
            ili_str = str(ili)
            if ili_str.startswith('i') and len(ili_str) > 1:
                ili_num = int(ili_str[1:])
                ili_nums.append(ili_num)
        except:
            pass

print(f'Total synsets with ILI: {len(ili_nums)}')
print(f'ILI range: {min(ili_nums)} to {max(ili_nums)}')

# Check what's already generated
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

print(f'Already generated: {len(existing)}')

# Find unprocessed ILIs
available = [i for i in ili_nums if i not in existing]
print(f'Available: {len(available)}')

# Pick a random one
if available:
    chosen = random.choice(available)
    print(f'\nRandom choice: ILI {chosen}')
    
    # Show details
    synset = wn.synset(f'i{chosen}')
    print(f'POS: {synset.pos}')
    print(f'Lemmas: {[w.title() for w in synset.words()]}')
    print(f'Definition: {synset.definition()}')
    
    # Show hypernyms
    for h in synset.hypernyms():
        print(f'  Hypernym: {[w.title() for w in h.words()]} - {h.definition()}')
    
    # Show hyponyms
    for h in synset.hyponyms()[:5]:
        print(f'  Hyponym: {[w.title() for w in h.words()]} - {h.definition()}')
    
    # Examples
    for ex in synset.examples():
        print(f'  Example: {ex}')
else:
    print('No unprocessed ILIs available!')
