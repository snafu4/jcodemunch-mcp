"""Standalone web dashboard for jCodeMunch token-savings statistics."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

_BYTES_PER_TOKEN = 4
_SAVINGS_FILE = "_savings.json"
_DEFAULT_OPUS_PRICE_PER_MILLION_TOKENS = 15.00
_DEFAULT_GPT_PRICE_PER_MILLION_TOKENS = 10.00


def _price_from_env(env_var: str, default: float) -> float:
    """Return non-negative float from env var, otherwise default."""
    raw = os.environ.get(env_var)
    if raw is None:
        return default
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _current_pricing() -> dict[str, float]:
    return {
        "claude_opus": _price_from_env("JCODEMUNCH_OPUS_PRICE", _DEFAULT_OPUS_PRICE_PER_MILLION_TOKENS) / 1_000_000,
        "gpt5_latest": _price_from_env("JCODEMUNCH_GPT_PRICE", _DEFAULT_GPT_PRICE_PER_MILLION_TOKENS) / 1_000_000,
    }


def _per_million_token_prices(pricing_per_token: dict[str, float]) -> dict[str, float]:
    """Convert USD/token rates into USD per 1M tokens for display."""
    return {model: round(rate * 1_000_000, 4) for model, rate in pricing_per_token.items()}

HTML_TEMPLATE = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>jCodeMunch Token Stats</title>
  <style>
    :root { color-scheme: light dark; }
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; max-width: 960px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; }
    .card { border: 1px solid #8884; border-radius: 12px; padding: 1rem; background: #ffffff10; }
    .metric { font-size: 1.6rem; font-weight: 700; margin-top: .3rem; }
    .muted { opacity: .7; font-size: .9rem; }
    table { width: 100%; border-collapse: collapse; margin-top: .5rem; }
    th, td { text-align: left; padding: .35rem; border-bottom: 1px solid #8884; }
    code { font-size: .85rem; }
  </style>
</head>
<body>
  <h1>jCodeMunch Token Savings Dashboard</h1>
  <p class=\"muted\">Auto-refreshing every <span id=\"refresh\"></span>s</p>

  <section class=\"grid\">
    <div class=\"card\"><div>Total tokens saved</div><div id=\"tokens\" class=\"metric\">-</div></div>
    <div class=\"card\"><div>Approx bytes avoided</div><div id=\"bytes\" class=\"metric\">-</div></div>
    <div class=\"card\"><div>Equivalent 128k contexts</div><div id=\"ctx128\" class=\"metric\">-</div></div>
    <div class=\"card\"><div>Telemetry enabled</div><div id=\"telemetry\" class=\"metric\">-</div></div>
  </section>

  <section class=\"card\" style=\"margin-top: 1rem;\">
    <h2>Estimated cost avoided</h2>
    <table>
      <thead><tr><th>Model</th><th>Cost avoided</th></tr></thead>
      <tbody id=\"costs\"></tbody>
    </table>
  </section>

  <section class=\"card\" style=\"margin-top: 1rem;\">
    <h2>Pricing used in calculations (per 1M tokens)</h2>
    <div class=\"muted\">Values come from <code>JCODEMUNCH_OPUS_PRICE</code> and <code>JCODEMUNCH_GPT_PRICE</code> (stored internally as per-token rates).</div>
    <table>
      <thead><tr><th>Model</th><th>Price / 1M tokens</th></tr></thead>
      <tbody id=\"prices\"></tbody>
    </table>
  </section>

  <section class=\"card\" style=\"margin-top: 1rem;\">
    <h2>Source</h2>
    <div>Updated: <span id=\"updated\">-</span></div>
    <div class=\"muted\">Savings file: <code id=\"file\">-</code></div>
  </section>

<script>
const refreshSeconds = __REFRESH_SECONDS__;
document.getElementById('refresh').textContent = refreshSeconds;

const fmt = (n) => new Intl.NumberFormat().format(n ?? 0);
const fmtMoney = (n) => new Intl.NumberFormat(undefined, {style: 'currency', currency: 'USD'}).format(n ?? 0);

async function loadStats() {
  const response = await fetch('/api/stats');
  const data = await response.json();

  document.getElementById('tokens').textContent = fmt(data.total_tokens_saved);
  document.getElementById('bytes').textContent = fmt(data.approx_raw_bytes_avoided);
  document.getElementById('ctx128').textContent = data.equivalent_context_windows?.['128k'] ?? 0;
  document.getElementById('telemetry').textContent = data.telemetry_enabled ? 'Yes' : 'No';
  document.getElementById('updated').textContent = data.generated_at;
  document.getElementById('file').textContent = data.savings_file || '-';

  const tbody = document.getElementById('costs');
  tbody.innerHTML = '';
  for (const [model, value] of Object.entries(data.total_cost_avoided || {})) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${model}</td><td>${fmtMoney(value)}</td>`;
    tbody.appendChild(tr);
  }

  const priceBody = document.getElementById('prices');
  priceBody.innerHTML = '';
  for (const [model, value] of Object.entries(data.pricing_usd_per_million_tokens || {})) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${model}</td><td>${fmtMoney(value)}</td>`;
    priceBody.appendChild(tr);
  }
}

loadStats();
setInterval(loadStats, refreshSeconds * 1000);
</script>
</body>
</html>
"""


def _savings_path(base_path: str | None = None) -> Path:
    root = Path(base_path) if base_path else Path.home() / ".code-index"
    root.mkdir(parents=True, exist_ok=True)
    return root / _SAVINGS_FILE


def _read_savings_data(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = path.read_bytes()
    except Exception:
        return {}
    if not raw:
        return {}
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return json.loads(raw.decode(encoding))
        except Exception:
            continue
    return {}


def build_stats_payload(base_path: str | None = None) -> dict[str, Any]:
    path = _savings_path(base_path or os.environ.get("CODE_INDEX_PATH"))
    data = _read_savings_data(path)
    total_tokens_saved = max(0, int(data.get("total_tokens_saved", 0) or 0))
    pricing = _current_pricing()

    return {
        "total_tokens_saved": total_tokens_saved,
        "approx_raw_bytes_avoided": total_tokens_saved * _BYTES_PER_TOKEN,
        "pricing_usd_per_token": pricing,
        "pricing_usd_per_million_tokens": _per_million_token_prices(pricing),
        "total_cost_avoided": {
            model: round(total_tokens_saved * rate, 4)
            for model, rate in pricing.items()
        },
        "equivalent_context_windows": {
            "32k": round(total_tokens_saved / 32_000, 2),
            "128k": round(total_tokens_saved / 128_000, 2),
            "1m": round(total_tokens_saved / 1_000_000, 4),
        },
        "telemetry_enabled": os.environ.get("JCODEMUNCH_SHARE_SAVINGS", "1") != "0",
        "anon_id_present": bool(data.get("anon_id")),
        "savings_file": str(path),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def create_handler(base_path: str | None, refresh_seconds: int) -> type[BaseHTTPRequestHandler]:
    html = HTML_TEMPLATE.replace("__REFRESH_SECONDS__", str(refresh_seconds))

    class StatsHandler(BaseHTTPRequestHandler):
        def _send_json(self, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/api/stats":
                self._send_json(build_stats_payload(base_path))
                return
            if self.path == "/":
                self._send_html(html)
                return
            self.send_error(404, "Not Found")

        def log_message(self, format: str, *args: object) -> None:
            return

    return StatsHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run token-savings dashboard web app.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on.")
    parser.add_argument("--base-path", default=os.environ.get("CODE_INDEX_PATH"), help="Optional base path containing _savings.json.")
    parser.add_argument("--refresh-seconds", type=int, default=5, help="How often browser fetches updated stats.")
    args = parser.parse_args()

    if args.refresh_seconds < 1:
        parser.error("--refresh-seconds must be >= 1")

    server = ThreadingHTTPServer((args.host, args.port), create_handler(args.base_path, args.refresh_seconds))
    print(f"Dashboard available at http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
