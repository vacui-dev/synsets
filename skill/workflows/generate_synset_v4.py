#!/usr/bin/env python3
"""
Synset Generation Driver v4 - True Multilingual Edition

Generates each language INDEPENDENTLY with language-specific prompts
and native WordNet lookups (no English bias).

Usage:
    python generate_synset_v4.py [--ili N] [--langs en,cz,ja]
"""

import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
from datetime import datetime

LANGUAGES = {
    'en': {'name': 'English', 'prompt_lang': 'English', 'wordnet': 'ewn:2020'},
    'cz': {'name': 'Chinese', 'prompt_lang': 'Chinese', 'wordnet': 'omw-zh:1.3'},
    'ja': {'name': 'Japanese', 'prompt_lang': 'Japanese', 'wordnet': 'omw-ja:1.3'},
}


def get_model_info():
    """Get current model from Hermes config."""
    try:
        result = subprocess.run(
            ['grep', 'default:', '/home/ubt18/.hermes/config.yaml'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip().split(':')[-1].strip()
    except:
        pass
    return "unknown"


def get_next_ili():
    """Get next unprocessed ILI."""
    data_dir = "/home/ubt18/synsets/data/synsets"
    existing = set()
    if os.path.exists(data_dir):
        for d in os.listdir(data_dir):
            if d.startswith("ili_"):
                try:
                    existing.add(int(d.split("_")[1]))
                except:
                    pass
    
    attempts = 0
    while attempts < 1000:
        ili = random.randint(1, 117480)
        if ili not in existing:
            return ili
        attempts += 1
    
    for i in range(1, 117481):
        if i not in existing:
            return i
    return None


def invoke_hermes_for_language(ili_num: int, model: str, lang_code: str, lang_config: dict):
    """Generate ONE language independently with native-language prompt."""
    
    lang_name = lang_config['name']
    prompt_lang = lang_config['prompt_lang']
    wordnet_id = lang_config['wordnet']
    
    # Prompt is in the TARGET LANGUAGE to avoid English bias
    prompts = {
        'en': f"""Generate English definition for synset ILI {ili_num}.

Research: Use mcp_wordnet_get_synset(ili="i{ili_num}") with English WordNet.

Write: english.txt
- Wikipedia-quality definition in NATURAL ENGLISH
- 3-5 sentences covering: what it is, context, usage, relationships
- Do NOT translate from another language - write directly in English
- Use English grammatical patterns naturally

Then annotate: english_ili.txt
- Tag content words with ILI using mcp_wordnet_lookup_word
- Format: <|ILI_NNNNN|>word
- Do NOT tag: the, a, an, is, of, in, and, or, to, etc.

Location: data/synsets/ili_{ili_num}/{model}/natural/en.txt
           data/synsets/ili_{ili_num}/{model}/ili/en.txt""",

        'cz': f"""为同义词集 ILI {ili_num} 生成中文定义。

研究：使用 mcp_wordnet_get_synset(ili="i{ili_num}") 查询中文WordNet。

撰写：chinese.txt
- 维基百科质量的中文定义
- 3-5句话，涵盖：是什么、上下文、用法、关系
- 不要从其他语言翻译——直接用中文写作
- 自然使用中文语法和表达习惯

然后标注：chinese_ili.txt
- 使用 mcp_wordnet_lookup_word 为实词标注ILI
- 格式： <|ILI_NNNNN|>词
- 不要标注：的、了、在、和、或、与等虚词

位置：data/synsets/ili_{ili_num}/{model}/natural/cz.txt
      data/synsets/ili_{ili_num}/{model}/ili/cz.txt""",

        'ja': f"""同義語セット ILI {ili_num} の日本語定義を生成します。

調査：mcp_wordnet_get_synset(ili="i{ili_num}") で日本語WordNetを使用。

作成：japanese.txt
- ウィキペディア品質の日本語定義
- 3-5文で：何か、文脈、使い方、関連性を説明
- 他の言語から翻訳しない——直接日本語で書く
- 自然な日本語の文法パターンを使用

次に注釈：japanese_ili.txt
- mcp_wordnet_lookup_word で内容語にILIを付与
- 形式： <|ILI_NNNNN|>単語
- 付与しない：は、を、が、に、で、と、のなどの助詞

場所：data/synsets/ili_{ili_num}/{model}/natural/ja.txt
      data/synsets/ili_{ili_num}/{model}/ili/ja.txt""",
    }
    
    prompt = prompts.get(lang_code, prompts['en'])
    
    result = subprocess.run(
        ['hermes', 'chat', '--yolo', '--query', prompt],
        capture_output=True,
        text=True,
        timeout=300
    )
    
    print(f"[{lang_name}] {result.stdout[-500:] if len(result.stdout) > 500 else result.stdout}")
    if result.stderr:
        print(f"[{lang_name} STDERR] {result.stderr}", file=sys.stderr)
    
    return result.returncode == 0


def create_merged_aligned(ili_num: int, model: str, langs: list):
    """Create merged/aligned versions from independently generated content."""
    
    base_dir = f"/home/ubt18/synsets/data/synsets/ili_{ili_num}/{model}"
    
    # Read all language ILI files
    lang_ili_content = {}
    for lang in langs:
        ili_path = f"{base_dir}/ili/{lang}.txt"
        if os.path.exists(ili_path):
            with open(ili_path, 'r', encoding='utf-8') as f:
                lang_ili_content[lang] = f.read()
    
    if len(lang_ili_content) < 2:
        print("Not enough languages for alignment")
        return False
    
    # For now, copy ILI files to merged (they're already aligned if generation worked)
    # In strict mode, we'd need to verify/reconcile counts
    os.makedirs(f"{base_dir}/merged", exist_ok=True)
    
    for lang, content in lang_ili_content.items():
        merged_path = f"{base_dir}/merged/{lang}.txt"
        with open(merged_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ili', type=int, help='Specific ILI')
    parser.add_argument('--langs', default='en,cz,ja', help='Languages (comma-separated)')
    parser.add_argument('--model', help='Model override')
    parser.add_argument('--parallel', action='store_true', help='Generate languages in parallel')
    args = parser.parse_args()
    
    model = args.model or get_model_info()
    langs = args.langs.split(',')
    
    if args.ili:
        ili = args.ili
    else:
        ili = get_next_ili()
    
    if not ili:
        print("All ILIs processed!")
        return
    
    print(f"Processing ILI {ili} with model {model}")
    print(f"Languages: {langs} (independent generation)")
    
    # Create directories
    base_dir = f"/home/ubt18/synsets/data/synsets/ili_{ili}/{model}"
    for subdir in ['natural', 'ili', 'merged']:
        for lang in langs:
            os.makedirs(f"{base_dir}/{subdir}", exist_ok=True)
    
    # Generate each language INDEPENDENTLY
    results = {}
    
    if args.parallel:
        # TODO: Actually implement parallel execution
        pass
    else:
        # Sequential generation
        for lang in langs:
            if lang not in LANGUAGES:
                print(f"Unknown language: {lang}")
                continue
            
            print(f"\n{'='*60}")
            print(f"Generating {LANGUAGES[lang]['name']}...")
            print(f"{'='*60}")
            
            success = invoke_hermes_for_language(ili, model, lang, LANGUAGES[lang])
            results[lang] = success
    
    # Create merged versions
    if all(results.values()):
        print("\nCreating merged/aligned versions...")
        create_merged_aligned(ili, model, langs)
        
        # Validate
        result = subprocess.run(
            ['python3', '/home/ubt18/synsets/skill/scripts/verify_alignment.py',
             f'{base_dir}', '--mode', 'strict'],
            capture_output=True, text=True
        )
        print(result.stdout)
        
        if result.returncode == 0:
            # Metadata
            meta = {
                "ili": ili,
                "model": model,
                "timestamp": datetime.now().isoformat(),
                "languages": langs,
                "generation_method": "independent_per_language",
                "verification": "strict"
            }
            
            with open(f"/home/ubt18/synsets/data/synsets/ili_{ili}/meta.json", 'w') as f:
                json.dump(meta, f, indent=2)
            
            # Commit
            subprocess.run(['git', '-C', '/home/ubt18/synsets', 'add', 
                          f'data/synsets/ili_{ili}/'])
            subprocess.run(['git', '-C', '/home/ubt18/synsets', 'commit', '-m',
                          f'Add synset ILI {ili} [{model}] v4-independent'])
            print(f"✓ Completed ILI {ili}")
        else:
            print(f"⚠ ILI {ili} needs alignment fixes")
    else:
        failed = [l for l, s in results.items() if not s]
        print(f"✗ Failed languages: {failed}")


if __name__ == "__main__":
    main()
