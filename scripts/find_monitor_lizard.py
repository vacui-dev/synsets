#!/usr/bin/env python3
"""Find monitor lizard synset in ewn:2020."""
import wn

# Search for monitor lizard
for word in ['monitor lizard', 'varan', 'monitor', 'lizard']:
    print(f'\n=== Synsets for "{word}" ===')
    for ss in wn.synsets(word)[:10]:
        ili = ss.ili
        ili_num = str(ili).replace("ILI('i", "").replace("')", "") if ili else "?"
        words = [w.lemma() for w in ss.words()]
        print(f'  {ss.id} | ili=i{ili_num} | {words}')
        print(f'    {ss.definition()[:120]}')
