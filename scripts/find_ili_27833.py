#!/usr/bin/env python3
import wn

# Get the English WordNet lexicon
en_lexicons = list(wn.lexicons(lang='en'))
en = en_lexicons[0]

synsets = list(wn.synsets(lexicon=en.id))
print(f"Total synsets: {len(synsets)}")

# Find synset with ILI i27833
target_ili = 'i27833'
found = None

for ss in synsets:
    if ss.ili and str(ss.ili) == f"ILI('{target_ili}')":
        found = ss
        break

if found:
    print(f"\nFound synset with ILI {target_ili}!")
    print(f"  ID: {found.id}")
    print(f"  POS: {found.pos}")
    print(f"  Lemmas: {found.lemmas()}")
    print(f"  Definition: {found.definition()}")
    print(f"  Examples: {found.examples()}")
else:
    # Extract all ILI numbers
    ilis = []
    for ss in synsets:
        if ss.ili:
            try:
                ili_str = str(ss.ili)  # ILI('i66397')
                num = int(ili_str[6:-2])  # Extract number from ILI('iXXXXX')
                ilis.append(num)
            except:
                pass
    
    ilis.sort()
    print(f"\nSynset with ILI {target_ili} not found")
    print(f"Total synsets with ILI: {len(ilis)}")
    print(f"Min ILI: i{ilis[0]}")
    print(f"Max ILI: i{ilis[-1]}")
    
    target_num = 27833
    if target_num in ilis:
        print(f"ILI i{target_num} IS in the list but wasn't found (bug?)")
    else:
        lower = [i for i in ilis if i < target_num]
        upper = [i for i in ilis if i > target_num]
        print(f"\nTarget i{target_num} is NOT in the available ILI range")
        if lower:
            print(f"Closest lower ILI: i{lower[-1]}")
        if upper:
            print(f"Closest upper ILI: i{upper[0]}")
