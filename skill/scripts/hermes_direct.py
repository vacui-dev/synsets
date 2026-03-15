#!/usr/bin/env python3
"""
Send a direct message to Hermes and save the response.
No conversation history — direct Hermes interaction.

Usage:
    python3 hermes_direct.py "Your message" --output response.txt
    python3 hermes_direct.py --file prompt.txt --output response.html
"""

import json
import os
import sys
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(SCRIPT_DIR, "..", "..", ".env")
API_URL = "https://inference-api.nousresearch.com/v1/chat/completions"
MODEL = "Hermes-4-405B"


def load_api_key() -> str:
    if os.environ.get("NOUS_API_KEY"):
        return os.environ["NOUS_API_KEY"]
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for line in f:
                if line.startswith("NOUS_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    print("ERROR: No API key", file=sys.stderr)
    sys.exit(1)


def call_hermes(messages: list[dict], max_tokens: int = 16384) -> str:
    api_key = load_api_key()
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "reasoning": True,
    }).encode()

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read())

    return result["choices"][0]["message"]["content"]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Send a direct message to Hermes")
    parser.add_argument("message", nargs="?", help="Message to send")
    parser.add_argument("--file", help="Read message from file")
    parser.add_argument("--output", "-o", help="Save response to file")
    parser.add_argument("--system", help="System prompt")
    parser.add_argument("--max-tokens", type=int, default=16384)
    parser.add_argument("--continue-from", help="Continue conversation from previous response file")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            message = f.read()
    elif args.message:
        message = args.message
    else:
        print("Provide a message or --file", file=sys.stderr)
        sys.exit(1)

    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})

    if args.continue_from and os.path.exists(args.continue_from):
        with open(args.continue_from) as f:
            prev = f.read()
        messages.append({"role": "assistant", "content": prev})

    messages.append({"role": "user", "content": message})

    print(f"Sending to Hermes ({len(message)} chars)...", file=sys.stderr)
    response = call_hermes(messages, max_tokens=args.max_tokens)
    print(f"Got response ({len(response)} chars)", file=sys.stderr)

    if args.output:
        with open(args.output, "w") as f:
            f.write(response)
        print(f"Saved to {args.output}", file=sys.stderr)
    else:
        print(response)


if __name__ == "__main__":
    main()
