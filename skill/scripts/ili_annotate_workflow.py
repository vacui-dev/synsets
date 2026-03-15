#!/usr/bin/env python3
"""
ILI Annotation Workflow for Hermes Agent

This script uses the native Hermes Agent tool interface to annotate text
with Interlingual Index (ILI) identifiers from WordNet. It calls the
wordnet MCP server's tools directly.

Usage:
    # From within Hermes Agent with the wordnet MCP server configured
    python skill/scripts/ili_annotate_workflow.py --text "The cat sat on the mat"
    python skill/scripts/ili_annotate_workflow.py --file input.txt --output annotated.jsonl
    python skill/scripts/ili_annotate_workflow.py --batch --start 0 --count 1000
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

STOPWORDS = frozenset({
    # determiners
    "a", "an", "the", "this", "that", "these", "those", "my", "your", "his",
    "her", "its", "our", "their", "some", "any", "no", "every", "each",
    "all", "both", "few", "many", "much", "several", "such",
    # pronouns
    "i", "me", "we", "us", "you", "he", "him", "she", "it", "they", "them",
    "myself", "yourself", "himself", "herself", "itself", "ourselves",
    "themselves", "who", "whom", "whose", "which", "what", "whoever",
    # prepositions
    "of", "in", "to", "for", "with", "on", "at", "from", "by", "about",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "under", "along", "until", "upon", "toward", "towards",
    "across", "against", "among", "around", "behind", "beyond", "within",
    "without", "throughout", "despite", "over", "near", "beside", "besides",
    # conjunctions
    "and", "but", "or", "nor", "so", "yet", "for", "because", "although",
    "though", "while", "whereas", "if", "unless", "since", "whether",
    "either", "neither", "than",
    # auxiliary / modal verbs
    "is", "am", "are", "was", "were", "be", "been", "being",
    "has", "have", "had", "having",
    "do", "does", "did", "doing",
    "will", "would", "shall", "should", "may", "might", "can", "could",
    "must", "need", "dare", "ought",
    # adverbs
    "not", "very", "also", "just", "only", "even", "still", "already",
    "then", "too", "here", "there", "where", "when", "how", "why",
    "now", "never", "always", "often", "ever", "quite", "rather",
    # indefinite pronouns
    "something", "anything", "everything", "nothing",
    "someone", "anyone", "everyone", "nobody", "somebody", "anybody",
    "somewhere", "anywhere", "everywhere", "nowhere",
    # other
    "etc", "e", "g", "ie", "vs", "non",
})

ILITOKEN_RE = re.com...) 

# ---------------------------------------------------------------------------
# Text Processing
# ---------------------------------------------------------------------------

def extract_content_words(text: str) -> list[tuple[str, int, int]]:
    """Extract content words from text positions.
    
    Returns list of (word, start_idx, end_idx) for each content word.
    Skips function words (stopwords), short words, and ILI tokens.
    """
    words = []
    # Split on ILI tokens first to get text spans
    parts = ILITOKEN_RE.split(text)
    current_pos = 0
    
    for part in parts:
        if not part:
            current_pos += len("<|i0|>")  # approximate
            continue
            
        # Tokenize words
        for match in re.finditer(r"[a-zA-Z']+", part):
            word = match.group().lower()
            if len(word) >= 2 and word not in STOPWORDS:
                words.append((word, current_pos + match.start(), current_pos + match.end()))
        current_pos += len(part)
    
    return words

def simple_lemmatize(word: str) -> list[str]:
    """Generate candidate lemmas by stripping common English suffixes."""
    candidates = [word]
    w = word.lower()
    
    if w.endswith("ing") and len(w) > 5:
        candidates.append(w[:-3])
        candidates.append(w[:-3] + "e")
        if len(w) > 6 and w[-4] == w[-5]:
            candidates.append(w[:-4])
    if w.endswith("ed") and len(w) > 4:
        candidates.append(w[:-2])
        candidates.append(w[:-1])
        if w.endswith("ied"):
            candidates.append(w[:-3] + "y")
    if w.endswith("es") and len(w) > 4:
        candidates.append(w[:-2])
        candidates.append(w[:-1])
    if w.endswith("ies") and len(w) > 5:
        candidates.append(w[:-3] + "y")
    elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        candidates.append(w[:-1])
    if w.endswith("ly") and len(w) > 4:
        candidates.append(w[:-2])
    if w.endswith("ness") and len(w) > 6:
        candidates.append(w[:-4])
    if w.endswith("ment") and len(w) > 6:
        candidates.append(w[:-4])
    
    return list(dict.fromkeys(candidates))

# ---------------------------------------------------------------------------
# Annotation Workflow
# ---------------------------------------------------------------------------

class ILIAnnotator:
    """Annotate text with ILI identifiers using Hermes Agent tool calls."""
    
    def __init__(self, mcp_wordnet_call=None):
        """
        Args:
            mcp_wordnet_call: Function to call wordnet MCP tools.
                Should have signature: call_tool(name: str, args: dict) -> str
                When running inside Hermes, this will be mcp_wordnet_<tool_name>()
        """
        self.call_tool = mcp_wordnet_call
        self.cache = {}  # Cache lookups
    
    def lookup_word(self, word: str, pos: str | None = None):
        """Call wordnet lookup_word tool."""
        cache_key = (word, pos)
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        if self.call_tool:
            result = self.call_tool("lookup_word", {"word": word, "pos": pos})
        else:
            result = None
        
        self.cache[cache_key] = result
        return result
    
    def annotate_text(self, text: str, context: str = "") -> dict:
        """Annotate a single text with ILI identifiers.
        
        Returns dict with:
            - original_text: input text
            - annotated_text: text with ILI tokens
            - assignments: list of {word, ili, pos, definition, start, end}
        """
        content_words = extract_content_words(text)
        assignments = []
        annotated = text
        offset = 0
        
        for word, start, end in content_words:
            # Try lookup
            result = self.lookup_word(word)
            if result:
                import json
                try:
                    senses = json.loads(result) if isinstance(result, str) else result
                    if senses:
                        # Take first sense (or use context for WSD)
                        sense = senses[0]
                        ili = sense.get("ili", "")
                        pos = sense.get("pos", "")
                        definition = sense.get("definition", "")
                        
                        # Insert ILI token
                        insert_pos = start + offset
                        ili_token = f"<|{ili}|>"
                        annotated = annotated[:insert_pos] + ili_token + annotated[insert_pos:]
                        offset += len(ili_token)
                        
                        assignments.append({
                            "word": word,
                            "ili": ili,
                            "pos": pos,
                            "definition": definition,
                            "start": start,
                            "end": end
                        })
                except json.JSONDecodeError:
                    pass
        
        return {
            "original_text": text,
            "annotated_text": annotated,
            "assignments": assignments
        }

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Annotate text with ILI identifiers")
    parser.add_argument("--text", help="Text to annotate")
    parser.add_argument("--file", help="File to read text from")
    parser.add_argument("--output", "-o", help="Output JSONL file")
    parser.add_argument("--batch", action="store_true", help="Batch mode from corpus")
    parser.add_argument("--start", type=int, default=0, help="Start index (batch)")
    parser.add_argument("--count", type=int, default=100, help="Count (batch)")
    
    args = parser.parse_args()
    
    # Note: When running inside Hermes, the MCP tools are available as
    # mcp_wordnet_lookup_word(), mcp_wordnet_lookup_phrase(), etc.
    # When running standalone, we need to use HTTP or direct DB calls.
    
    annotator = ILIAnnotator()
    
    if args.text:
        result = annotator.annotate_text(args.text)
        print(json.dumps(result, indent=2))
    elif args.file:
        with open(args.file) as f:
            text = f.read()
        result = annotator.annotate_text(text)
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()
        print("\nNote: Full workflow requires running within Hermes Agent with wordnet MCP configured.")

if __name__ == "__main__":
    main()
