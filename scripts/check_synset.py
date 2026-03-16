#!/usr/bin/env python3
import wn

# Get the English WordNet lexicon
en_lexicons = list(wn.lexicons(lang='en'))
en = en_lexicons[0]

# Try to find synset with ILI i27833
synsets = list(wn.synsets(lexicon=en.id))

# Print first few synsets to see their structure
print("First 10 synsets:")
for ss in synsets[:10]:
    print(f"  ID: {ss.id}")
    print(f"  ILI: {ss.ili}")
    print(f"  POS: {ss.pos}")
    print(f"  Lemmas: {ss.lemmas()}")
    print(f"  Definition: {ss.definition()[:80]}...")
    print()

# Check if there's a way to access ILI
print("Checking synset attributes:")
ss = synsets[0]
print(f"dir(ss): {[a for a in dir(ss) if not a.startswith('_')]}")
print(f"ili attribute: {ss.ili}")
print(f"ili type: {type(ss.ili)}")
