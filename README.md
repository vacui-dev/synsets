# Synsets — Autonomous ILI Annotation with Hermes-4-405B

[![License: MOSL v2.0](https://img.shields.io/badge/License-MOSL%20v2.0-blue)](https://github.com/vacui-dev/synsets/blob/main/LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/vacui-dev/synsets)](https://github.com/vacui-dev/synsets/commits/main)

**Built for the [Nous Research Hermes Agent Hackathon 2026](https://nousresearch.com)**

Synsets is a tool that uses **Hermes-4-405B** as an autonomous agent to annotate text with [Interlingual Index](https://cili.globalwordnet.org/) (ILI) identifiers from WordNet. Hermes calls tools against a local **WordNet MCP server**, performs word sense disambiguation in context, and produces annotated text where every content word is linked to a language-neutral concept ID.

## How It Works

```
┌─────────────────────────────────────────────────────┐
│  Hermes-4-405B (via Nous Inference API)             │
│  ┌───────────────────────────────────────────────┐  │
│  │  System prompt: "You are an ILI annotator.    │  │
│  │  For EVERY content word, call a tool first.   │  │
│  │  Never guess an ILI ID from memory."          │  │
│  └───────────────────┬───────────────────────────┘  │
│                      │ tool_calls                    │
│                      ▼                               │
│  ┌─────────────────────────────────────────────┐    │
│  │  Tool Execution Loop                        │    │
│  │  1. Hermes emits tool_call (lookup_word)    │    │
│  │  2. Local executor runs query against MCP   │    │
│  │  3. Results returned as tool message        │    │
│  │  4. Repeat until Hermes returns final text  │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  WordNet MCP Server (localhost:8741)                 │
│                                                     │
│  GET /lookup?word=represent&pos=v                    │
│  GET /phrase?words=orange+juice                      │
│  GET /synset?ili=i35152                              │
│  GET /search?q=financial+institution                 │
│  GET /health                                        │
│                                                     │
│  SQLite backend: 120K synsets, 117K ILI mappings    │
│  Auto-lemmatization: -s, -ed, -ing, -ies, -ly, etc │
│  Threaded HTTP server, persistent DB connection     │
└─────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│  Output: JSONL with per-word ILI assignments        │
│                                                     │
│  {                                                  │
│    "record_num": 42,                                │
│    "original_text": "The concept of realm ...",     │
│    "retranslated_text": "The <|i67543|> of ...",    │
│    "assignments": [                                 │
│      {"word":"concept","ili":67543,"pos":"n",       │
│       "definition":"an abstract or general idea"}   │
│    ]                                                │
│  }                                                  │
└─────────────────────────────────────────────────────┘
```

## What is ILI?

The **Interlingual Index** (ILI) provides language-neutral concept IDs from the [Collaborative Interlingual Index](https://cili.globalwordnet.org/) (CILI). Each ILI ID maps to a WordNet synset — a group of words sharing the same meaning. ILI IDs are stable across languages: `i67543` means "an abstract or general idea" whether you're working in English, Dutch, Japanese, or any other language with a linked WordNet.

This makes ILI-annotated text a bridge between natural language and structured semantics. The same annotated corpus can be used for:
- Cross-lingual NLP (word sense alignment across languages)
- Semantic search (query by concept, not surface form)
- Training data for word sense disambiguation models
- Knowledge graph construction

## Beyond Annotation: Concept-Based Tokenization

Current LLM tokenizers (BPE, SentencePiece) encode **co-occurrence patterns**, not meaning. "Bank" always gets the same token ID whether it means a financial institution or a riverbank. The embedding layer flattens every type of relationship — semantic, brand, metaphorical — into a single vector, and attention has to sort it out. This is a [documented problem](https://aclanthology.org/2024.emnlp-main.272.pdf): "Azure" is closer to "Microsoft" than to "blue" in most model embedding spaces. "Apple" is closer to "iPhone" than to "fruit."

ILI solves this at the vocabulary level. Each concept gets a unique token: `bank (financial)` and `bank (river)` are different IDs, not the same token requiring disambiguation. ~120K language-neutral concepts, already mapped across 50+ languages via WordNet's [Collaborative Interlingual Index](https://cili.globalwordnet.org/). A model trained on ILI-tokenized text would have semantic grounding that BPE cannot provide — and it would be inherently multilingual, since the same concept ID works regardless of input language.

**This tool builds the training data.** Hermes-4-405B autonomously disambiguates every content word against WordNet, producing ILI-annotated text at scale. The disambiguation cost is paid once at data generation time, not per token at inference. Almost nobody has tried using ILI as a model vocabulary — the [wordnet community](https://cili.globalwordnet.org/) uses it for dataset linking, not model training. This project bridges that gap.

## The MCP Server

The core infrastructure piece is a **WordNet MCP server** that exposes the full English WordNet as REST endpoints:

```bash
# Start the server
python3 skill/scripts/wordnet_mcp_server.py

# Endpoints
curl "http://localhost:8741/lookup?word=bank&pos=n"     # All noun senses of "bank"
curl "http://localhost:8741/phrase?words=credit+card"    # Multi-word expressions
curl "http://localhost:8741/synset?ili=i35152"           # Full synset details + relations
curl "http://localhost:8741/search?q=financial+body"     # Search definitions
curl "http://localhost:8741/health"                      # Server status
```

The server loads the WordNet SQLite database once, holds it in memory with WAL mode and 64MB cache, and handles concurrent requests via threading. It auto-lemmatizes queries (stripping `-s`, `-ed`, `-ing`, `-ies`, `-ly`, `-ness`, `-ment` suffixes) so inflected forms resolve correctly.

Any MCP-compatible agent can connect to this server — it's a general-purpose WordNet API, not Hermes-specific.

## How Hermes Uses Tools

Hermes-4-405B's tool-use capabilities drive the annotation pipeline. The system prompt forces tool usage:

> *"You MUST call `lookup_word` for EVERY content word before assigning an ILI ID. You WILL hallucinate ILI IDs if you try to produce them from memory. Do NOT assign any ILI without first receiving tool results."*

The tool-use loop:
1. **Hermes receives text** and a list of 3 tools (`lookup_word`, `lookup_phrase`, `search_definition`)
2. **Hermes emits `tool_calls`** — typically 5-15 calls per text passage, batching related lookups
3. **Local executor** forwards each call to the MCP server and returns results
4. **Hermes reads results**, disambiguates senses using context, and emits the final annotated text with ILI tokens

This architecture means **every ILI ID is traceable** to a specific WordNet tool call. Zero hallucination — if WordNet doesn't have a sense for a word, Hermes skips it rather than guessing.

## Real Example

**Input:** `"The concept of realm boundaries challenges imagination"`

**Tool calls by Hermes:**
```
lookup_word("concept", pos="n")    → i67543: "an abstract or general idea..."
lookup_word("realm", pos="n")      → i113279: "a domain in which something is dominant"
lookup_word("boundaries", pos="n") → i81782: "the line or plane indicating the limit..."
lookup_word("challenges", pos="v") → [skipped — ambiguous in context]
lookup_word("imagination", pos="n")→ i66470: "the formation of a mental image..."
```

**Output:**
```
The <|i67543|>concept of <|i113279|>realm <|i81782|>boundaries challenges <|i66470|>imagination
```

## Quick Start

```bash
# 1. Install WordNet database
python3 -c 'import wn; wn.download("ewn:2020")'

# 2. Set your API key
echo "NOUS_API_KEY=your_key" > .env

# 3. Start the MCP server
python3 skill/scripts/wordnet_mcp_server.py &

# 4. Run annotation (single record)
python3 skill/scripts/hermes_tool_use.py --record 0 --limit 50

# 5. Run batch annotation (parallelized)
python3 skill/scripts/hermes_tool_use.py --batch --start 0 --count 100

# 6. View results — open index.html in a browser
```

## Interactive Explorer

Open [`index.html`](index.html) in a browser to explore annotated text. Every content word is clickable — click any word to see its ILI ID, part of speech, and WordNet definition. Arrow keys navigate between records. Supports search, export, and dark mode.

## Data Methodology

The included dataset was produced in two stages:

1. **Confidence-based pre-processing**: An initial pass assigned ILI tokens to high-confidence words using direct WordNet lookup with lemmatization. This produced partially-annotated text where ~51 ILIs per record were assigned automatically based on exact and lemmatized matches. No disambiguation was performed — ambiguous words were left as plaintext.

2. **Hermes tool-use annotation**: Hermes-4-405B received each partially-annotated record and used WordNet tool calls to disambiguate and assign ILIs to the remaining content words (~46 additional ILIs per record). Hermes performs actual word sense disambiguation — reading all candidate senses from WordNet and selecting the correct one based on surrounding context.

The merged output (`data/synsets_annotated.jsonl`) includes both `human_text` (fully readable English) and per-word `assignments` from Hermes. Each record tracks `preexisting_ili_count` vs `hermes_ili_count` so you can see exactly which ILIs came from which method.

**We encourage re-generating the data** rather than reusing ours. The MCP server and annotation pipeline are the contribution — the included data is a demonstration, not a finished dataset.

## Project Structure

```
skill/
  scripts/
    hermes_tool_use.py         # Hermes tool-use annotation pipeline
    wordnet_mcp_server.py      # WordNet MCP server (REST API)
    merge_results.py           # Post-processing: merge, deduplicate, humanize
    hermes_direct.py           # Direct Hermes messaging utility
  SKILL.md                     # Hermes Agent skill specification
data/
  synsets_annotated.jsonl      # Merged output (human-readable + assignments)
  stats.json                   # Summary statistics
  retranslated_batch_*.jsonl   # Raw batch worker output
index.html                     # Interactive web explorer
```

## Built With Hermes

This project demonstrates Hermes-4-405B's autonomous agent capabilities:

- **Tool use**: Hermes calls 3 custom tools against a local WordNet MCP server, making 5-15 tool calls per text passage to look up every content word
- **Word sense disambiguation**: Hermes reads all candidate senses returned by WordNet and selects the correct one based on surrounding context
- **Batch autonomy**: Each record is processed end-to-end by Hermes with no human intervention — Hermes decides which tools to call, how many rounds of lookup to perform, and when it has enough information to assign final ILI IDs
- **Zero hallucination by design**: The system prompt and tool architecture ensure Hermes never assigns an ILI ID without first receiving it from a tool call. If WordNet doesn't have an entry, Hermes skips the word
- **Skill specification**: The [`SKILL.md`](skill/SKILL.md) file defines the annotation workflow in Hermes Agent skill format

## License

[MOSL v2.0](LICENSE) (Mandatory Open Source License) — See [LICENSE](LICENSE)

Forks and branches are encouraged. Contributions submitted to this repository grant the Author additional usage rights per the Contributor License (Section 4).
