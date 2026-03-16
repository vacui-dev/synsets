#!/usr/bin/env python3
"""Full research for ILI 44214 (monitor lizard)."""
import wn

ss = wn.synset('ewn-01697350-n')
print(f'=== ILI 44214: monitor lizard ===')
print(f'ID: {ss.id}')
print(f'POS: {ss.pos}')
print(f'Definition: {ss.definition()}')

print('\nWords:')
for w in ss.words():
    print(f'  {w.lemma()}')

print('\nExamples:')
for ex in ss.examples():
    print(f'  {ex}')

print('\nHypernyms:')
for h in ss.hypernyms():
    print(f'  {[w.lemma() for w in h.words()]} — {h.definition()}')
    for hh in h.hypernyms():
        print(f'    {[w.lemma() for w in hh.words()]} — {hh.definition()}')

print('\nHyponyms:')
for h in ss.hyponyms():
    print(f'  {[w.lemma() for w in h.words()]} — {h.definition()}')

print('\nHolonyms:')
for h in ss.holonyms():
    print(f'  {[w.lemma() for w in h.words()]} — {h.definition()}')

print('\nMeronyms:')
for m in ss.meronyms():
    print(f'  {[w.lemma() for w in m.words()]} — {m.definition()}')

print('\nRelations:')
for rel_name, rel_synsets in ss.relations().items():
    for rs in rel_synsets[:3]:
        print(f'  {rel_name}: {[w.lemma() for w in rs.words()]} — {rs.definition()[:80]}')

# Also get key related synsets
print('\n=== Related synsets ===')
for lemma in ['lizard', 'reptile', 'Komodo dragon', 'crocodile', 'sauropsid']:
    results = wn.synsets(lemma)[:3]
    if results:
        print(f'\n"{lemma}":')
        for r in results:
            ili = r.ili
            ili_num = str(ili).replace("ILI('i", "").replace("')", "") if ili else "?"
            print(f'  i{ili_num}: {[w.lemma() for w in r.words()]} — {r.definition()[:100]}')

# Also get ancestor chain
print('\n=== Hypernym chain ===')
def print_hypernyms(synset, depth=0):
    for h in synset.hypernyms():
        print(f'  {"  " * depth}{[w.lemma() for w in h.words()]} — {h.definition()[:80]}')
        if depth < 3:
            print_hypernyms(h, depth + 1)
print_hypernyms(ss)
