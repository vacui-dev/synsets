#!/usr/bin/env python3
"""
Compressed-ILI (.cili) format encoder/decoder.

Format:
  - Header: #CILI v1, vocab size, record count
  - Vocab: one line per ILI, sorted by corpus frequency (most frequent = rank 0)
    Format: <rank> <original_ILI_id> <corpus_frequency>
  - Separator: ---
  - Documents: text with ILI references as <rank>, separated by ===
    Within each document, ILI rank IDs appear in increasing order of first occurrence.

The format compresses well with gzip because frequent ILIs get small rank numbers
(single digits), and the text is highly repetitive.

A researcher can extend a tokenizer by adding <|ILI_NNNNNN|> tokens for each
vocab entry, where NNNNNN is the original ILI ID from the vocab table.
"""

import json
import re
import sys
import gzip
from collections import Counter
from pathlib import Path

ILI_PATTERN = re.compile(r'<\|i(\d+)(?::[^|]*)?\|>')


def build_global_vocab(jsonl_path: str) -> list[tuple[int, int]]:
    """Scan corpus, return [(ili_id, frequency)] sorted by frequency desc."""
    freq = Counter()
    with open(jsonl_path) as f:
        for line in f:
            d = json.loads(line)
            for m in ILI_PATTERN.finditer(d['text']):
                freq[int(m.group(1))] += 1
    # Sort by frequency descending, then by ILI ID ascending for ties
    return sorted(freq.items(), key=lambda x: (-x[1], x[0]))


def encode_document(text: str, ili_to_rank: dict[int, int]) -> str:
    """Replace <|iNNN|> and <|iNNN:word|> tokens with <rank> references.

    Tokens are replaced in document order. The rank IDs naturally increase
    through the document because the vocab is frequency-sorted.
    """
    def replace_ili(m):
        ili_id = int(m.group(1))
        rank = ili_to_rank.get(ili_id)
        if rank is not None:
            return f'<{rank}>'
        return m.group(0)  # keep original if not in vocab

    return ILI_PATTERN.sub(replace_ili, text)


def compress_corpus(jsonl_path: str, output_path: str):
    """Convert JSONL corpus to .cili format."""
    print(f"Building vocabulary from {jsonl_path}...")
    vocab = build_global_vocab(jsonl_path)
    ili_to_rank = {ili_id: rank for rank, (ili_id, _) in enumerate(vocab)}

    print(f"Vocabulary: {len(vocab)} ILIs")

    # Read all records
    records = []
    with open(jsonl_path) as f:
        for line in f:
            records.append(json.loads(line))

    print(f"Records: {len(records)}")

    # Write .cili format
    lines = []
    lines.append(f'#CILI v1')
    lines.append(f'#vocab {len(vocab)}')
    lines.append(f'#records {len(records)}')
    lines.append('')

    # Vocab section: rank ili_id frequency
    for rank, (ili_id, freq) in enumerate(vocab):
        lines.append(f'{rank} {ili_id} {freq}')

    lines.append('---')

    # Documents section
    for i, record in enumerate(records):
        if i > 0:
            lines.append('===')

        # Source ILI as metadata line
        if 'source_ili' in record:
            lines.append(f'#src {record["source_ili"]}')

        encoded = encode_document(record['text'], ili_to_rank)
        lines.append(encoded)

    cili_text = '\n'.join(lines) + '\n'

    # Write plain text
    plain_path = output_path
    with open(plain_path, 'w') as f:
        f.write(cili_text)
    plain_size = Path(plain_path).stat().st_size

    # Write gzipped
    gz_path = output_path + '.gz'
    with gzip.open(gz_path, 'wt', compresslevel=9) as f:
        f.write(cili_text)
    gz_size = Path(gz_path).stat().st_size

    print(f"Plain:  {plain_path} ({plain_size / 1024 / 1024:.1f} MB)")
    print(f"Gzipped: {gz_path} ({gz_size / 1024 / 1024:.1f} MB)")

    # Stats
    original_size = Path(jsonl_path).stat().st_size
    print(f"Original JSONL: {original_size / 1024 / 1024:.1f} MB")
    print(f"Compression: {gz_size / original_size * 100:.1f}% of original")


def decode_cili(cili_path: str) -> list[dict]:
    """Decode .cili format back to records with <|ILI_NNNNNN|> tokens."""
    opener = gzip.open if cili_path.endswith('.gz') else open

    with opener(cili_path, 'rt') as f:
        content = f.read()

    # Parse header
    header_end = content.index('\n---\n')
    header = content[:header_end]
    body = content[header_end + 5:]  # skip \n---\n

    # Parse vocab
    rank_to_ili = {}
    for line in header.split('\n'):
        if line.startswith('#') or not line.strip():
            continue
        parts = line.split()
        rank, ili_id = int(parts[0]), int(parts[1])
        rank_to_ili[rank] = ili_id

    # Parse documents
    rank_pattern = re.compile(r'<(\d+)>')
    records = []

    for doc_text in body.split('\n===\n'):
        source_ili = None
        lines = doc_text.split('\n')
        text_lines = []
        for line in lines:
            if line.startswith('#src '):
                source_ili = int(line[5:])
            else:
                text_lines.append(line)

        text = '\n'.join(text_lines)

        # Replace <rank> with <|ILI_NNNNNN|>
        def expand_rank(m):
            rank = int(m.group(1))
            ili_id = rank_to_ili.get(rank, 0)
            return f'<|ILI_{ili_id:06d}|>'

        expanded = rank_pattern.sub(expand_rank, text)

        record = {'text': expanded}
        if source_ili is not None:
            record['source_ili'] = source_ili
        records.append(record)

    return records


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage:")
        print("  compress_ili.py encode <input.jsonl> <output.cili>")
        print("  compress_ili.py decode <input.cili|input.cili.gz> [output.jsonl]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'encode':
        compress_corpus(sys.argv[2], sys.argv[3])

    elif cmd == 'decode':
        records = decode_cili(sys.argv[2])
        if len(sys.argv) > 3:
            with open(sys.argv[3], 'w') as f:
                for r in records:
                    f.write(json.dumps(r) + '\n')
            print(f"Decoded {len(records)} records to {sys.argv[3]}")
        else:
            # Print first 3
            for r in records[:3]:
                print(r['text'][:200])
                print('---')

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
