#!/usr/bin/env python3
import wn

# Get synset by ILI
ili_id = 'i3856'
try:
    synset = wn.synset(ili_id)
    print('ILI:', ili_id)
    print('POS:', synset.pos)
    print('Definition:', synset.definition())
    print('Lemmas:', synset.lemmas())
    print('Hypernyms:', [(h.id, h.definition()[:60]) for h in synset.hypernyms()])
    print('Hyponyms:', [(h.id, h.definition()[:60]) for h in synset.hyponyms()[:5]])
except Exception as e:
    print(f'Error: {e}')
