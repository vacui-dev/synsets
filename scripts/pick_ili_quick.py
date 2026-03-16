#!/usr/bin/env python3
"""Quick pick of a good ILI from first 5000 synsets."""
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

# Sample from first 5000 synsets
all_synsets = list(wn.synsets())[:5000]
random.shuffle(all_synsets)

for ss in all_synsets[:50]:
    ili = ss.ili
    if not ili:
        continue
    try:
        num = int(str(ili).replace("ILI('i", "").replace("')", ""))
    except:
        continue
    if num in existing:
        continue
    
    defn = ss.definition()
    if not defn or len(defn) < 30:
        continue
    
    words = [w.lemma() for w in ss.words()]
    hyps = ss.hypernyms()
    hypos = ss.hyponyms()
    
    # Want something with hypernyms (context) and hyponyms (specificity)
    if len(hyps) > 0 and len(defn) > 40:
        print(f'=== ILI {num} [{ss.pos}] ===')
        print(f'Words: {words}')
        print(f'Definition: {defn}')
        print(f'Hypernyms: {[[w.lemma() for w in h.words()] for h in hyps[:3]]}')
        print(f'Hyponyms: {[[w.lemma() for w in h.words()] for h in hypos[:5]]}')
        for ex in ss.examples():
            print(f'Example: {ex}')
        print(f'USE_ILI={num}')
        break
