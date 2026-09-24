"""Per-model smoke test: latency, token accounting, and whether an answer arrives at all."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request

from eval import config
from eval.client import chat

PROMPT = "In one sentence: what is the main risk in promoting a strong engineer into management?"


def list_models(base_url: str, api_key: str) -> list[str]:
    request = urllib.request.Request(base_url + "/models", headers={"Authorization": "Bearer " + api_key})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8", "replace"))
        return [item.get("id", "?") for item in body.get("data", [])]
    except Exception as exc:  # noqa: BLE001
        return ["<models endpoint failed: %s>" % exc]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="", help="comma separated; default is every advertised model")
    args = parser.parse_args(argv)

    cfg = config.settings()
    if not cfg["api_key"]:
        print("no CHEAPSEEK_API_KEY in .env")
        return 2

    advertised = list_models(cfg["base_url"], cfg["api_key"])
    print("advertised models: %s" % ", ".join(advertised))
    models = [name.strip() for name in args.models.split(",") if name.strip()] or advertised

    for model in models:
        wall_start = time.time()
        result = chat(
            [{"role": "user", "content": PROMPT}],
            model,
            cfg["api_key"],
            cfg["base_url"],
            max_tokens=1200,
            temperature=0.7,
        )
        wall_ms = int((time.time() - wall_start) * 1000)
        usage = result["usage"]
        cost = config.cost_usd(usage["prompt_tokens"], usage["completion_tokens"],
                               cfg["price_in"], cfg["price_out"])
        print(
            "\n%s\n  ok=%s wall=%sms api=%sms attempts=%s finish=%s\n"
            "  tokens in=%s out=%s  cost=$%.6f\n  text: %s\n  error: %s"
            % (
                model,
                result["ok"],
                wall_ms,
                result["latency_ms"],
                result["attempts"],
                result["finish"],
                usage["prompt_tokens"],
                usage["completion_tokens"],
                cost,
                (result["text"][:200] or "<empty>").replace("\n", " "),
                result["error"] or "-",
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

