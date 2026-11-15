#!/usr/bin/env python3
"""Local backend for the RAG Lead Console GUI.

Serves ``gui/`` and proxies the five provider calls using the keys already in
``.env``. Keys never reach the browser. Bind to 127.0.0.1 by default.

Run:
    cd ~/rag-la-restaurant/rag-lead-generation
    source .venv/bin/activate
    python gui_server.py
    # open http://127.0.0.1:8080
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from rag_leads.config import (  # noqa: E402
    DEFAULT_PRICE_LEVELS,
    ConfigError,
    Rectangle,
    Settings,
    load_settings,
)
from rag_leads.embeddings import EmbeddingClient  # noqa: E402
from rag_leads.hasdata import fetch_reviews  # noqa: E402
from rag_leads.places import search_restaurants  # noqa: E402
from rag_leads.store import VectorStore  # noqa: E402

GUI_DIR = ROOT / "gui"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}

SETTINGS: Settings | None = None


def _redact(message: str) -> str:
    """Never let a provider exception echo a credential back to the browser."""
    if SETTINGS is None:
        return message
    for attr in (
        "pinecone_api_key",
        "hasdata_api_key",
        "google_places_api_key",
        "huggingface_api_token",
        "deepseek_api_key",
    ):
        value = getattr(SETTINGS, attr, None)
        if value:
            message = message.replace(value, "[redacted]")
    return message


class Handler(BaseHTTPRequestHandler):
    server_version = "RAGLeadConsole/1.0"

    # --- responses -----------------------------------------------------

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 10_000_000:
            raise ValueError("request body too large")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw or b"{}")
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON body: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def _serve_static(self, path: str) -> bool:
        entry = STATIC_FILES.get(path)
        if not entry:
            return False

        name, content_type = entry
        file_path = GUI_DIR / name
        if not file_path.is_file():
            self._json(404, {"error": f"GUI asset missing: {name}"})
            return True

        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)
        return True

    # --- routes --------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]

        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        try:
            if path == "/api/health":
                self._json(200, self._health())
                return
            if path == "/api/pinecone/index":
                self._json(200, self._pinecone_info())
                return
        except ConfigError as exc:
            self._json(500, {"error": _redact(str(exc))})
            return
        except Exception as exc:
            self._json(502, {"error": _redact(f"{type(exc).__name__}: {exc}")})
            return

        if self._serve_static(path):
            return
        self._json(404, {"error": f"not found: {path}"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]

        routes = {
            "/api/google/geocode": self._google_geocode,
            "/api/google/places": self._google_places,
            "/api/hasdata/reviews": self._hasdata_reviews,
            "/api/hf/embed": self._hf_embed,
            "/api/pinecone/upsert": self._pinecone_upsert,
            "/api/pinecone/query": self._pinecone_query,
            "/api/deepseek/chat": self._deepseek_chat,
        }

        route = routes.get(path)
        if not route:
            self._json(404, {"error": f"not found: {path}"})
            return

        try:
            payload = route()
            self._json(200, payload)
        except ValueError as exc:
            self._json(400, {"error": _redact(str(exc))})
        except ConfigError as exc:
            self._json(500, {"error": _redact(str(exc))})
        except Exception as exc:
            self._json(502, {"error": _redact(f"{type(exc).__name__}: {exc}")})

    # --- provider calls ------------------------------------------------

    @staticmethod
    def _settings() -> Settings:
        if SETTINGS is None:
            raise ConfigError("server settings were not loaded")
        return SETTINGS

    def _health(self) -> dict:
        settings = self._settings()
        return {
            "ok": True,
            "apis": {
                "google": bool(settings.google_places_api_key),
                "hasdata": bool(settings.hasdata_api_key),
                "hf": bool(settings.huggingface_api_token),
                "deepseek": bool(settings.deepseek_api_key),
                "pinecone": bool(settings.pinecone_api_key),
            },
            "index": settings.pinecone_index_name,
            "namespace": settings.namespace,
        }

    def _google_geocode(self) -> dict:
        settings = self._settings()
        body = self._body()
        zip_code = str(body.get("zip", "")).strip()
        if not zip_code:
            raise ValueError("zip is required")

        response = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={
                "address": zip_code,
                "key": settings.key("google_places_api_key"),
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Google Geocoding HTTP {response.status_code}")

        data = response.json()
        if data.get("status") != "OK" or not data.get("results"):
            message = data.get("error_message") or "no result for that ZIP"
            raise RuntimeError(f"Geocoding {data.get('status', 'failed')}: {message}")

        result = data["results"][0]
        viewport = result.get("geometry", {}).get("viewport")
        if not viewport:
            raise RuntimeError("Geocoding response has no viewport")

        low = {
            "latitude": viewport["southwest"]["lat"],
            "longitude": viewport["southwest"]["lng"],
        }
        high = {
            "latitude": viewport["northeast"]["lat"],
            "longitude": viewport["northeast"]["lng"],
        }
        if not (low["latitude"] < high["latitude"] and low["longitude"] < high["longitude"]):
            raise RuntimeError("Geocoding viewport has invalid low/high corners")

        return {
            "low": low,
            "high": high,
            "formatted": result.get("formatted_address", zip_code),
        }

    def _google_places(self) -> dict:
        settings = self._settings()
        body = self._body()

        low = body.get("low") or {}
        high = body.get("high") or {}
        max_results = int(body.get("maxResults", 10))
        if not 1 <= max_results <= 20:
            raise ValueError("maxResults must be between 1 and 20")

        rectangle = Rectangle(
            low=(float(low["latitude"]), float(low["longitude"])),
            high=(float(high["latitude"]), float(high["longitude"])),
        )
        places = search_restaurants(
            settings,
            text_query="restaurants",
            max_results=max_results,
            box=rectangle,
        )
        return {"places": places}

    def _hasdata_reviews(self) -> dict:
        settings = self._settings()
        body = self._body()
        place_id = str(body.get("placeId", "")).strip()
        if not place_id:
            raise ValueError("placeId is required")

        batch = fetch_reviews(settings, place_id, max_pages=1)
        return {
            "reviews": batch.reviews,
            "calls": batch.calls,
            "credits": batch.credits_spent,
        }

    def _hf_embed(self) -> dict:
        settings = self._settings()
        body = self._body()
        texts = body.get("texts")
        if not isinstance(texts, list) or not texts:
            raise ValueError("texts must be a non-empty list")
        if len(texts) > 100:
            raise ValueError("at most 100 texts per request")

        vectors = EmbeddingClient(settings).embed([str(text) for text in texts])
        return {"vectors": vectors}

    def _pinecone_info(self) -> dict:
        settings = self._settings()
        from pinecone import Pinecone

        pc = Pinecone(api_key=settings.key("pinecone_api_key"))
        info = pc.describe_index(settings.pinecone_index_name)
        return {
            "name": settings.pinecone_index_name,
            "host": info.host,
            "dimension": int(info.dimension),
            "metric": getattr(info, "metric", "cosine"),
        }

    def _pinecone_upsert(self) -> dict:
        settings = self._settings()
        body = self._body()
        vectors = body.get("vectors")
        if not isinstance(vectors, list) or not vectors:
            raise ValueError("vectors must be a non-empty list")

        count = VectorStore(settings).upsert(vectors)
        return {"upserted": count}

    def _pinecone_query(self) -> dict:
        settings = self._settings()
        body = self._body()

        vector = body.get("vector")
        restaurant_ids = body.get("restaurantIds")
        if not isinstance(vector, list) or len(vector) != 384:
            raise ValueError("vector must be a 384-dimension list")
        if not isinstance(restaurant_ids, list) or not restaurant_ids:
            raise ValueError("restaurantIds must be a non-empty list")

        matches = VectorStore(settings).query(
            vector,
            top_k=50,
            filter={
                "price_level": {"$in": list(DEFAULT_PRICE_LEVELS)},
                "restaurant_id": {"$in": restaurant_ids},
            },
        )
        return {"matches": matches}

    def _deepseek_chat(self) -> dict:
        settings = self._settings()
        body = self._body()

        messages = body.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages must be a non-empty list")

        temperature = float(body.get("temperature", 0.3))
        max_tokens = int(body.get("maxTokens", 500))

        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.key('deepseek_api_key')}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=60,
        )

        if response.status_code != 200:
            raise RuntimeError(f"DeepSeek HTTP {response.status_code}: {response.text[:300]}")

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        if not content:
            raise RuntimeError("DeepSeek returned an empty completion")
        return {"content": content.strip()}

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def main() -> int:
    global SETTINGS

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--open", action="store_true", help="open the GUI in a browser")
    args = parser.parse_args()

    # Load all values; missing keys are reported per API in the GUI instead of
    # preventing the server from starting.
    try:
        SETTINGS = load_settings()
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.daemon_threads = True
    url = f"http://{args.host}:{args.port}"
    print(f"RAG Lead Console: {url}")
    print("Keys are loaded from .env; they are never sent to the browser.")
    print("Ctrl+C to stop.")

    if args.open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
