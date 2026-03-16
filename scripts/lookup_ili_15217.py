#!/usr/bin/env python3
import nltk
nltk.data.path.append('/home/ubt18/nltk_data')
from nltk.corpus import wordnet as wn

# ILI 15217 - try as synset offset
for pos in ['n', 'v', 'a', 'r']:
    try:
        synset = wn.synset_from_pos_and_offset(pos, 15217)
        print(f'Found as {pos}: {synset.name()}')
        print(f'Definition: {synset.definition()}')
        print(f'Lemmas: {[l.name() for l in synset.lemmas()]}')
        for h in synset.hypernyms():
            print(f'  Hypernym: {h.name()} - {h.definition()}')
        for h in synset.hyponyms()[:5]:
            print(f'  Hyponym: {h.name()} - {h.definition()}')
        for h in synset.part_meronyms()[:3]:
            print(f'  Meronym: {h.name()} - {h.definition()}')
        for h in synset.part_holonyms()[:3]:
            print(f'  Holonym: {h.name()} - {h.definition()}')
        break
    except Exception as e:
        pass
else:
    print('Not found as direct offset')
    # Try OMW ili map
    import json, zipfile, os
    omw_path = '/home/ubt18/nltk_data/corpora/omw-1.4.zip'
    if os.path.exists(omw_path):
        with zipfile.ZipFile(omw_path) as z:
            print('OMW files:', [n for n in z.namelist()[:30]])
            for name in z.namelist():
                if 'ili' in name.lower() or 'map' in name.lower():
                    print(f'  Candidate: {name}')
