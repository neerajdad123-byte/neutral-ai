"""Settings loaded from .env. stdlib only, no dependency."""

from __future__ import annotations

import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

DEFAULTS = {
    "CHEAPSEEK_BASE_URL": "https://cheapseek.kdns.fr/v1",
    "CHEAPSEEK_API_KEY": "",
    "PRICE_IN_PER_MTOK": "0.04",
    "PRICE_OUT_PER_MTOK": "1.00",
    "GEN_MODEL": "deepseek-flash",
    "JUDGE_MODEL": "deepseek-flash",
}


def load_env(path: pathlib.Path | None = None) -> dict[str, str]:
    """Read .env into a dict. A real environment variable beats the file."""
    env = dict(DEFAULTS)
    target = pathlib.Path(path) if path else ROOT / ".env"
    if target.exists():
        for raw in target.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    for key in list(env):
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env


def settings() -> dict:
    env = load_env()
    return {
        "base_url": env["CHEAPSEEK_BASE_URL"].rstrip("/"),
        "api_key": env["CHEAPSEEK_API_KEY"],
        "gen_model": env["GEN_MODEL"],
        "judge_model": env["JUDGE_MODEL"],
        "price_in": float(env["PRICE_IN_PER_MTOK"]),
        "price_out": float(env["PRICE_OUT_PER_MTOK"]),
    }


def cost_usd(prompt_tokens: int, completion_tokens: int, price_in: float, price_out: float) -> float:
    """Prices are USD per 1M tokens."""
    return prompt_tokens / 1e6 * price_in + completion_tokens / 1e6 * price_out

