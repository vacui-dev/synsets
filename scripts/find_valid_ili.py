#!/usr/bin/env python3
import wn
import random
import os

# Collect all synset IDs and their ILIs
all_synsets = list(wn.synsets())
print(f'Total synsets: {len(all_synsets)}')

# Check what's already generated
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

# The ewn:2020 uses its own IDs (ewn-00001740-n) but we need to find ones 
# that correspond to the ILI numbering used by the project.
# Let's check how the project stores ILI - look at an existing synset
sample_dir = os.path.join(data_dir, "ili_1")
if os.path.exists(sample_dir):
    for root, dirs, files in os.walk(sample_dir):
        for f in files[:5]:
            fp = os.path.join(root, f)
            print(f'  Sample file: {fp}')
            with open(fp) as fh:
                content = fh.read()[:200]
                print(f'    Content: {content}')
else:
    # Check what exists
    dirs = [d for d in os.listdir(data_dir) if d.startswith("ili_")] if os.path.exists(data_dir) else []
    print(f'Existing dirs: {dirs[:10]}')
    if dirs:
        sample = os.path.join(data_dir, dirs[0])
        for root, _, files in os.walk(sample):
            for f in files[:5]:
                fp = os.path.join(root, f)
                print(f'  Sample: {fp}')
                with open(fp) as fh:
                    print(f'    {fh.read()[:300]}')

# Try a different approach - pick a synset by word and use its ID
print('\n--- Finding valid ILIs via synset IDs ---')
# Show first 5 synsets with their details
for i, ss in enumerate(all_synsets[:5]):
    words = ss.words()
    word_str = ', '.join(w.lemma() for w in words)
    print(f'{ss.id} [{ss.pos}] = "{word_str}" | ili={ss.ili}')
    print(f'  Def: {ss.definition()[:80]}')
    hyps = ss.hypernyms()
    if hyps:
        print(f'  Hypernyms: {[", ".join(w.lemma() for w in h.words()) for h in hyps[:3]]}')
