#!/usr/bin/env python3
"""Minimal Gemini smoke test to verify raw API behavior.

Usage examples:
  python scripts/test_gemini_minimal.py
  python scripts/test_gemini_minimal.py --json --print-response
  python scripts/test_gemini_minimal.py --model gemini-2.5-flash --max-output-tokens 1024
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

import google.generativeai as genai


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.config import load_config  # noqa: E402


def build_generation_config(cfg: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    dspy_cfg = cfg.get("dspy", {}) if isinstance(cfg, dict) else {}
    generation = {
        "temperature": args.temperature if args.temperature is not None else dspy_cfg.get("temperature", 0.9),
        "top_p": args.top_p if args.top_p is not None else dspy_cfg.get("top_p", 0.8),
        "top_k": args.top_k if args.top_k is not None else dspy_cfg.get("top_k", 40),
        "max_output_tokens": args.max_output_tokens if args.max_output_tokens is not None else dspy_cfg.get("max_output_tokens", 2048),
    }
    if args.json:
        generation["response_mime_type"] = "application/json"
    return generation


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal Gemini API smoke test")
    parser.add_argument("--model", default=None, help="Gemini model name")
    parser.add_argument("--prompt", default="請用 JSON 回答：{\"ok\": true}", help="Prompt to send")
    parser.add_argument("--prompt-file", default=None, help="Path to prompt text file")
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--top-p", type=float, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--max-output-tokens", type=int, default=None)
    parser.add_argument("--json", action="store_true", help="Force response_mime_type=application/json")
    parser.add_argument("--print-response", action="store_true", help="Print raw response text")
    args = parser.parse_args()

    cfg = load_config()
    api_key = cfg.get("google_api_key")
    if not api_key:
        raise SystemExit("Missing google_api_key in config/config.yaml or GOOGLE_API_KEY env")

    genai.configure(api_key=api_key)

    if args.prompt_file:
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            args.prompt = f.read()

    model_name = args.model or cfg.get("dspy", {}).get("model") or "gemini-3-flash-preview"
    generation_config = build_generation_config(cfg, args)

    print(f"Model: {model_name}")
    print(f"Generation config: {generation_config}")

    model = genai.GenerativeModel(model_name)
    response = model.generate_content(args.prompt, generation_config=generation_config)

    text = getattr(response, "text", "")
    candidates = getattr(response, "candidates", None) or []
    finish_reason = None
    if candidates:
        finish_reason = getattr(candidates[0], "finish_reason", None)

    print(f"Finish reason: {finish_reason}")
    print(f"Response length: {len(text)}")

    if args.print_response:
        print("Raw response:")
        print(text)

    if args.json:
        try:
            parsed = json.loads(text)
            print("JSON parse: OK")
            print(json.dumps(parsed, ensure_ascii=False, indent=2)[:1000])
        except Exception as exc:
            print(f"JSON parse: FAILED ({exc})")


if __name__ == "__main__":
    main()
