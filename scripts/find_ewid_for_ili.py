#!/usr/bin/env python3
"""Find ewn synset for ILI 44214."""
import wn

target_ili = "i44214"

for ss in wn.synsets():
    ili = ss.ili
    if ili and str(ili) == target_ili:
        print(f'Found! ID: {ss.id}')
        print(f'POS: {ss.pos}')
        print(f'Words: {[w.lemma() for w in ss.words()]}')
        print(f'Definition: {ss.definition()}')
        
        print('\nHypernyms:')
        for h in ss.hypernyms():
            hw = [w.lemma() for w in h.words()]
            print(f'  {hw} — {h.definition()}')
            for hh in h.hypernyms():
                hhw = [w.lemma() for w in hh.words()]
                print(f'    {hhw} — {hh.definition()}')
        
        print('\nHyponyms:')
        for h in ss.hyponyms():
            hw = [w.lemma() for w in h.words()]
            print(f'  {hw} — {h.definition()}')
        
        print('\nHolonyms:')
        for h in ss.holonyms():
            hw = [w.lemma() for w in h.words()]
            print(f'  {hw} — {h.definition()}')
        
        print('\nRelations:')
        for rel_name, rel_synsets in ss.relations().items():
            for rs in rel_synsets[:3]:
                rw = [w.lemma() for w in rs.words()]
                print(f'  {rel_name}: {rw} — {rs.definition()[:80]}')
        
        print('\nExamples:')
        for ex in ss.examples():
            print(f'  {ex}')
        
        print(f'\nEWN_ID={ss.id}')
        break
else:
    print(f'ILI {target_ili} not found!')
    # Search nearby
    print('Searching...')
    count = 0
    for ss in wn.synsets():
        ili = ss.ili
        if ili:
            s = str(ili)
            if 'i44' in s:
                print(f'  Near match: {s} -> {ss.id} {[w.lemma() for w in ss.words()]}')
                count += 1
                if count > 10:
                    break
