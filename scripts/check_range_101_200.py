#!/usr/bin/env python3
"""Check ILIs 101-200"""
import wn
import re

synsets = list(wn.synsets(lexicon='ewn:2020'))

# Build lookup
ili_lookup = {}
for synset in synsets:
    if synset.ili:
        ili_str = str(synset.ili)
        match = re.search(r"i(\d+)", ili_str)
        if match:
            num = int(match.group(1))
            ili_lookup[num] = synset

# Check 101-200
print(f'Checking ILIs 101-200...')
found = []
for num in range(101, 201):
    if num in ili_lookup:
        synset = ili_lookup[num]
        found.append((num, synset.lemmas(), synset.definition()))

print(f'Found {len(found)} ILIs in range 101-200')
for f in found[:10]:
    print(f'  i{f[0]}: {f[1][:3] if f[1] else []} - {f[2][:60] if f[2] else ""}...')

if len(found) > 10:
    print(f'  ... and {len(found)-10} more')
