---
skill: synsets
tags:
- annotation
- wordnet
- ili
- wsd
author: Hermes
gaia:
  id: 
  namespace: 
license: MOSL-2.0
endorsements:
- skill: text-annotation
version: 1.0.0
skill_icon: 📚
cost: 1
custom:
  mcp_server: http://localhost:8741
  ili_format: "<|ILI_NNNNNN|>"
  ili_internal_format: "<|iNNNNN|>"
  content_word_pos: [n, v, a, r]
  function_word_pos: [u]
dependencies:
- type: mcp
  name: wordnet-server
  version: 1.0.0
input:
  type: text
  description: Text to annotate with ILI tokens
output:
  type: text
  description: Annotated text with ILI tokens inserted
examples:
- input: "The cat sat on the mat."
  output: "The <|ILI_N017004|> sat <|ILI_N029597|> the mat."
- input: "She represents the company."
  output: "She <|ILI_V019040|> the company."
---

# ILI Annotator Skill

This skill annotates text with Interlingual Index (ILI) tokens from WordNet/CILI using a local MCP server.

## What is ILI?

The Interlingual Index provides language-neutral concept IDs that link equivalent synsets across different WordNets. ILI IDs follow the format `ILI_NNNNNN` where NNNNNN is a zero-padded 6-digit number.

## Prerequisites

1. Ensure the WordNet MCP server is running at `http://localhost:8741`
2. Check server status:
   ```bash
   curl http://localhost:8741/health
   ```

## Native Hermes Agent Integration

This skill can be used natively within Hermes Agent via the MCP server:

1. Configure the MCP server in `~/.hermes/config.yaml`:
   ```yaml
   mcp_servers:
     wordnet:
       command: "python3"
       args: ["/path/to/synsets/skill/scripts/wordnet_mcp_server_stdio.py"]
   ```

2. Restart Hermes Agent - the wordnet tools will be auto-discovered

3. Use the annotation workflow:
   ```
   @hermes annotate this text with ILI identifiers: "The cat sat on the mat"
   ```

When running natively, Hermes calls these MCP tools directly:
- `mcp_wordnet_lookup_word` - Look up word senses
- `mcp_wordnet_lookup_phrase` - Multi-word expressions  
- `mcp_wordnet_get_synset` - Synset details by ILI
- `mcp_wordnet_search_definitions` - Search definitions

## Standalone Annotation Process

### Step 1: Tokenization and POS Tagging
First, tokenize the input text and identify content words (nouns, verbs, adjectives, adverbs) that need ILI annotation. Function words (articles, prepositions, pronouns) remain as plaintext.

### Step 2: Word Sense Disambiguation (WSD)
For each content word:
1. Look up all possible senses using the MCP server:
   ```bash
   curl "http://localhost:8741/lookup?word=represent&pos=v"
   ```
2. Use context to disambiguate and select the most appropriate sense

### Step 3: ILI Assignment
1. Get the synset details for the selected sense:
   ```bash
   curl "http://localhost:8741/synset?ili=i35152"
   ```
2. Extract the ILI ID from the response
3. Insert the ILI token using the format `<|ILI_NNNNNN|>`

### Step 4: Multi-word Expressions
For compound expressions like "orange juice":
```bash
curl "http://localhost:8741/phrase?words=orange+juice"
```

## Workflow Example

**Input:** "The cat sat on the mat."

1. Tokenize and identify content words:
   - cat (noun)
   - sat (verb)
   - mat (noun)

2. Disambiguate senses:
   ```bash
   curl "http://localhost:8741/lookup?word=cat&pos=n"
   # Select synset i017004 (feline mammal)
   
   curl "http://localhost:8741/lookup?word=sat&pos=v"
   # Select synset i019040 (be seated)
   
   curl "http://localhost:8741/lookup?word=mat&pos=n"
   # Select synset i029597 (floor covering)
   ```

3. Get synset details and extract ILI IDs:
   ```bash
   curl "http://localhost:8741/synset?ili=i017004"  # Returns ILI_N017004
   curl "http://localhost:8741/synset?ili=i019040"  # Returns ILI_V019040
   curl "http://localhost:8741/synset?ili=i029597"  # Returns ILI_N029597
   ```

4. Generate annotated output:
   ```
   The <|ILI_N017004|> <|ILI_V019040|> on the <|ILI_N029597|>.
   ```

## Important Notes

1. Always look up every content word - never guess or hallucinate ILI IDs
2. Use context carefully for word sense disambiguation
3. Maintain the original sentence structure with ILI tokens inserted
4. Check the MCP server health regularly:
   ```bash
   curl http://localhost:8741/health
   ```

## Search Functionality

You can also search for synsets by keywords in definitions:
```bash
curl "http://localhost:8741/search?q=financial+institution"
```

This skill provides a robust way to add semantic annotation to text using standardized ILI identifiers from WordNet.