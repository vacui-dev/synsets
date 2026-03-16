#!/usr/bin/env python3
"""Find ILI numbers for key concepts in the monitor lizard synset."""
import wn

targets = [
    'lizard', 'reptile', 'crocodile', 'Komodo dragon', 'carnivore',
    'tropical', 'predator', 'reptilian', 'saurian', 'Varanus',
    'Africa', 'Asia', 'Australia', 'egg', 'insect', 'mammal',
    'tail', 'limb', 'warn', 'prehensile', 'species',
    'genus', 'family', 'vertebrate', 'cold-blooded',
    'African monitor', 'dragon', 'elapid', 'varanid',
    'vertebrate', 'diapsid', 'hunting', 'intelligence'
]

for target in targets:
    results = wn.synsets(target)[:3]
    for r in results:
        ili = r.ili
        ili_num = str(ili).replace("ILI('i", "").replace("')", "") if ili else "?"
        words = [w.lemma() for w in r.words()]
        defn = r.definition()[:80]
        print(f'i{ili_num}: {words} — {defn}')
    if not results:
        print(f'--- "{target}" not found ---')
