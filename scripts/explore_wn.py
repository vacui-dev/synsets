#!/usr/bin/env python3
import wn

# Get first 5 synsets - just dump everything
count = 0
for ss in wn.synsets():
    if count >= 5: break
    ili = ss.ili
    words = ss.words()
    word_names = [str(w) for w in words]
    print(f'ID: {ss.id} | ili: {ili} | pos: {ss.pos} | words: {word_names}')
    print(f'  Def: {ss.definition()[:100]}')
    count += 1

total = sum(1 for _ in wn.synsets())
print(f'\nTotal synsets: {total}')
