#!/usr/bin/env python3
"""
Minimal Gemini call with a single prompt string.

This bypasses all project layers and sends exactly one text prompt to the
model, mimicking how our provider concatenates messages into plain text
(e.g., "시스템: ...\n\n사용자: ...").

Usage:
  # Use explicit prompt string
  python3 scripts/gemini_minimal_text.py --prompt "시스템: ...\n\n사용자: ..."

  # Or load from file
  python3 scripts/gemini_minimal_text.py --prompt-file ./prompt.txt

  # Or use built-in sample (the file-selection prompt with 3 candidates)
  python3 scripts/gemini_minimal_text.py --use-sample 1

Env:
  GOOGLE_AI_API_KEY or GOOGLE_API_KEY must be set.
"""

from __future__ import annotations

import os
import sys
import json
import argparse


SAMPLE_PROMPT = (
    "시스템: 너는 파일 선택 도우미야.\n"
    "- 아래 후보 리스트 중 사용자의 의도에 가장 맞는 하나를 고르고, JSON만 반환해.\n"
    "- 출력 형식: {\"selected_index\": <정수>}\n"
    "- 설명/텍스트/코드블록 없이 JSON 하나만.\n"
    "- 문서류(.hwpx/.hwp/.docx/.pdf/.txt)와 얕은 경로를 선호.\n"
    "- 노이즈(Thumbs.db, .DS_Store, desktop.ini)는 제외.\n\n"
    "사용자: 사용자의 지시에 가장 부합하는 원본 파일을 선택하세요.\n\n"
    "[규칙] JSON만, {\"selected_index\": <정수> 형식으로 답변하세요.\n"
    "[참고] 아래는 후보 목록입니다. index로만 선택하세요.\n\n"
    "[후보 file] (index, name)\n"
    "0. MCP설계계획.txt\n"
    "1. 설계학회 여름세미나- 도시설계와 AI.hwpx\n"
    "2. 스크린샷 2025-08-19 오후 3.15.26.png\n"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.getenv("AI_MODEL", "gemini-2.5-flash"))
    ap.add_argument("--prompt", default=None, help="직접 전달할 전체 프롬프트 문자열")
    ap.add_argument("--prompt-file", default=None, help="프롬프트가 들어있는 파일 경로")
    ap.add_argument("--use-sample", type=int, default=0, help="내장 샘플 프롬프트 사용 여부(1/0)")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=64)
    ap.add_argument("--json-mode", type=int, default=0, help="1이면 response_mime_type=application/json 힌트")
    ap.add_argument("--force-schema", type=int, default=0, help="1이면 response_schema로 {selected_index:int} 강제")
    ap.add_argument("--safety-off", type=int, default=0, help="1이면 모든 HarmCategory에 BLOCK_NONE 적용")
    args = ap.parse_args()

    api_key = os.getenv("GOOGLE_AI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_AI_API_KEY/GOOGLE_API_KEY 환경변수가 필요합니다.")
        return 2

    # Resolve prompt
    prompt = None
    if args.prompt:
        prompt = args.prompt
    elif args.prompt_file:
        try:
            with open(args.prompt_file, "r", encoding="utf-8") as f:
                prompt = f.read()
        except Exception as e:
            print(f"❌ 프롬프트 파일 읽기 실패: {e}")
            return 2
    elif args.use_sample:
        prompt = SAMPLE_PROMPT
    else:
        print("❌ --prompt 또는 --prompt-file 또는 --use-sample 1 중 하나를 지정하세요.")
        return 2

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        generation_config = {
            "temperature": args.temperature,
            "max_output_tokens": args.max_tokens,
        }
        if args.json_mode or args.force_schema:
            generation_config["response_mime_type"] = "application/json"
        if args.force_schema:
            generation_config["response_schema"] = {
                "type": "object",
                "properties": {"selected_index": {"type": "integer"}},
                "required": ["selected_index"],
            }

        # Optional safety settings
        safety_settings = None
        if args.safety_off:
            try:
                from google.generativeai.types import HarmCategory, HarmBlockThreshold
                safety_settings = [
                    {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_NONE},
                    {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_NONE},
                    {"category": HarmCategory.HARM_CATEGORY_SEXUAL, "threshold": HarmBlockThreshold.BLOCK_NONE},
                    {"category": HarmCategory.HARM_CATEGORY_DANGEROUS, "threshold": HarmBlockThreshold.BLOCK_NONE},
                    {"category": HarmCategory.HARM_CATEGORY_UNSPECIFIED, "threshold": HarmBlockThreshold.BLOCK_NONE},
                ]
            except Exception:
                safety_settings = None

        model = genai.GenerativeModel(model_name=args.model)
        if safety_settings is not None:
            resp = model.generate_content(prompt, generation_config=generation_config, safety_settings=safety_settings)
        else:
            resp = model.generate_content(prompt, generation_config=generation_config)

        # Print minimal diagnostics
        finish_reason = None
        text = None
        try:
            text = getattr(resp, "text", None)
        except Exception as e:
            text = f"<.text accessor error: {e}>"
        try:
            if resp.candidates:
                finish_reason = getattr(resp.candidates[0], "finish_reason", None)
        except Exception:
            pass

        print("=== Minimal Gemini Result ===")
        print(json.dumps({
            "model": args.model,
            "finish_reason": str(finish_reason) if finish_reason is not None else None,
            "text": text,
            "prompt_len": len(prompt),
        }, ensure_ascii=False, indent=2))

        # Try to print first content part text if .text is empty
        if (not text) and getattr(resp, 'candidates', None):
            try:
                parts = getattr(resp.candidates[0], 'content', None)
                if parts and getattr(parts, 'parts', None):
                    texts = [getattr(p, 'text', None) for p in parts.parts if getattr(p, 'text', None)]
                    if texts:
                        print("\nparts[0].text:")
                        print(texts[0])
            except Exception:
                pass

        return 0
    except Exception as e:
        print(f"❌ Minimal probe error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
