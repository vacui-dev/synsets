#!/usr/bin/env python3
import wn

# Look up ILI 15217
try:
    synset = wn.synset('i15217')
    print(f'ILI: {synset.ili}')
    print(f'POS: {synset.pos}')
    print(f'Lemmas: {[l.title() for l in synset.words()]}')
    print(f'Definition: {synset.definition()}')
    
    # Hypernyms
    for h in synset.hypernyms():
        hw = h.words()
        print(f'  Hypernym: {[w.title() for w in hw]} - {h.definition()}')
    
    # Hyponyms
    for h in synset.hyponyms()[:5]:
        hw = h.words()
        print(f'  Hyponym: {[w.title() for w in hw]} - {h.definition()}')
    
    # Examples
    for ex in synset.examples():
        print(f'  Example: {ex}')
        
except Exception as e:
    print(f'Error: {e}')
    
    # Try to find it by scanning
    print('\nSearching for ILI 15217...')
    count = 0
    for ss in wn.synsets():
        ili = ss.ili
        if ili and str(ili) == 'i15217':
            print(f'Found! {ss.id()} - {[w.title() for w in ss.words()]}')
            print(f'Definition: {ss.definition()}')
            break
        count += 1
        if count % 100000 == 0:
            print(f'  Scanned {count} synsets...')
    else:
        print(f'ILI 15217 not found after scanning {count} synsets')
