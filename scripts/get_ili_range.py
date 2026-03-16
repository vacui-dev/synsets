#!/usr/bin/env python3
"""Get actual ILI range in the wordnet database"""
import wn

synsets = list(wn.synsets(lexicon='ewn:2020'))
print(f'Total synsets: {len(synsets)}')

ilis = []
for synset in synsets:
    if synset.ili:
        ili_str = str(synset.ili)
        # ILI format is ILI('iXXXXX')
        import re
        match = re.search(r"i(\d+)", ili_str)
        if match:
            num = int(match.group(1))
            ilis.append(num)

ilis.sort()
print(f'Total ILIs: {len(ilis)}')
if ilis:
    print(f'Min ILI: i{min(ilis)}')
    print(f'Max ILI: i{max(ilis)}')
    print(f'\nFirst 20 ILIs: i{ilis[0]} to i{ilis[19]}')
    print(f'Last 20 ILIs: i{ilis[-20]} to i{ilis[-1]}')
