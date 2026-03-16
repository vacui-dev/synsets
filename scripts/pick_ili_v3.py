#!/usr/bin/env python3
"""Pick an ILI with rich content for multilingual generation."""
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

# Pick from synsets that have good definitions and relationships
all_synsets = list(wn.synsets())
random.shuffle(all_synsets)

found = []
for ss in all_synsets[:20000]:
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
    if not defn or len(defn) < 50:
        continue
    
    words = [w.lemma() for w in ss.words()]
    
    # Skip very long multi-word entries and very short ones
    if len(words) > 8 or any(len(w) > 30 for w in words):
        continue
    
    hyps = ss.hypernyms()
    hypos = ss.hyponyms()
    
    # Want synsets with both hypernyms (context) and hyponyms (subtypes)
    if len(hyps) >= 1 and len(hypos) >= 2:
        found.append((num, ss, words, hyps, hypos))
    
    if len(found) >= 5:
        break

if not found:
    # Relax criteria
    for ss in all_synsets[:30000]:
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
        words = [w.lemma() for w in ss.words()]
        if defn and len(defn) >= 40 and len(words) <= 8:
            found.append((num, ss, words, ss.hypernyms(), ss.hyponyms()))
            if len(found) >= 3:
                break

for i, (num, ss, words, hyps, hypos) in enumerate(found):
    print(f'\n=== Candidate {i+1}: ILI {num} [{ss.pos}] ===')
    print(f'Words: {words}')
    print(f'Definition: {ss.definition()}')
    print(f'Hypernyms: {[[w.lemma() for w in h.words()] for h in hyps[:3]]}')
    print(f'Hyponyms: {[[w.lemma() for w in h.words()] for h in hypos[:5]]}')
    for ex in ss.examples():
        print(f'Example: {ex}')
    for rel_name, rel_synsets in ss.relations().items():
        for rs in rel_synsets[:2]:
            rw = [w.lemma() for w in rs.words()]
            print(f'  {rel_name}: {rw}')

if found:
    num, ss, words, _, _ = found[0]
    print(f'\n=== USE_ILI={num} ===')
