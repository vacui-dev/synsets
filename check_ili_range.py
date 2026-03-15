#!/usr/bin/env python3
import wn

# Try to find synset with ili around 3856
synsets = list(wn.synsets())
ilis = []
for s in synsets:
    ili = s.ili
    if ili:
        try:
            num = int(str(ili)[1:])
            ilis.append((num, str(ili), s))
        except:
            pass

ilis.sort()
print('First 10 ILIs:', [i[1] for i in ilis[:10]])
print('Last 10 ILIs:', [i[1] for i in ilis[-10:]])
print('Min:', min(i[0] for i in ilis))
print('Max:', max(i[0] for i in ilis))
print('Total:', len(ilis))

# Check if 3856 exists
matches = [i for i in ilis if i[0] == 3856]
if matches:
    for m in matches:
        print(f'Found ILI {m[1]}: {m[2].definition()}')
else:
    print('ILI 3856 not found in database')
    # Show nearby
    nearby = [i for i in ilis if 3800 <= i[0] <= 3900]
    print(f'Nearby ILIs (3800-3900): {len(nearby)}')
    for n in nearby[:10]:
        print(f'  {n[1]}: {n[2].definition()[:60]}')
