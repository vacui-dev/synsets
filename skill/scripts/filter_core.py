#!/usr/bin/env python3
"""
Filter Core ILIs — extract only the 9,461 well-defined core concepts.

Core ILIs are concepts that have their own dedicated definition document
in the corpus. Each has 2-50+ occurrences and rich cross-references.

Non-core ILIs (cross-references) are kept as plain text in the output
so the natural language context is preserved.

Usage:
    python filter_core.py data/synset_v4.cili.gz -o data/core_only.cili.gz
    python filter_core.py data/synset_v4.cili.gz --stats  # just print stats
"""

import argparse
import gzip
import re
import sys
from collections import Counter
from pathlib import Path


def parse_cili(cili_path: str):
    """Parse a .cili.gz file into vocab and documents."""
    opener = gzip.open if cili_path.endswith('.gz') else open

    vocab = {}  # ili_id -> (rank, freq)
    source_ilis = set()
    documents = []

    with opener(cili_path, 'rt') as f:
        in_docs = False
        current_doc = None

        for line in f:
            line = line.rstrip('\n')

            if line.strip() == '---':
                in_docs = True
                continue

            if not in_docs:
                if line.startswith('#') or not line.strip():
                    continue
                parts = line.split()
                if len(parts) == 3:
                    rank, ili_id, freq = int(parts[0]), int(parts[1]), int(parts[2])
                    vocab[ili_id] = (rank, freq)
            else:
                if line.strip() == '===':
                    if current_doc is not None:
                        documents.append(current_doc)
                    current_doc = {'src': None, 'lines': []}
                elif line.startswith('#src '):
                    if current_doc is None:
                        current_doc = {'src': None, 'lines': []}
                    current_doc['src'] = int(line.split()[1])
                    source_ilis.add(current_doc['src'])
                else:
                    if current_doc is None:
                        current_doc = {'src': None, 'lines': []}
                    current_doc['lines'].append(line)

        if current_doc is not None:
            documents.append(current_doc)

    return vocab, source_ilis, documents


def filter_to_core(cili_path: str, output_path: str | None = None, stats_only: bool = False):
    """Filter corpus to only core ILIs."""
    vocab, source_ilis, documents = parse_cili(cili_path)

    # Core vs cross-ref stats
    core_vocab = {ili: (rank, freq) for ili, (rank, freq) in vocab.items() if ili in source_ilis}
    crossref_vocab = {ili: (rank, freq) for ili, (rank, freq) in vocab.items() if ili not in source_ilis}

    core_total_occ = sum(freq for _, freq in core_vocab.values())
    crossref_total_occ = sum(freq for _, freq in crossref_vocab.values())

    print(f"=== Corpus Analysis ===")
    print(f"Total ILIs:          {len(vocab):,}")
    print(f"Core ILIs:           {len(core_vocab):,} ({len(core_vocab)/len(vocab)*100:.1f}%)")
    print(f"Cross-ref ILIs:      {len(crossref_vocab):,} ({len(crossref_vocab)/len(vocab)*100:.1f}%)")
    print(f"")
    print(f"Core occurrences:    {core_total_occ:,} ({core_total_occ/(core_total_occ+crossref_total_occ)*100:.1f}%)")
    print(f"Cross-ref occ:       {crossref_total_occ:,} ({crossref_total_occ/(core_total_occ+crossref_total_occ)*100:.1f}%)")
    print(f"Documents:           {len(documents):,}")

    # Frequency distribution of core ILIs
    print(f"\n=== Core ILI Frequency Distribution ===")
    buckets = [(2, 5), (6, 10), (11, 20), (21, 50), (51, 100), (101, 99999)]
    for lo, hi in buckets:
        count = sum(1 for _, (_, f) in core_vocab.items() if lo <= f <= hi)
        label = f"{lo}-{hi}" if hi < 99999 else f">= {lo}"
        print(f"  {label:12s}: {count:6,} ILIs")

    if stats_only:
        return

    if output_path is None:
        print("\nNo output path specified. Use -o to write filtered corpus.", file=sys.stderr)
        return

    # Build filtered vocab (core only, re-ranked)
    core_sorted = sorted(core_vocab.items(), key=lambda x: (-x[1][1], x[0]))
    new_rank = {}
    for i, (ili, (_, freq)) in enumerate(core_sorted):
        new_rank[ili] = i

    # Write filtered .cili
    lines = []
    lines.append('#CILI v1')
    lines.append(f'#vocab {len(core_sorted)}')
    lines.append(f'#records {len(documents)}')
    lines.append(f'#filter core-only')
    lines.append('')

    for i, (ili, (_, freq)) in enumerate(core_sorted):
        lines.append(f'{i} {ili} {freq}')

    lines.append('---')

    # Re-encode documents with only core ILI references
    rank_pattern = re.compile(r'<(\d+)>')
    old_rank_to_ili = {rank: ili for ili, (rank, _) in vocab.items()}

    for i, doc in enumerate(documents):
        if i > 0:
            lines.append('===')
        if doc['src'] is not None:
            lines.append(f'#src {doc["src"]}')

        for line in doc['lines']:
            def replace_rank(m):
                old_rank = int(m.group(1))
                ili = old_rank_to_ili.get(old_rank)
                if ili is not None and ili in new_rank:
                    return f'<{new_rank[ili]}>'
                # Non-core ILI: remove the token, keep surrounding text
                return ''
            filtered_line = rank_pattern.sub(replace_rank, line)
            # Clean up double spaces from removed tokens
            filtered_line = re.sub(r'  +', ' ', filtered_line)
            lines.append(filtered_line)

    cili_text = '\n'.join(lines) + '\n'

    if output_path.endswith('.gz'):
        with gzip.open(output_path, 'wt', compresslevel=9) as f:
            f.write(cili_text)
    else:
        with open(output_path, 'w') as f:
            f.write(cili_text)

    size = Path(output_path).stat().st_size
    print(f"\nWritten core-only corpus to {output_path} ({size/1024/1024:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Filter corpus to core ILIs only")
    parser.add_argument("input", help="Input .cili or .cili.gz file")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("--stats", action="store_true", help="Print stats only, don't filter")
    args = parser.parse_args()
    filter_to_core(args.input, args.output, args.stats)


if __name__ == "__main__":
    main()
