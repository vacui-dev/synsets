#!/usr/bin/env python3
"""
Annotate definition files with ILI identifiers.

Usage:
    python annotate_definition.py input.txt output.txt
"""

import json
import re
import sys
import os

# Add parent directory to path to import common
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import from MCP server module
try:
    from scripts.wordnet_mcp_server_stdio import lookup_word, simple_lemmatize
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("Warning: MCP server module not available, using fallback")

STOPWORDS = {
    'a', 'an', 'the', 'is', 'of', 'in', 'or', 'and', 'for', 'as', 'it', 'were', 'are',
    'was', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
    'would', 'could', 'should', 'may', 'might', 'can', 'shall', 'to', 'from', 'by',
    'with', 'at', 'on', 'before', 'after', 'during', 'through', 'above', 'below',
    'under', 'over', 'into', 'onto', 'off', 'out', 'up', 'down', 'such', 'that',
    'this', 'these', 'those', 'they', 'their', 'them', 'there', 'then', 'than',
    'when', 'where', 'why', 'how', 'what', 'who', 'which', 'while', 'although',
    'though', 'because', 'since', 'until', 'unless', 'if', 'whether', 'so', 'yet',
    'but', 'nor', 'either', 'neither', 'both', 'all', 'any', 'some', 'many', 'much',
    'more', 'most', 'few', 'fewer', 'fewest', 'little', 'less', 'least', 'very',
    'quite', 'rather', 'just', 'only', 'even', 'also', 'too', 'enough', 'almost',
    'nearly', 'really', 'actually', 'already', 'always', 'often', 'sometimes',
    'usually', 'never', 'not', 'no', 'yes', 'am', 'oh', 'ah', 'hey', 'hi', 'hello',
    's', 't', 'd', 'll', 're', 've', 'm', 'other'
}

def normalize_ili(ili: str) -> str:
    """Convert ili to ILI_NNNNNN format."""
    ili_clean = ili.replace('i', '').replace('ILI_', '')
    return f"ILI_{int(ili_clean):06d}"

def annotate_text(text: str, cache: dict = None) -> str:
    """Annotate text with ILI tokens for each content word."""
    if cache is None:
        cache = {}
    
    result = []
    words_found = []
    
    # Split text into words while preserving whitespace/punctuation
    for match in re.finditer(r'(\b[a-zA-Z]+\b)|(\W+)', text):
        word = match.group(1)
        non_word = match.group(2)
        
        if word:
            word_lower = word.lower()
            
            # Skip stopwords and short words
            if word_lower in STOPWORDS or len(word_lower) < 2:
                result.append(word)
            else:
                # Look up word in cache or query
                if word_lower not in cache:
                    if MCP_AVAILABLE:
                        senses = lookup_word(word_lower)
                        if senses:
                            # Take first sense (could use context for better disambiguation)
                            cache[word_lower] = senses[0]['ili']
                        else:
                            cache[word_lower] = None
                    else:
                        cache[word_lower] = None
                
                ili = cache.get(word_lower)
                if ili:
                    formatted_ili = normalize_ili(ili)
                    result.append(f"<|{formatted_ili}|>{word}")
                    words_found.append((word, ili))
                else:
                    result.append(word)
        elif non_word:
            result.append(non_word)
    
    return ''.join(result), words_found

def main():
    if len(sys.argv) < 3:
        print("Usage: python annotate_definition.py input.txt output.txt")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    with open(input_file, 'r') as f:
        text = f.read()
    
    annotated, words = annotate_text(text)
    
    with open(output_file, 'w') as f:
        f.write(annotated)
    
    print(f"Annotated {len(words)} words")
    print(f"Output written to {output_file}")

if __name__ == "__main__":
    main()
