"""
Flask chat UI for the Orchestrator HTTP endpoint
================================================

A small web chat interface for the orchestrator HTTP API exposed by
``../orchestrator_http.py``. The page has a textbox to configure which
orchestrator ``/chat`` endpoint to talk to (defaulting to the local orchestrator),
so you can re-point the UI at another environment without editing any files.

Requests from the browser are proxied server-side through this Flask app to the
chosen orchestrator endpoint (avoids browser CORS issues).

Run:
        1. Start the orchestrator HTTP server:
            python ../orchestrator_http.py
    2. python app.py
    3. Open http://127.0.0.1:5000 in a browser.
"""

from __future__ import annotations

import os

import requests
from flask import Flask, Response, jsonify, render_template, request

# Default orchestrator endpoint (orchestrator_http.py defaults to port 8000).
DEFAULT_ENDPOINT = os.getenv(
    "ORCHESTRATOR_ENDPOINT", "http://127.0.0.1:8000/chat"
)
# How long to wait for the orchestrator (agent + MCP calls can take a while).
REQUEST_TIMEOUT = float(os.getenv("ORCHESTRATOR_TIMEOUT", "120"))

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html", default_endpoint=DEFAULT_ENDPOINT)


@app.post("/api/chat")
def api_chat():
    """Proxy a single chat turn to the configured orchestrator endpoint."""
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    endpoint = (data.get("endpoint") or DEFAULT_ENDPOINT).strip()
    session_id = data.get("session_id")

    if not message:
        return jsonify({"error": "Message must not be empty."}), 400
    if not endpoint:
        return jsonify({"error": "Orchestrator endpoint must not be empty."}), 400

    payload: dict[str, object] = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    try:
        resp = requests.post(endpoint, json=payload, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        return jsonify({"error": f"Could not reach orchestrator: {exc}"}), 502

    if resp.status_code != 200:
        detail = resp.text
        try:
            detail = resp.json().get("detail", detail)
        except ValueError:
            pass
        return jsonify({"error": f"Orchestrator returned {resp.status_code}: {detail}"}), 502

    try:
        body = resp.json()
    except requests.JSONDecodeError:
        return jsonify({"error": "Orchestrator returned an invalid JSON response."}), 502
    return jsonify({"reply": body.get("reply", ""), "session_id": body.get("session_id")})


@app.post("/api/chat/stream")
def api_chat_stream():
    """Proxy a chat turn to the orchestrator's SSE endpoint, streaming events through.

    The browser posts the base ``/chat`` endpoint; the matching streaming endpoint is
    ``<endpoint>/stream``. If the endpoint already ends with ``/stream`` (someone pasted
    the streaming URL), it's used as-is so we never produce ``/stream/stream``. Events
    are forwarded verbatim (no server-side buffering).
    """
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    endpoint = (data.get("endpoint") or DEFAULT_ENDPOINT).strip()
    session_id = data.get("session_id")

    if not message:
        return jsonify({"error": "Message must not be empty."}), 400
    if not endpoint:
        return jsonify({"error": "Orchestrator endpoint must not be empty."}), 400

    base = endpoint.rstrip("/")
    stream_endpoint = base if base.endswith("/stream") else base + "/stream"
    payload: dict[str, object] = {"message": message}
    if session_id:
        payload["session_id"] = session_id

    try:
        upstream = requests.post(
            stream_endpoint, json=payload, timeout=REQUEST_TIMEOUT, stream=True
        )
    except requests.RequestException as exc:
        return jsonify({"error": f"Could not reach orchestrator: {exc}"}), 502

    if upstream.status_code != 200:
        detail = upstream.text
        try:
            detail = upstream.json().get("detail", detail)
        except ValueError:
            pass
        return jsonify({"error": f"Orchestrator returned {upstream.status_code}: {detail}"}), 502

    def generate():
        try:
            for line in upstream.iter_lines(chunk_size=1):
                yield line + b"\n"
        finally:
            upstream.close()

    return Response(generate(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=True)