#!/usr/bin/env python3
"""
Process synset annotation batch for ILI range 101-200
Agent: BETA
"""
import wn
import re
from datetime import datetime

LOG_FILE = '/home/ubt18/synsets/logs/agent_beta.log'
OUTPUT_FILE = '/home/ubt18/synsets/output/batch_101_200.tsv'

def log(msg):
    timestamp = datetime.now().isoformat()
    with open(LOG_FILE, 'a') as f:
        f.write(f'[{timestamp}] {msg}\n')
    print(f'[{timestamp}] {msg}')

log('=== Starting batch processing for ILIs 101-200 ===')

# Build lookup of all synsets
synsets = list(wn.synsets(lexicon='ewn:2020'))
ili_lookup = {}
for synset in synsets:
    if synset.ili:
        ili_str = str(synset.ili)
        match = re.search(r"i(\d+)", ili_str)
        if match:
            num = int(match.group(1))
            ili_lookup[num] = synset

# Process ILIs 101-200
results = []
for num in range(101, 201):
    if num in ili_lookup:
        synset = ili_lookup[num]
        pos = synset.pos
        definition = synset.definition() or ''
        lemmas = ', '.join(synset.lemmas()) if synset.lemmas() else ''
        
        entry = {
            'ili': f'i{num}',
            'pos': pos,
            'lemmas': lemmas,
            'en_definition': definition,
            'zh_definition': '',  # Placeholder for Chinese translation
            'ja_definition': ''   # Placeholder for Japanese translation
        }
        results.append(entry)
        log(f'Processed i{num}: {lemmas[:40]}...')
    else:
        log(f'Skipped i{num}: not found in database')

# Write output
with open(OUTPUT_FILE, 'w') as f:
    f.write('ILI\tPOS\tLemmas\tEN_Definition\tZH_Definition\tJA_Definition\n')
    for r in results:
        f.write(f"{r['ili']}\t{r['pos']}\t{r['lemmas']}\t{r['en_definition']}\t{r['zh_definition']}\t{r['ja_definition']}\n")

log(f'=== Completed processing ===')
log(f'Total synsets processed: {len(results)}')
log(f'Output written to: {OUTPUT_FILE}')
