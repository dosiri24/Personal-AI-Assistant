#!/usr/bin/env python3
"""
Standalone Gemini JSON selection probe

Replicates the prompt shape used in MCPIntegration._llm_select_from_candidates
without importing the project. Useful to compare API behavior in isolation.

Usage examples:
  # Default (replicate project):
  python3 scripts/gemini_json_probe.py \
      --kind file \
      --candidates "MCP설계계획.txt;설계학회 여름세미나- 도시설계와 AI.hwpx;스크린샷 2025-08-19 오후 3.15.26.png"

  # Force JSON mode (Gemini hint):
  python3 scripts/gemini_json_probe.py --json-mode 1 --kind file --candidates "A.txt;B.pdf;C.png"

Env:
  GOOGLE_AI_API_KEY or GOOGLE_API_KEY must be set.
"""

from __future__ import annotations

import os
import sys
import json
import argparse
from typing import List


def build_messages(kind: str, candidates: List[str]):
    system = (
        "너는 파일 선택 도우미야.\n"
        "- 아래 후보 리스트 중 사용자의 의도에 가장 맞는 하나를 고르고, JSON만 반환해.\n"
        "- 출력 형식: {\"selected_index\": <정수>}\n"
        "- 설명/텍스트/코드블록 없이 JSON 하나만.\n"
        "- 문서류(.hwpx/.hwp/.docx/.pdf/.txt)와 얕은 경로를 선호.\n"
        "- 노이즈(Thumbs.db, .DS_Store, desktop.ini)는 제외.\n"
    )
    lines = [
        "사용자의 지시에 가장 부합하는 원본 파일을 선택하세요.",
        "",
        "[규칙] JSON만, {\"selected_index\": <정수> 형식으로 답변하세요.",
        "[참고] 아래는 후보 목록입니다. index로만 선택하세요.",
        "",
        f"[후보 {kind}] (index, name)",
    ]
    for i, name in enumerate(candidates):
        lines.append(f"{i}. {name}")
    user = "\n".join(lines)
    return system, user


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.getenv("AI_MODEL", "gemini-2.5-flash"))
    ap.add_argument("--kind", default="file", choices=["file", "directory"])
    ap.add_argument("--candidates", required=True, help="';'로 구분된 후보 이름 목록")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=64)
    ap.add_argument("--json-mode", type=int, default=0, help="1이면 response_mime_type=application/json 힌트")
    args = ap.parse_args()

    api_key = os.getenv("GOOGLE_AI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_AI_API_KEY/GOOGLE_API_KEY 환경변수가 필요합니다.")
        sys.exit(2)

    cand_list = [c.strip() for c in args.candidates.split(";") if c.strip()]
    if not cand_list:
        print("❌ 후보가 비어있습니다")
        sys.exit(2)

    system, user = build_messages(args.kind, cand_list)

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        # Set response JSON hint optionally
        generation_config = {
            "temperature": args.temperature,
            "max_output_tokens": args.max_tokens,
        }
        if args.json_mode:
            generation_config["response_mime_type"] = "application/json"

        model = genai.GenerativeModel(
            model_name=args.model,
            system_instruction=system,
            generation_config=generation_config,
        )
        resp = model.generate_content([
            {"role": "user", "parts": [user]},
        ])

        # Collect diagnostics
        diag = {
            "model": args.model,
            "finish_reason": None,
            "safety_ratings": None,
            "raw_text": None,
            "parts": None,
        }

        try:
            diag["raw_text"] = getattr(resp, "text", None)
        except Exception as e:
            diag["raw_text"] = f"<.text accessor error: {e}>"

        try:
            if resp.candidates:
                cand0 = resp.candidates[0]
                fr = getattr(cand0, "finish_reason", None)
                diag["finish_reason"] = str(fr) if fr is not None else None
                sr = getattr(cand0, "safety_ratings", None)
                diag["safety_ratings"] = str(sr) if sr is not None else None
                parts = getattr(cand0, "content", None)
                if parts and getattr(parts, "parts", None):
                    # Try to extract text parts
                    texts = []
                    for p in parts.parts:
                        t = getattr(p, "text", None)
                        if t:
                            texts.append(t)
                    diag["parts"] = texts
        except Exception:
            pass

        # Print concise summary
        print("=== Gemini Probe Result ===")
        print(json.dumps(diag, ensure_ascii=False, indent=2))

        # Best-effort JSON parse if any text present
        payload = diag.get("raw_text") or (diag.get("parts") or [None])[0]
        if payload and isinstance(payload, str):
            try:
                data = json.loads(payload.strip().strip("`"))
                print("\nParsed JSON:")
                print(json.dumps(data, ensure_ascii=False, indent=2))
            except Exception:
                pass

        return 0
    except Exception as e:
        print(f"❌ Probe error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
