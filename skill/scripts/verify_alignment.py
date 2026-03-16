#!/usr/bin/env python3
"""
Verify ILI alignment across multilingual merged files.

Two verification modes:
- STRICT (default): All ILI counts must match exactly across languages
- LOOSE: All unique ILIs must appear in all languages, counts may differ

Usage:
    python verify_alignment.py ili_XXXXX/MODEL_NAME [--mode strict|loose]
    
Examples:
    # Strict mode - exact count match (default)
    python verify_alignment.py ili_73081/kimi-k2.5
    
    # Loose mode - unique ILI coverage only
    python verify_alignment.py ili_73081/kimi-k2.5 --mode loose
    
Exit codes:
    0 - Verification passed
    1 - Verification failed (regression detected)
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
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


def get_ili_counts(filepath):
    """Get Counter of ILI occurrences."""
    ilis = extract_ili_sequence(filepath)
    if ilis is None:
        return None
    return Counter(ilis)


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


def verify_strict(sequences, counts):
    """
    Strict mode: All ILI counts must match exactly.
    
    If EN has ILI_12345 appearing 3 times, JA must also have it 3 times.
    This fights LLM laziness where languages drop ILI repetitions.
    """
    langs = list(sequences.keys())
    if len(langs) < 2:
        return False, []
    
    ref_lang = langs[0]
    ref_seq = sequences[ref_lang]
    ref_counts = counts[ref_lang]
    
    all_aligned = True
    mismatches = []
    
    for lang in langs[1:]:
        seq = sequences[lang]
        lang_counts = counts[lang]
        
        # Check total count
        if len(seq) != len(ref_seq):
            print(f"  ✗ {lang}: Total count mismatch ({len(seq)} vs {len(ref_seq)})")
            all_aligned = False
            mismatches.append({
                'language': lang,
                'issue': 'total_count_mismatch',
                'expected': len(ref_seq),
                'actual': len(seq),
                'mode': 'strict'
            })
            continue
        
        # Check per-ILI counts
        per_ili_issues = []
        for ili, ref_count in ref_counts.items():
            lang_count = lang_counts.get(ili, 0)
            if lang_count != ref_count:
                per_ili_issues.append({
                    'ili': ili,
                    'expected_count': ref_count,
                    'actual_count': lang_count
                })
        
        if per_ili_issues:
            print(f"  ✗ {lang}: Per-ILI count mismatches ({len(per_ili_issues)} issues)")
            for issue in per_ili_issues[:5]:  # Show first 5
                print(f"     ILI_{issue['ili']}: expected {issue['expected_count']}, got {issue['actual_count']}")
            if len(per_ili_issues) > 5:
                print(f"     ... and {len(per_ili_issues) - 5} more")
            
            all_aligned = False
            mismatches.append({
                'language': lang,
                'issue': 'per_ili_count_mismatch',
                'mode': 'strict',
                'details': per_ili_issues
            })
        elif seq != ref_seq:
            # Same counts but different order - also a mismatch
            for i, (a, b) in enumerate(zip(ref_seq, seq)):
                if a != b:
                    print(f"  ✗ {lang}: Order mismatch at position {i}")
                    print(f"     Expected: ILI_{a}, Got: ILI_{b}")
                    mismatches.append({
                        'language': lang,
                        'issue': 'order_mismatch',
                        'position': i,
                        'expected': a,
                        'actual': b,
                        'mode': 'strict'
                    })
                    all_aligned = False
                    break
        else:
            print(f"  ✓ {lang}: Strict alignment passed")
    
    return all_aligned, mismatches


def verify_loose(sequences, counts):
    """
    Loose mode: All unique ILIs must appear in all languages.
    
    If EN has ILI_12345 appearing 3 times and JA has it 1 time, that's okay.
    This allows language-specific expression differences while ensuring
    all concepts are covered.
    """
    langs = list(sequences.keys())
    if len(langs) < 2:
        return False, []
    
    ref_lang = langs[0]
    ref_counts = counts[ref_lang]
    ref_unique = set(ref_counts.keys())
    
    all_covered = True
    mismatches = []
    
    for lang in langs[1:]:
        lang_counts = counts[lang]
        lang_unique = set(lang_counts.keys())
        
        # Check coverage
        missing = ref_unique - lang_unique
        extra = lang_unique - ref_unique
        
        if missing or extra:
            print(f"  ✗ {lang}: ILI set mismatch")
            if missing:
                print(f"     Missing ILIs: {sorted(list(missing))[:10]}")
                if len(missing) > 10:
                    print(f"     ... and {len(missing) - 10} more")
            if extra:
                print(f"     Extra ILIs: {sorted(list(extra))[:10]}")
                if len(extra) > 10:
                    print(f"     ... and {len(extra) - 10} more")
            
            all_covered = False
            mismatches.append({
                'language': lang,
                'issue': 'ili_set_mismatch',
                'mode': 'loose',
                'missing': list(missing),
                'extra': list(extra)
            })
        else:
            # Show count differences (informational)
            count_diffs = []
            for ili in ref_unique:
                ref_count = ref_counts[ili]
                lang_count = lang_counts[ili]
                if ref_count != lang_count:
                    count_diffs.append(f"ILI_{ili}: {ref_count}→{lang_count}")
            
            if count_diffs:
                print(f"  ✓ {lang}: Coverage passed (count diffs: {len(count_diffs)})")
                for diff in count_diffs[:3]:
                    print(f"     {diff}")
                if len(count_diffs) > 3:
                    print(f"     ... and {len(count_diffs) - 3} more")
            else:
                print(f"  ✓ {lang}: Full alignment (counts match too)")
    
    return all_covered, mismatches


def verify_ili_directory(ili_dir, mode='strict'):
    """Verify all merged files in an ILI directory."""
    merged_dir = os.path.join(ili_dir, 'merged')
    
    if not os.path.exists(merged_dir):
        print(f"Error: No merged/ directory in {ili_dir}")
        return False, []
    
    # Find all language files
    lang_files = {}
    for f in os.listdir(merged_dir):
        if f.endswith('.txt') and not f.startswith('.'):
            lang = f.replace('.txt', '')
            lang_files[lang] = os.path.join(merged_dir, f)
    
    if len(lang_files) < 2:
        print(f"Warning: Only {len(lang_files)} language file(s) found")
        return False, []
    
    # Extract ILI sequences and counts
    sequences = {}
    counts = {}
    
    for lang, filepath in lang_files.items():
        seq = extract_ili_sequence(filepath)
        if seq:
            sequences[lang] = seq
            counts[lang] = Counter(seq)
            print(f"  {lang}: {len(seq)} ILIs, {len(counts[lang])} unique")
    
    # Verify based on mode
    if mode == 'strict':
        print(f"\n  Mode: STRICT (exact count match required)")
        return verify_strict(sequences, counts)
    else:
        print(f"\n  Mode: LOOSE (unique ILI coverage required)")
        return verify_loose(sequences, counts)


def main():
    parser = argparse.ArgumentParser(
        description='Verify ILI alignment across multilingual files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Modes:
  strict (default) - All ILI counts must match exactly across languages.
                     Fights LLM laziness where languages drop repetitions.
  
  loose            - All unique ILIs must appear in all languages.
                     Allows language-specific expression differences.

Examples:
  %(prog)s ili_73081/kimi-k2.5
  %(prog)s ili_73081/kimi-k2.5 --mode strict
  %(prog)s ili_73081/kimi-k2.5 --mode loose
        '''
    )
    parser.add_argument('ili_dir', help='Path to ili_XXXXX/MODEL directory')
    parser.add_argument('--mode', choices=['strict', 'loose'], default='strict',
                        help='Verification mode (default: strict)')
    parser.add_argument('--strip', action='store_true',
                        help='Create ILI-only stripped versions')
    parser.add_argument('--output-dir', help='Directory for stripped files')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.ili_dir):
        print(f"Error: Directory not found: {args.ili_dir}")
        sys.exit(1)
    
    print(f"Verifying: {args.ili_dir}")
    
    aligned, mismatches = verify_ili_directory(args.ili_dir, args.mode)
    
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
    meta_path = os.path.join(os.path.dirname(args.ili_dir), 'meta.json')
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        
        model_name = os.path.basename(args.ili_dir)
        if 'models' not in meta:
            meta['models'] = {}
        if model_name not in meta['models']:
            meta['models'][model_name] = {}
        
        meta['models'][model_name]['alignment_verified'] = aligned
        meta['models'][model_name]['verification_mode'] = args.mode
        meta['models'][model_name]['alignment_mismatches'] = mismatches
        
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=2)
        
        print(f"\nUpdated: {meta_path}")
    
    if aligned:
        print(f"\n✓ Verification passed ({args.mode} mode)")
        sys.exit(0)
    else:
        print(f"\n✗ Verification failed ({args.mode} mode)")
        print("\nTip: Use --mode loose if count differences are intentional")
        print("     (e.g., language-specific expression differences)")
        sys.exit(1)


if __name__ == '__main__':
    main()
