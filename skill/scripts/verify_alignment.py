#!/usr/bin/env python3
"""
Verify ILI alignment across multilingual merged files.

Usage:
    python verify_alignment.py ili_XXXXX
    
Checks that all language files in merged/ have:
- Same ILI sequence (order preserved)
- Same ILI count per language
- Reports any mismatches
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path


def extract_ili_sequence(filepath):
    """Extract ordered list of ILIs from a file."""
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all ILI tags in order
    ilis = re.findall(r'<\|ILI_(\d+)\|>', content)
    return ilis


def strip_to_ili_only(filepath, output_path=None):
    """Strip file to ILI sequence only (for machine learning)."""
    ilis = extract_ili_sequence(filepath)
    if ilis is None:
        return None
    
    result = ' '.join([f"<|ILI_{ili}|>" for ili in ilis])
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)
    
    return result


def verify_ili_directory(ili_dir):
    """Verify all merged files in an ILI directory."""
    merged_dir = os.path.join(ili_dir, 'merged')
    
    if not os.path.exists(merged_dir):
        print(f"Error: No merged/ directory in {ili_dir}")
        return False
    
    # Find all language files
    lang_files = {}
    for f in os.listdir(merged_dir):
        if f.endswith('.txt') and not f.startswith('.'):
            lang = f.replace('.txt', '')
            lang_files[lang] = os.path.join(merged_dir, f)
    
    if len(lang_files) < 2:
        print(f"Warning: Only {len(lang_files)} language file(s) found")
        return False
    
    # Extract ILI sequences
    sequences = {}
    for lang, filepath in lang_files.items():
        seq = extract_ili_sequence(filepath)
        if seq:
            sequences[lang] = seq
            print(f"  {lang}: {len(seq)} ILIs")
    
    # Verify alignment
    if len(sequences) < 2:
        print("Error: Need at least 2 languages with ILIs")
        return False
    
    # Use first language as reference
    ref_lang = list(sequences.keys())[0]
    ref_seq = sequences[ref_lang]
    
    all_aligned = True
    mismatches = []
    
    for lang, seq in sequences.items():
        if lang == ref_lang:
            continue
        
        if len(seq) != len(ref_seq):
            print(f"  ✗ {lang}: Count mismatch ({len(seq)} vs {len(ref_seq)})")
            all_aligned = False
            mismatches.append({
                'language': lang,
                'issue': 'count_mismatch',
                'expected': len(ref_seq),
                'actual': len(seq)
            })
        elif seq != ref_seq:
            # Find first mismatch
            for i, (a, b) in enumerate(zip(ref_seq, seq)):
                if a != b:
                    print(f"  ✗ {lang}: Order mismatch at position {i}")
                    print(f"     Expected: ILI_{a}, Got: ILI_{b}")
                    mismatches.append({
                        'language': lang,
                        'issue': 'order_mismatch',
                        'position': i,
                        'expected': a,
                        'actual': b
                    })
                    all_aligned = False
                    break
        else:
            print(f"  ✓ {lang}: Aligned")
    
    return all_aligned, mismatches


def main():
    parser = argparse.ArgumentParser(
        description='Verify ILI alignment across multilingual files'
    )
    parser.add_argument('ili_dir', help='Path to ili_XXXXX directory')
    parser.add_argument('--strip', action='store_true',
                        help='Create ILI-only stripped versions')
    parser.add_argument('--output-dir', help='Directory for stripped files')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.ili_dir):
        print(f"Error: Directory not found: {args.ili_dir}")
        sys.exit(1)
    
    print(f"Verifying: {args.ili_dir}")
    
    result = verify_ili_directory(args.ili_dir)
    
    if isinstance(result, tuple):
        aligned, mismatches = result
    else:
        aligned = result
        mismatches = []
    
    # Create stripped versions if requested
    if args.strip and args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        
        merged_dir = os.path.join(args.ili_dir, 'merged')
        for f in os.listdir(merged_dir):
            if f.endswith('.txt'):
                input_path = os.path.join(merged_dir, f)
                output_path = os.path.join(args.output_dir, f.replace('.txt', '.ili'))
                strip_to_ili_only(input_path, output_path)
                print(f"  Stripped: {f} -> {output_path}")
    
    # Update meta.json
    meta_path = os.path.join(args.ili_dir, 'meta.json')
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        
        meta['alignment_verified'] = aligned
        meta['alignment_mismatches'] = mismatches
        
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=2)
        
        print(f"\nUpdated: {meta_path}")
    
    if aligned:
        print("\n✓ All languages aligned")
        sys.exit(0)
    else:
        print("\n✗ Alignment issues found")
        sys.exit(1)


if __name__ == '__main__':
    main()
