---
name: synsets
description: >
  Annotate text with Interlingual Index (ILI) identifiers. Produces 
  language-neutral concept-tagged text for cross-lingual NLP and semantic 
  tokenization research.
version: 1.2.0
author: vacui-dev
license: MOSL-2.0
metadata:
  hermes:
    tags: [WordNet, ILI, annotation, WSD, NLP, MCP, tool-use]
    related_skills: []
    invoke_on: ["/disambiguate", "/synsets", "annotate text", "ILI", "wordnet", "disambiguate"]
---

# Synsets — ILI Text Annotation

Every LLM tokenizes text blind to meaning. "Bank" is one token whether it's a 
financial institution or a riverbank. "Apple" is closer to "iPhone" than "fruit" 
in embedding space. This skill fixes that at the data layer.

It annotates English text with **Interlingual Index (ILI)** concept IDs from 
WordNet — ~120K language-neutral identifiers that pre-disambiguate every content 
word. The model receives meaning in the vocabulary, not derived from context.

## What It Does

Takes ambiguous text and tags each content word with its precise meaning:

```
"The bank approved the loan"
→ "The <|i92258|>bank approved the <|i47222|>loan"
```

`bank` → i92258 (financial institution, not i92416 "sloping land beside water")

## Quick Examples

**Polysemy — same word, different concepts:**
```
"I deposited cash at the river bank"
→ "I <|i24675|>deposited <|i143581|>cash at the <|i92416|>bank"
                                       financial ↑         riverbank ↑

"The bank approved my loan"  
→ "The <|i92258|>bank approved my <|i47222|>loan"
    financial inst. ↑
```

**Multi-word expressions — looked up as units:**
```
"orange juice is fruit juice"
→ "<|i78945|>orange juice is <|i78938|>fruit juice"
  (single concept)          (broader category)
```

**Composition — complex sentences:**
```
"The wheel of the car"
→ "The <|i61096|>wheel of the <|i51496|>car"

"cloud of despair"
→ "<|i113334|>cloud of <|i76387|>despair"
  (metaphorical "gloom")  (hopelessness)
```

**Cross-lingual concepts:**
```
"金持ち means someone who is rich in japanese"
→ "<|i26268|>means <|i35562|>someone who is <|i91209|>rich in <|i72985|>japanese"
  (intend/signify)  (wealthy)     (affluent)      (Japanese language)
```

## How to Use

**Just give me text — any of these work:**
```
/disambiguate "The quick brown fox jumps over the lazy dog"
/synsets "She represents the company"
Annotate: The bank approved the loan
```

**Prerequisites** (must be running before annotation):
```bash
# 1. Install WordNet data (one-time setup)
pip install wn wn-data
python -m wn download ewn:2020

# 2. Start the MCP server (background process)
cd ~/synsets && python3 skill/scripts/wordnet_mcp_server.py &
```

**I will:**
1. Tokenize and identify content words (nouns, verbs, adjectives, adverbs)
2. Look up each word's senses via WordNet MCP tools
3. Disambiguate using sentence context
4. Return inline-tagged text + structured JSON

**Output formats:**

*Inline (plain text):*
```
The <|i92258|>bank <|i25018|>approved the <|i47222|>loan
```

*JSONL (structured):*
```json
{
  "original": "The bank approved the loan",
  "annotated": "The <|i92258|>bank approved the <|i47222|>loan",
  "annotations": [
    {"span": "bank", "ili": 92258, "pos": "n"},
    {"span": "approved", "ili": 25018, "pos": "v"},
    {"span": "loan", "ili": 47222, "pos": "n"}
  ]
}
```

## What Gets Tagged

| Type | Examples | Action |
|------|----------|--------|
| Nouns | bank, car, cat, despair | Tag with ILI |
| Verbs | eat, approve, represent | Tag with ILI |
| Adjectives | lazy, rich, frozen | Tag with ILI |
| Adverbs | probably, always | Tag with ILI |
| Articles | the, a, an | Skip |
| Prepositions | of, in, to, at | Skip |
| Pronouns | I, you, he, she, it | Skip |
| Auxiliaries | is, am, are, was | Skip |
| Conjunctions | and, but, or | Skip |
| Modals | can, will, should | Skip |

## Other Capabilities

**Explore word senses:**
```
"What are the senses of 'run'?"
→ Returns all ILI senses: physical motion (i21017), operate (i21024), 
  manage (i21058), flow (i21089), ...
```

**Look up a synset:**
```
"Tell me about i92258"
→ Definition: "financial institution", hypernyms, hyponyms, relations
```

**Search by concept:**
```
"Find synsets for 'financial institution'"
→ Returns matching ILI IDs and definitions
```

**Multi-word expressions:**
```
"What's the ILI for 'credit card'?"
→ Single ILI for the compound concept
```

## Architecture

```
Your Text
    ↓
Hermes Agent (disambiguates each word)
    ↓ tool calls: lookup_word, lookup_phrase, get_synset
WordNet MCP Server (localhost:8741)
    ↓ SQLite queries
English WordNet (120K synsets, 117K ILI mappings)
    ↓
ILI-annotated Output
```

## Why This Matters

**Disambiguation is expensive.** Every transformer layer spends attention 
figuring out which "bank" you meant. Multiply by every content word, every 
sentence, every forward pass. ILI-annotated data pays this cost once at 
training time — the embedding becomes a concept space, not a subword soup.

**Language-neutral concepts.** `i92258` means "financial institution" in 
English, Chinese, Japanese, Arabic, and 46 other languages with linked WordNets. 
A model with ILI tokens is inherently multilingual.

## ILI Format Reference

```
<iNNNNN|>   — internal format (used in output)
  e.g. <|i92258|> = financial institution

ILI_NNNNNN — legacy format with POS prefix
  e.g. ILI_N092258, ILI_V025018
```

IDs come from the Collaborative Interlingual Index (CILI), linking ~120K 
concepts across 50+ language WordNets.
