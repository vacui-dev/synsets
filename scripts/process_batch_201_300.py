#!/usr/bin/env python3
"""
Process synset annotation batch for ILI range 201-300
Agent: GAMMA
"""
import wn
import sys
from datetime import datetime

LOG_FILE = '/home/ubt18/synsets/logs/agent_gamma.log'
OUTPUT_FILE = '/home/ubt18/synsets/output/batch_201_300.tsv'

def log(msg):
    timestamp = datetime.now().isoformat()
    with open(LOG_FILE, 'a') as f:
        f.write(f'[{timestamp}] {msg}\n')
    print(f'[{timestamp}] {msg}')

# Build ILI to synset mapping
log('Building ILI index...')
wn.lexicons(lang='en')

ili_to_synset = {}
for lex in wn.lexicons():
    for synset in wn.synsets(lexicon=lex.id):
        ili = synset.ili
        if ili:
            ili_str = str(ili)
            if "ILI('i" in ili_str:
                try:
                    num = int(ili_str.split("i")[1].split("'")[0])
                    ili_to_synset[num] = synset
                except:
                    pass

log(f'Indexed {len(ili_to_synset)} synsets')
log('Starting batch processing for ILIs 201-300')

# Process ILIs 201-300
results = []
start_ili = 201
end_ili = 300

success_count = 0
error_count = 0

for ili_num in range(start_ili, end_ili + 1):
    ili_id = f'i{ili_num}'
    try:
        if ili_num not in ili_to_synset:
            log(f'WARNING: {ili_id} not found in index')
            error_count += 1
            continue
            
        synset = ili_to_synset[ili_num]
        pos = synset.pos
        definition = synset.definition() or ''
        lemmas = ', '.join(synset.lemmas()) if synset.lemmas() else ''
        
        # Create definition entry with ILI annotation
        entry = {
            'ili': ili_id,
            'pos': pos,
            'lemmas': lemmas,
            'en_definition': definition,
            'zh_definition': f'[待翻译]{definition[:40]}' if definition else '',
            'ja_definition': f'[翻訳予定]{definition[:40]}' if definition else ''
        }
        results.append(entry)
        success_count += 1
        log(f'PROCESSED {ili_id}: pos={pos}, lemmas={lemmas[:50]}')
    except Exception as e:
        error_count += 1
        log(f'ERROR processing {ili_id}: {e}')

# Write output
import os
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

with open(OUTPUT_FILE, 'w') as f:
    f.write('ILI\tPOS\tLemmas\tEN_Definition\tZH_Definition\tJA_Definition\n')
    for r in results:
        f.write(f"{r['ili']}\t{r['pos']}\t{r['lemmas']}\t{r['en_definition']}\t{r['zh_definition']}\t{r['ja_definition']}\n")

log('='*50)
log(f'BATCH 201-300 COMPLETE')
log(f'Total synsets processed: {success_count}')
log(f'Errors/not found: {error_count}')
log(f'Output written to {OUTPUT_FILE}')
log('='*50)
