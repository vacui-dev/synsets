#!/usr/bin/env python3
"""Full research for ILI 44214 (monitor lizard)."""
import wn

ss = wn.synset('i44214')
print(f'=== ILI 44214 ===')
print(f'ID: {ss.id}')
print(f'POS: {ss.pos}')
print(f'Words: {[w.lemma() for w in ss.words()]}')
print(f'Definition: {ss.definition()}')
print()

print('Examples:')
for ex in ss.examples():
    print(f'  {ex}')

print('\nHypernyms:')
for h in ss.hypernyms():
    hw = [w.lemma() for w in h.words()]
    print(f'  {hw} — {h.definition()}')
    # Go one level up
    for hh in h.hypernyms():
        hhw = [w.lemma() for w in hh.words()]
        print(f'    {hhw} — {hh.definition()}')

print('\nHyponyms:')
for h in ss.hyponyms():
    hw = [w.lemma() for w in h.words()]
    print(f'  {hw} — {h.definition()}')

print('\nMeronyms:')
for m in ss.meronyms():
    mw = [w.lemma() for w in m.words()]
    print(f'  {mw} — {m.definition()}')

print('\nHolonyms:')
for h in ss.holonyms():
    hw = [w.lemma() for w in h.words()]
    print(f'  {hw} — {h.definition()}')

print('\nRelations:')
for rel_name, rel_synsets in ss.relations().items():
    for rs in rel_synsets:
        rw = [w.lemma() for w in rs.words()]
        print(f'  {rel_name}: {rw} — {rs.definition()[:80]}')

# Also check related senses for key words
print('\n=== Related synsets for "monitor" ===')
for related in wn.synsets('monitor', pos='n')[:8]:
    ili = related.ili
    ili_num = str(ili).replace("ILI('i", "").replace("')", "") if ili else "?"
    print(f'  i{ili_num}: {[w.lemma() for w in related.words()]} — {related.definition()[:80]}')

print('\n=== Related synsets for "lizard" ===')
for related in wn.synsets('lizard', pos='n')[:5]:
    ili = related.ili
    ili_num = str(ili).replace("ILI('i", "").replace("')", "") if ili else "?"
    print(f'  i{ili_num}: {[w.lemma() for w in related.words()]} — {related.definition()[:80]}')
