# Synsets — Concept-Based Tokenization for Language Models

[![License: MOSL v2.0](https://img.shields.io/badge/License-MOSL%20v2.0-blue)](https://github.com/vacui-dev/synsets/blob/main/LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/vacui-dev/synsets)](https://github.com/vacui-dev/synsets/commits/main)

**Built for the [Nous Research Hermes Agent Hackathon 2026](https://nousresearch.com)** 
Designed to be integrated with the **Hermes Agent IDE**. All project commits after the initial foundation were generated autonomously by the Hermes Agent.

[![](http://img.youtube.com/vi/PLACEHOLDER/0.jpg)](https://www.youtube.com/watch?v=PLACEHOLDER)
_Watch the development of this repository._
(Initial foundation created with [Claude Code](https://github.com/anthropics/claude-code)).

---

## The Problem

Every LLM in production today tokenizes text the same way: BPE or SentencePiece, trained on byte-level co-occurrence statistics. These algorithms are agnostic to meaning. "Bank" gets one token whether it's a riverbank or a financial institution. "Apple" is closer to "iPhone" than to "fruit" in embedding space. "Azure" vectors toward "Microsoft," not "blue."

This is a [documented, measurable problem](https://aclanthology.org/2024.emnlp-main.272.pdf). But it's worse than the paper shows — it's not just that embeddings are polluted. It's that **every transformer layer** must re-derive meaning from context, burning attention on a problem that could be solved once at tokenization. The model's finite compute is spent on disambiguation instead of reasoning.

Current models think like this:

```
"The bank approved the loan"
 → [bank] → embedding is ambiguous
 → layer 1: attends to "loan" → maybe financial?
 → layer 2: attends to "approved" → probably financial
 → layer 3: confident it's financial institution
 → ...model can now start actual reasoning
```

Three layers of attention, just to figure out which "bank" this is. Multiply by every content word, every sentence, every forward pass.

## The Solution

**Interlingual Index (ILI)** concept IDs from [CILI](https://cili.globalwordnet.org/) (Collaborative Interlingual Index) provide ~120K language-neutral concept identifiers, each mapped to a WordNet synset. Every concept gets a unique token:

```
bank (financial) → ILI_092258
bank (river)     → ILI_092416
bank (rely on)   → ILI_017203
```

A model trained on ILI-annotated text receives pre-disambiguated input. The meaning is in the vocabulary. Attention is freed for actual reasoning — inference, planning, composition — rather than spent on the tax of ambiguity.

```
"The <|ILI_092258|> approved the loan"
 → [ILI_092258] → embedding is unambiguous (financial institution)
 → layer 1: already knows the meaning → moves to reasoning
```

One layer instead of three. Across a 96-layer model, that's an enormous amount of reclaimed compute.

## What This Project Does

Synsets is an autonomous pipeline that uses an agent to produce ILI-annotated training data at scale. The agent:

1. Receives raw text
2. Calls tools against a local **WordNet MCP server** to look up every content word
3. Performs word sense disambiguation using context
4. Outputs text where every content word carries its ILI concept ID

The key architectural choice: **the disambiguation cost is paid once at data generation time, not per token at inference.** We use an agentic workflow to produce training data for models that will inherit disambiguated representations.

```
┌─────────────────────────────────────────────────────────┐
│  Hermes-4-405B Agent                                    │
│                                                         │
│  System: "You MUST call lookup_word for EVERY content   │
│  word. You WILL hallucinate ILI IDs from memory.        │
│  USE THE TOOLS."                                        │
│                                                         │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────┐  │
│  │ lookup_word │───→│ WordNet MCP  │───→│ ILI senses │  │
│  │ "bank"      │    │ Server       │    │ returned   │  │
│  └─────────────┘    └──────────────┘    └────────────┘  │
│         │                                    │          │
│         └──────── context ───────────────────┘          │
│                        │                                │
│                        ▼                                │
│              Disambiguated ILI assignment               │
│              bank → ILI_092258 (financial)              │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
              ILI-annotated training corpus
              (120K concepts, 50+ languages)
```

## Why This Matters

**For model architecture:** ILI tokens collapse the distinction between "knowing a word" and "knowing a concept." A model trained on ILI text learns concept-level representations directly. The embedding layer becomes a concept space, not a subword soup. This is the difference between learning statistics and learning meaning.

**For multilinguality:** ILI IDs are language-neutral. `ILI_092258` means "financial institution" in English, Chinese, Japanese, Arabic, and 46 other languages with linked WordNets. A model with ILI tokens in its vocabulary is inherently multilingual — the concept space doesn't need to be learned separately per language.

**For reasoning:** Disambiguation is a necessary precondition for reasoning. A model that must disambiguate "bank" before it can reason about finances is doing two tasks. ILI separates these concerns: disambiguation at the data layer, reasoning at the model layer.

**For the field:** Nobody has seriously tried this. The WordNet community uses ILI for dataset linking. The ML community uses BPE because it works well enough. This project bridges the gap — producing the training data that makes concept-based tokenization experimentally accessible.

## The MCP Server

A local WordNet server exposes the full English WordNet via the Model Context Protocol:

```bash
# Start
python3 skill/scripts/wordnet_mcp_server.py

# Or use stdio transport (for Hermes Agent integration)
python3 skill/scripts/wordnet_mcp_server_stdio.py
```

**HTTP Endpoints:**
```
GET /lookup?word=bank&pos=n          → all noun senses of "bank"
GET /phrase?words=credit+card         → multi-word expressions
GET /synset?ili=i92258                → full synset + relations
GET /search?q=financial+institution   → definition search
GET /health                           → server status
```

**MCP Tools (stdio):**
- `lookup_word(word, pos?)` — all senses for a word
- `lookup_phrase(words)` — multi-word expression lookup
- `get_synset(ili)` — synset details by ILI ID
- `search_definitions(query)` — search by concept description

The server loads the WordNet SQLite database (~120K synsets, ~117K ILI mappings) once, holds it in memory with WAL mode and 64MB cache, and handles concurrent requests via threading. Auto-lemmatization strips `-s`, `-ed`, `-ing`, `-ies`, `-ly`, `-ness`, `-ment` so inflected forms resolve correctly.

Any MCP-compatible agent can connect. Not Hermes-specific.

## Quick Start

```bash
# 1. Install WordNet database
python3 -c 'import wn; wn.download("ewn:2020")'

# 2. Set API key
echo "NOUS_API_KEY=sk-..." > .env

# 3. Start MCP server
python3 skill/scripts/wordnet_mcp_server.py &

# 4. Annotate a single record
python3 skill/scripts/hermes_tool_use.py --record 0 --limit 50

# 5. Batch annotation
python3 skill/scripts/hermes_tool_use.py --batch --start 0 --count 100

# 6. Validate output
python3 skill/scripts/validate.py data/retranslated_v1.jsonl

# 7. View results
open index.html
```

## Data Methodology

The pipeline uses a strict two-pass architecture:

### Pass 1: Natural Definitions (No ILI Awareness)

The model writes Wikipedia-quality definitions in English, Chinese, and Japanese from its own knowledge. It has NO access to WordNet, ILI IDs, or synset information during this pass. This keeps the encyclopedic knowledge pure — untainted by the particularities of synset structure.

### Pass 2: ILI Annotation (Post-Processing)

The model receives the natural definitions from Pass 1 plus a pre-computed WordNet sense table for every content word. It annotates content words with ILI tags: `<|ILI_NNNNNN|>word`. Function words (determiners, prepositions, particles, auxiliaries) remain untagged.

**Why two passes?** Synset information should be pure post-processing. If a model writes a definition while simultaneously thinking about ILI IDs, the synset structure leaks into the prose — definitions start mirroring WordNet's phrasing rather than reflecting genuine encyclopedic knowledge. Separation of concerns produces better data on both sides.

### Batch Mode (Advanced Models)

The `batch_generate.py` script processes multiple ILIs in parallel:
- All WordNet lookups happen in one batch (not word-by-word)
- All definitions generated in one pass (not sentence-by-sentence)
- All annotations applied in one pass (not ILI-by-ILI)

This is designed for models that can handle large context windows and parallel tool calls. Dumber models need hand-holding (one ILI, one sentence, one tool call at a time). Advanced models can handle 10+ ILIs × 3 languages × all tool lookups in a single shot.

```bash
# Batch generate 10 ILIs
python skill/scripts/batch_generate.py --count 10

# Specific range
python skill/scripts/batch_generate.py --start 1000 --count 20
```

**Generate your own data.** The MCP server and annotation pipeline are the contribution. The included data is a demonstration, not a finished dataset.

## Multilingual Synset Generation

The `data/synsets/` directory contains multilingual (English, Chinese, Japanese) ILI-annotated definitions generated via parallel autonomous agents. Each ILI gets a directory:

```
data/synsets/ili_XXXXXX/
  meta.json                          # ILI metadata, validation, model info
  MODEL_NAME/                        # e.g., kimi-k2.5, claude-opus-4.6
    natural/
      en.txt                         # English definition
      zh.txt                         # Chinese definition
      ja.txt                         # Japanese definition
    ili/
      en.txt                         # English with ILI tags
      zh.txt                         # Chinese with ILI tags
      ja.txt                         # Japanese with ILI tags
    merged/
      en.txt                         # Grammar-correct, ILI-aligned
      zh.txt                         # Grammar-correct, ILI-aligned
      ja.txt                         # Grammar-correct, ILI-aligned
```

Languages use ISO 639-1 codes: `en` (English), `zh` (Chinese), `ja` (Japanese).

## Architecture

```
skill/
  scripts/
    common.py                  # Shared utilities (stopwords, lemmatizer, DB, ILI patterns)
    batch_generate.py          # Two-pass batch synset generator (advanced models)
    hermes_tool_use.py         # Main annotation pipeline (tool-use loop)
    wordnet_mcp_server.py      # HTTP MCP server
    wordnet_mcp_server_stdio.py# stdio MCP server (for agent integration)
    merge_results.py           # Post-processing: merge, deduplicate, humanize
    validate.py                # Quality assurance: ILI existence + POS matching
    reconstruct.py             # Sentence-by-sentence refinement pass
    hermes_annotate.py         # Alternative: Hermes does WSD, then WordNet resolution
    hermes_disambiguate.py     # Alternative: batch disambiguation
    hermes_disambiguate_v2.py  # Alternative: local candidates + Hermes picks
    hermes_direct.py           # Direct Hermes messaging utility
    ili_lookup.py              # WordNet lookup via wn package
    extract_gaps.py            # Extract content words from ILI gaps
    filter_core.py             # Filter to core 9,461 well-defined concepts
    compress_ili.py            # .cili format encoder/decoder
    convert_synset_corpus.py   # Convert synset files to dataset format
    batch_convert.py           # Batch plaintext → ILI annotation
    verify_alignment.py        # Verify multilingual ILI alignment
    ili_annotate_workflow.py   # Hermes Agent native workflow
  SKILL.md                     # Hermes Agent skill specification
  references/
    format_spec.md             # ILI sidecar format specification
    golden_examples.json       # Human-verified annotation examples
  workflows/
    generate_synset_v*.py      # Multilingual synset generation workflows
    annotate_text.yaml         # Text annotation workflow spec
scripts/                        # Utility scripts (root-level, not part of skill)
  check_ili.py                 # ILI validation helpers
  find_ili.py                  # ILI search utilities
  lookup_*.py                  # Various lookup scripts
  process_batch_*.py           # Batch processing scripts
data/
  synsets/                     # Multilingual ILI definitions
  synsets_annotated.jsonl      # Merged annotation output
  stats.json                   # Summary statistics
index.html                     # Interactive web explorer
```

## What's Next

1. **Train a model on ILI text.** The data exists. The question is whether a transformer trained on concept-tokenized text learns different representations — and whether those representations transfer better across languages.

2. **Expand languages.** ILI is mapped to WordNets in 50+ languages. The pipeline supports any language — just point it at a different WordNet.

3. **Scale annotation.** The included corpus is ~200 records. The pipeline can process thousands in parallel. Hermes handles the disambiguation; you provide the text.

4. **Hybrid tokenization.** ILI tokens for content words, BPE for function words and morphology. Best of both worlds — disambiguated concepts where it matters, subword flexibility where it doesn't.

## Built With

- **Autonomous Agentic Workflows** — for word sense disambiguation
- **WordNet / CILI** — 120K synsets, 117K ILI mappings, 50+ languages
- **MCP (Model Context Protocol)** — standard tool interface for agents
- **Inference API** — agent hosting

## License

[MOSL v2.0](LICENSE) (Mandatory Open Source License). Forks and branches encouraged. Contributions grant the Author additional usage rights per Section 4.

---

*The tokenizer is the bottleneck. This is how we break it.*
