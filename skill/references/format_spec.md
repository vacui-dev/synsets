# ILI Sidecar Format Specification (v1)

## Token Format

```
<|ILI_NNNNNN|>
```

- `ILI_` prefix identifies this as an Interlingual Index concept token
- `NNNNNN` is the ILI integer ID, zero-padded to 6 digits
- Wrapped in `<|...|>` special token delimiters (compatible with most tokenizer conventions)

## ILI ID Source

ILI IDs come from the [Collaborative Interlingual Index (CILI)](https://github.com/globalwordnet/cili),
which assigns a unique integer to each WordNet synset (concept). These IDs are:

- **Language-neutral**: the same ID means the same concept in every language
- **Stable**: IDs do not change across WordNet versions
- **Public**: part of the open Global WordNet infrastructure
- **Unique**: one ID per concept (not per word -- polysemous words map to multiple IDs)

## Dataset JSON Format

```json
{
  "format": "ili-sidecar-v1",
  "description": "Text-to-ILI concept annotation pairs",
  "ili_vocab_size": 1234,
  "num_pairs": 5000,
  "pairs": [
    {
      "text": "The dog chased the cat up the tree",
      "annotated": "The <|ILI_046360|> <|ILI_059245|> the <|ILI_046593|> up the <|ILI_105570|>",
      "annotations": [
        {
          "span": "dog",
          "ili": 46360,
          "pos": "n",
          "gloss": "a member of the genus Canis..."
        }
      ]
    }
  ]
}
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `format` | string | Always `"ili-sidecar-v1"` |
| `ili_vocab_size` | int | Number of unique ILI concepts in this dataset |
| `num_pairs` | int | Number of text-annotation pairs |
| `pairs[].text` | string | Original text |
| `pairs[].annotated` | string | Text with content words replaced by ILI tokens |
| `pairs[].annotations` | array | Per-word annotation details |
| `annotations[].span` | string | The original surface form |
| `annotations[].ili` | int | The ILI concept ID (unpadded integer) |
| `annotations[].pos` | string | Part of speech: n (noun), v (verb), a (adjective), r (adverb) |
| `annotations[].gloss` | string | WordNet definition of the concept |

## JSONL Format

One JSON object per line, same fields as `pairs[]` above:

```jsonl
{"text": "...", "annotated": "...", "annotations": [...]}
{"text": "...", "annotated": "...", "annotations": [...]}
```

## Annotation Rules

1. **Content words only**: nouns, verbs, adjectives, adverbs
2. **Function words preserved**: determiners, prepositions, conjunctions, pronouns stay as text
3. **Sense disambiguation required**: "bank" (finance) vs "bank" (river) get different ILI IDs
4. **Inflected forms map to lemma ILI**: "running" -> ILI for "run", "dogs" -> ILI for "dog"
5. **Unknown words stay as text**: proper nouns, slang, and jargon without WordNet entries

## Using for Vocabulary Extension

```python
# 1. Collect unique ILI tokens from dataset
ili_tokens = {f"<|ILI_{ann['ili']:06d}|>" for pair in data['pairs'] for ann in pair['annotations']}

# 2. Add to tokenizer
tokenizer.add_tokens(sorted(ili_tokens))

# 3. Resize model embeddings
model.resize_token_embeddings(len(tokenizer))

# 4. Fine-tune on annotated text
# The model learns to predict ILI tokens in context,
# which is equivalent to learning word-sense disambiguation
```
