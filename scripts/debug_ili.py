#!/usr/bin/env python3
import wn

# Check the existing examples
try:
    ili_36750 = wn.synset('i36750')
    print('ILI 36750:')
    print('  Definition:', ili_36750.definition())
    print('  Lemmas:', ili_36750.lemmas())
    print('  POS:', ili_36750.pos)

    # Check the hypernym
    print('\nHypernyms:')
    for h in ili_36750.hypernyms():
        print('  ', h.ili, h.definition()[:60])
except Exception as e:
    print(f'Error with i36750: {e}')

# Let's search for "bubble bath"
print('\nSearching for bubble bath:')
for sense in wn.senses('bubble_bath', lang='en'):
    ss = sense.synset()
    print(f'  Found: {ss.ili} - {ss.definition()}')

print('\nSearching for bubble bath (without underscore):')
for sense in wn.senses('bubble', lang='en'):
    ss = sense.synset()
    if 'bath' in ss.definition().lower():
        print(f'  Found: {ss.ili} - {ss.definition()}')
