#!/usr/bin/env python3
"""Pick a random unprocessed ILI from ewn:2020."""
import wn
import random
import os

# Already generated
data_dir = "/home/ubt18/synsets/data/synsets"
existing = set()
if os.path.exists(data_dir):
    for d in os.listdir(data_dir):
        if d.startswith("ili_"):
            try:
                existing.add(int(d.split("_")[1]))
            except:
                pass

# Collect all valid ILIs from ewn:2020
valid_ilis = []
for ss in wn.synsets():
    ili = ss.ili
    if ili:
        ili_str = str(ili)  # "ILI('i66397')"
        # Extract the number
        try:
            num = int(ili_str.replace("ILI('i", "").replace("')", ""))
            if num not in existing:
                valid_ilis.append((num, ss))
        except:
            pass

print(f'Valid unprocessed ILIs: {len(valid_ilis)}')
print(f'Already processed: {len(existing)}')

# Pick random one
num, ss = random.choice(valid_ilis)
words = [w.lemma() for w in ss.words()]
print(f'\n=== ILI {num} ===')
print(f'ID: {ss.id}')
print(f'POS: {ss.pos}')
print(f'Words: {words}')
print(f'Definition: {ss.definition()}')

# Full context
for h in ss.hypernyms():
    hw = [w.lemma() for w in h.words()]
    print(f'  Hypernym: {hw} — {h.definition()[:80]}')

for h in ss.hyponyms()[:5]:
    hw = [w.lemma() for w in h.words()]
    print(f'  Hyponym: {hw} — {h.definition()[:80]}')

for ex in ss.examples():
    print(f'  Example: {ex}')

# Also check relations
for rel_name, rel_synsets in ss.relations().items():
    for rs in rel_synsets[:2]:
        rw = [w.lemma() for w in rs.words()]
        print(f'  {rel_name}: {rw}')

# Print the ILI number for the script to use
print(f'\nUSE_ILI={num}')
