#!/usr/bin/env python3
import wn

# Ensure WordNet is downloaded
try:
    wn.lexicons(lang='en')
except:
    wn.download('ewn:2020')

# Find synset by ILI
ili_id = 'i27833'
found = False
for lex in wn.lexicons():
    for synset in wn.synsets(lexicon=lex.id):
        if synset.ili == ili_id:
            print(f'ILI: {ili_id}')
            print(f'ID: {synset.id}')
            print(f'POS: {synset.pos}')
            print(f'Lemmas: {synset.lemmas()}')
            print(f'Definition: {synset.definition()}')
            print(f'Examples: {synset.examples()}')
            found = True
            break
    if found:
        break

if not found:
    # Try another method - search by synset ID
    print(f'Synset with ILI {ili_id} not found directly. Trying to find by ili number...')
    # Try getting synset directly
    try:
        synset = wn.synset(ili=ili_id)
        print(f'Found via wn.synset(ili={ili_id})')
        print(f'ID: {synset.id}')
        print(f'POS: {synset.pos}')
        print(f'Lemmas: {synset.lemmas()}')
        print(f'Definition: {synset.definition()}')
    except Exception as e:
        print(f'Error: {e}')
