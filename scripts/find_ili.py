#!/usr/bin/env python3
import wn

# Find the range of valid ILIs
ili_nums = []
for synset in wn.synsets():
    ili = synset.ili
    if ili:
        try:
            ili_str = str(ili)
            if ili_str.startswith('i') and len(ili_str) > 1:
                ili_num = int(ili_str[1:])
                ili_nums.append(ili_num)
        except:
            pass

if ili_nums:
    print(f"ILI range: {min(ili_nums)} to {max(ili_nums)}")
    print(f"Total synsets with ILI: {len(ili_nums)}")
    
    # Check if 3856 exists
    if 3856 in ili_nums:
        print("ILI 3856 exists!")
        synset = wn.synset(f'i3856')
        print(f"Definition: {synset.definition()}")
    else:
        print(f"\nILI 3856 does not exist in this WordNet")
        print(f"Nearest ILIs:")
        sorted_ilis = sorted(ili_nums)
        for il in sorted_ilis[:20]:
            print(f"  {il}")
