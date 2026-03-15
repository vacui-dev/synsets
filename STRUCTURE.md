# Synset Data Structure v3.0

## Directory Layout

```
data/synsets/
  ili_XXXXXX/                    # One folder per ILI
    meta.json                    # Model, timestamp, validation
    MODEL_NAME/                  # e.g., kimi-k2.5, claude-sonnet-4
      natural/                   # Wikipedia-quality natural text
        en.txt                   # English (proper grammar)
        cz.txt                   # Chinese (proper grammar)
        ja.txt                   # Japanese (proper grammar)
      ili/                       # ILI-annotated versions
        en.txt                   # English with ILI tags
        cz.txt                   # Chinese with ILI tags
        ja.txt                   # Japanese with ILI tags
      merged/                    # Grammar-correct, ILI-aligned
        en.txt                   # English (function words untagged)
        cz.txt                   # Chinese (function words untagged)
        ja.txt                   # Japanese (particles untagged)
```

## Multiple Models

Different models can generate data for the same ILI:

```
ili_73081/
  meta.json                      # Points to best/merged version
  kimi-k2.5/                     # Kimi generation
    natural/
    ili/
    merged/
  claude-sonnet-4/               # Claude generation
    natural/
    ili/
    merged/
  gpt-4/                         # GPT-4 generation
    natural/
    ili/
    merged/
```

## File Types

### MODEL/natural/*.txt
Original Wikipedia-quality definitions.
- Proper grammar for each language
- No ILI annotations
- May vary in length and detail per language

### MODEL/ili/*.txt
Word-by-word ILI annotations.
- Content words tagged: `<|ILI_12345|>word`
- Function words untagged: `the`, `and`, `of`, etc.
- Japanese particles untagged: `は`, `を`, `が`, etc.
- Grammar preserved from natural version

### MODEL/merged/*.txt
**Critical: All languages share exact ILI sequence.**

Grammar is constrained but correct:
- Tense preserved (was, is, will be)
- Quantity preserved (a, the, plural markers)
- Japanese particles present and untagged
- ILI order identical across all languages

Example:
```
# kimi-k2.5/merged/en.txt
<|ILI_73081|>Thraco-Phrygian <|ILI_025997|>was proposed as an 
<|ILI_005091|>extinct <|ILI_081247|>branch of the ...

# kimi-k2.5/merged/ja.txt  
<|ILI_73081|>トラキア・フリギア語族は<|ILI_025997|>提案された
<|ILI_005091|>死滅した<|ILI_081247|>分枝で、...
```

Both have same ILI count and order, though Japanese grammar differs.

## meta.json

```json
{
  "ili": 73081,
  "primary_model": "kimi-k2.5",
  "timestamp": "2026-03-15T15:00:00Z",
  "languages": ["en", "cz", "ja"],
  "models": {
    "kimi-k2.5": {
      "timestamp": "2026-03-15T15:00:00Z",
      "alignment_verified": true,
      "ilis_per_lang": {"en": 15, "cz": 15, "ja": 15}
    }
  },
  "validation": {
    "en_cz_ja_aligned": true,
    "all_langs_same_count": true,
    "all_langs_same_order": true
  }
}
```

## Validation

Run verification:
```bash
# Verify specific model
python skill/scripts/verify_alignment.py data/synsets/ili_XXXXX/MODEL_NAME

# Verify all models for an ILI
python skill/scripts/verify_alignment.py data/synsets/ili_XXXXX --all-models
```

This checks:
- Same ILI count per language
- Same ILI order across languages
- Reports mismatches

## Machine Learning Pipeline

Strip to ILI sequences only:
```bash
python skill/scripts/verify_alignment.py data/synsets/ili_XXXXX/kimi-k2.5 \
  --strip --output-dir ili_only/
```

Produces:
```
ili_only/
  en.ili    # <|ILI_73081|> <|ILI_025997|> <|ILI_005091|> ...
  cz.ili
  ja.ili
```

The residual (non-ILI text) can be processed separately for grammar learning.
