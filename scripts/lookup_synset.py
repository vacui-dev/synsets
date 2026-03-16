#!/usr/bin/env python3
import wn

# Get the English WordNet lexicon
en_lexicons = list(wn.lexicons(lang='en'))
print(f"Found {len(en_lexicons)} English lexicons")

if not en_lexicons:
    print("No English lexicon found!")
    exit(1)

en = en_lexicons[0]
print(f"Using lexicon: {en.id}")

# Try to find synset with ILI i27833
synsets = list(wn.synsets(lexicon=en.id))
print(f"Total synsets: {len(synsets)}")

# Find the synset with ILI i27833
target = 'i27833'
found = False
for ss in synsets:
    if ss.ili == target:
        print(f"\nFound synset with ILI {target}!")
        print(f"  ID: {ss.id}")
        print(f"  POS: {ss.pos}")
        print(f"  Lemmas: {ss.lemmas()}")
        print(f"  Definition: {ss.definition()}")
        print(f"  Examples: {ss.examples()}")
        found = True
        break

if not found:
    print(f"\nSynset with ILI {target} not found")
    
    # Collect all ILIs
    ilis = []
    for ss in synsets:
        if ss.ili:
            try:
                ilis.append(int(ss.ili[1:]))
            except:
                pass
    
    ilis.sort()
    print(f"Total synsets with ILI: {len(ilis)}")
    print(f"Min ILI: {ilis[0] if ilis else 'N/A'}")
    print(f"Max ILI: {ilis[-1] if ilis else 'N/A'}")
    
    # Check range
    target_num = 27833
    if ilis:
        lower = [i for i in ilis if i < target_num]
        upper = [i for i in ilis if i > target_num]
        if lower:
            print(f"Closest lower ILI: {lower[-1]}")
        if upper:
            print(f"Closest upper ILI: {upper[0]}")
