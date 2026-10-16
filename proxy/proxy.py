"""Token-metering proxy in front of the OpenAI-compatible LLM endpoint.

Every arm points its base URL at http://proxy:8080/run/<run_id>/v1 . The proxy
strips the /run/<run_id> prefix, adds the upstream auth headers, forwards the
request, and appends one line per LLM call to /out/usage.jsonl with the token
usage the upstream reported. Streaming requests get
stream_options.include_usage=true injected so the final SSE chunk carries usage.

Same meter for every arm, so no arm depends on its own runtime's logging.
Stdlib only.
"""

import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = os.environ["UPSTREAM_BASE"].rstrip("/")  # .../workers-ai/v1
TOKEN = os.environ["UPSTREAM_TOKEN"]
LOG_PATH = os.environ.get("USAGE_LOG", "/out/usage.jsonl")
PATH_RE = re.compile(r"^/run/(?P<run>[A-Za-z0-9_.-]+)/v1(?P<rest>/.*)$")
TRANSCRIPTS = os.path.join(os.path.dirname(LOG_PATH), "transcripts")
_lock = threading.Lock()
# Fault injection, keyed by a tag inside the run id (see PREREGISTRATION.md):
#   "-f429-"  -> the run's FIRST chat call gets HTTP 429 (never reaches the model)
#   "-fjson-" -> the run's FIRST chat call is forwarded, but its content is replaced
#               with broken JSON before the client sees it
_first_seen: set[str] = set()


def first_call(run_id: str) -> bool:
	with _lock:
		if run_id in _first_seen:
			return False
		_first_seen.add(run_id)
		return True


def transcript(run_id: str, row: dict) -> None:
	os.makedirs(TRANSCRIPTS, exist_ok=True)
	with _lock, open(os.path.join(TRANSCRIPTS, f"{run_id}.jsonl"), "a") as f:
		f.write(json.dumps(row) + "\n")


def log(row: dict) -> None:
	with _lock, open(LOG_PATH, "a") as f:
		f.write(json.dumps(row) + "\n")


class Handler(BaseHTTPRequestHandler):
	protocol_version = "HTTP/1.1"

	def log_message(self, *_args) -> None:  # quiet
		return

	def _forward(self, method: str) -> None:
		m = PATH_RE.match(self.path)
		if not m:
			self.send_error(404, "expected /run/<run_id>/v1/...")
			return
		run_id, rest = m.group("run"), m.group("rest")
		length = int(self.headers.get("Content-Length") or 0)
		body = self.rfile.read(length) if length else b""
		payload = None
		stream = False
		if body and self.headers.get("Content-Type", "").startswith("application/json"):
			try:
				payload = json.loads(body)
			except json.JSONDecodeError:
				payload = None
		if isinstance(payload, dict) and payload.get("stream"):
			stream = True
			payload.setdefault("stream_options", {})["include_usage"] = True
			body = json.dumps(payload).encode()
		# M2 (deepseek-v4-flash) thinks by default and in the pilot ran its reasoning into the
		# token cap with no answer. Thinking is switched off here, for every arm alike
		# (PREREGISTRATION.md, Deviations).
		if isinstance(payload, dict) and "deepseek" in str(payload.get("model", "")):
			payload.setdefault("chat_template_kwargs", {})["thinking"] = False
			body = json.dumps(payload).encode()
		# Workers AI caps a reply at 256 tokens when the client sends no max_tokens (Hermes
		# sends none). Give every arm the same 8,000 ceiling A2 and A3 set themselves.
		if isinstance(payload, dict) and rest.endswith("/chat/completions") and not payload.get("max_tokens"):
			payload["max_tokens"] = 8000
			body = json.dumps(payload).encode()

		is_chat = rest.endswith("/chat/completions")
		first = is_chat and first_call(run_id)
		if first and "-f429-" in run_id:
			data = b'{"error":{"message":"Rate limit exceeded (injected)","type":"rate_limit_error"}}'
			self.send_response(429)
			self.send_header("Content-Type", "application/json")
			self.send_header("Retry-After", "2")
			self.send_header("Content-Length", str(len(data)))
			self.end_headers()
			self.wfile.write(data)
			log({"run_id": run_id, "ts": time.time(), "ms": 0, "status": 429, "model": (payload or {}).get("model"), "stream": stream, "injected": "f429", "prompt_tokens": 0, "completion_tokens": 0})
			transcript(run_id, {"ts": time.time(), "request": payload, "status": 429, "injected": "f429"})
			return
		corrupt = first and "-fjson-" in run_id
		# A corrupted streaming call is fetched non-streaming, broken, then replayed as SSE.
		fake_sse = corrupt and stream
		if fake_sse:
			payload["stream"] = False
			payload.pop("stream_options", None)
			body = json.dumps(payload).encode()
			stream = False

		req = urllib.request.Request(UPSTREAM + rest, data=body or None, method=method)
		req.add_header("Content-Type", "application/json")
		# Cloudflare's bot rules 403 the default Python-urllib user agent.
		req.add_header("User-Agent", "lokerdollar-research-proxy/1.0")
		req.add_header("Authorization", f"Bearer {TOKEN}")
		req.add_header("cf-aig-authorization", f"Bearer {TOKEN}")
		started = time.time()
		status = 0
		usage = None
		model = payload.get("model") if isinstance(payload, dict) else None
		try:
			resp = urllib.request.urlopen(req, timeout=600)
			status = resp.status
		except urllib.error.HTTPError as e:
			resp = e
			status = e.code

		self.send_response(status)
		ctype = "text/event-stream" if fake_sse and status == 200 else resp.headers.get("Content-Type", "application/json")
		self.send_header("Content-Type", ctype)
		if stream and status == 200:
			self.send_header("Transfer-Encoding", "chunked")
			self.end_headers()
			buf = b""
			while True:
				chunk = resp.read1(65536) if hasattr(resp, "read1") else resp.read(65536)
				if not chunk:
					break
				buf += chunk
				self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
				self.wfile.flush()
			self.wfile.write(b"0\r\n\r\n")
			for line in buf.decode(errors="ignore").splitlines():
				if line.startswith("data:") and '"usage"' in line:
					try:
						u = json.loads(line[5:].strip()).get("usage")
						if u:
							usage = u
					except json.JSONDecodeError:
						pass
		else:
			data = resp.read()
			if corrupt and status == 200:
				try:
					j = json.loads(data)
					j["choices"][0]["message"]["content"] = '{"linkedin": "Only 23% of remote jobs list pay, "x_thread": [ broken'
					j["choices"][0]["message"].pop("tool_calls", None)
					j["choices"][0]["finish_reason"] = "stop"
					data = json.dumps(j).encode()
				except (json.JSONDecodeError, KeyError, IndexError):
					pass
			if fake_sse and status == 200:
				j = json.loads(data)
				usage = j.get("usage")
				base = {"id": j.get("id"), "object": "chat.completion.chunk", "created": j.get("created"), "model": j.get("model")}
				events = [
					{**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": j["choices"][0]["message"]["content"]}, "finish_reason": None}]},
					{**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
					{**base, "choices": [], "usage": usage},
				]
				data = ("".join(f"data: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n").encode()
			self.send_header("Content-Length", str(len(data)))
			self.end_headers()
			self.wfile.write(data)
			if not fake_sse:
				try:
					usage = json.loads(data).get("usage")
				except (json.JSONDecodeError, AttributeError):
					usage = None

		if is_chat:
			transcript(
				run_id,
				{
					"ts": started,
					"request": payload,
					"status": status,
					"response": buf.decode(errors="ignore")[-20000:] if stream and status == 200 else data.decode(errors="ignore")[:20000],
					"injected": "fjson" if corrupt else None,
				},
			)
			log(
				{
					"run_id": run_id,
					"ts": started,
					"ms": round((time.time() - started) * 1000),
					"status": status,
					"model": model,
					"stream": stream or fake_sse,
					"n_messages": len(payload.get("messages", [])) if isinstance(payload, dict) else None,
					"n_tools": len(payload.get("tools", []) or []) if isinstance(payload, dict) else None,
					"prompt_tokens": (usage or {}).get("prompt_tokens"),
					"completion_tokens": (usage or {}).get("completion_tokens"),
					"injected": "fjson" if corrupt else None,
				}
			)

	def do_POST(self) -> None:
		self._forward("POST")

	def do_GET(self) -> None:
		self._forward("GET")


if __name__ == "__main__":
	ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
