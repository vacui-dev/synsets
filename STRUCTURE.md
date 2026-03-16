# Synset Data Structure v3.0

## Directory Layout

```
data/synsets/
  ili_XXXXXX/                    # One folder per ILI
    meta.json                    # Model, timestamp, validation
    MODEL_NAME/                  # e.g., kimi-k2.5, claude-sonnet-4
      natural/                   # Wikipedia-quality natural text
        en.txt                   # English (proper grammar)
        zh.txt                   # Chinese (proper grammar)
        ja.txt                   # Japanese (proper grammar)
      ili/                       # ILI-annotated versions
        en.txt                   # English with ILI tags
        zh.txt                   # Chinese with ILI tags
        ja.txt                   # Japanese with ILI tags
      merged/                    # Grammar-correct, ILI-aligned
        en.txt                   # English (function words untagged)
        zh.txt                   # Chinese (function words untagged)
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

# kimi-k2.5/merged/zh.txt
<|ILI_73081|>色雷斯-弗里吉亚语族<|ILI_025997|>被提议为一个
<|ILI_005091|>已灭绝的<|ILI_081247|>分支...
```

Both have same ILI count and order, though Japanese grammar differs.

## meta.json

```json
{
  "ili": 73081,
  "primary_model": "kimi-k2.5",
  "timestamp": "2026-03-15T15:00:00Z",
  "languages": ["en", "zh", "ja"],
  "models": {
    "kimi-k2.5": {
      "timestamp": "2026-03-15T15:00:00Z",
      "alignment_verified": true,
      "ilis_per_lang": {"en": 15, "zh": 15, "ja": 15}
    }
  },
  "validation": {
    "en_zh_ja_aligned": true,
    "all_langs_same_count": true,
    "all_langs_same_order": true
  }
}
```

## Validation Modes

Two verification modes to combat LLM laziness:

### Strict Mode (default)
All ILI counts must match exactly across languages.

```bash
python skill/scripts/verify_alignment.py ili_XXXXX/MODEL_NAME --mode strict
```

- If EN has ILI_12345 appearing 3 times, JA must also have it 3 times
- Fights LLM laziness where languages drop ILI repetitions
- Ensures complete semantic alignment
- Use when data quality is paramount

### Loose Mode
All unique ILIs must appear in all languages, counts may differ.

```bash
python skill/scripts/verify_alignment.py ili_XXXXX/MODEL_NAME --mode loose
```

- Allows language-specific expression differences
- If EN has 3 occurrences and JA has 1, that's acceptable
- Use when languages naturally express concepts differently
- Still ensures all concepts are covered

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
  zh.ili
  ja.ili
```

The residual (non-ILI text) can be processed separately for grammar learning.
