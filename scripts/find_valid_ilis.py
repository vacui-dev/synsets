#!/usr/bin/env python3
"""Find valid ILIs in the wordnet database"""
import wn

print('Checking lexicons...')
lexicons = wn.lexicons()
print(f'Available lexicons: {lexicons}')

# Collect all ILIs
ilis = []
synsets = list(wn.synsets(lexicon='ewn:2020'))
print(f'Total synsets in ewn:2020: {len(synsets)}')

for synset in synsets[:20]:  # Just check first 20
    print(f'Synset: {synset.id}, ILI: {synset.ili}, Lemmas: {synset.lemmas()[:2] if synset.lemmas() else []}')

# Check if any ILIs match i101-i200 pattern
print('\n--- Checking for ILIs in range 101-200 ---')
for synset in synsets:
    if synset.ili:
        ili_str = str(synset.ili)
        if ili_str.startswith('i'):
            try:
                num = int(ili_str[1:])
                if 101 <= num <= 200:
                    ilis.append((num, ili_str, synset.lemmas(), synset.definition()))
            except:
                pass

print(f'Found {len(ilis)} ILIs in range 101-200')
for ili in ilis[:10]:
    print(ili)
