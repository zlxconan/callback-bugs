"""Local HTTP page fixture used for real Playwright adapter verification."""

import json
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

PAGE = """<!doctype html>
<html><body>
  <input id="business-id" value="">
  <button id="create-order">Create order</button>
  <output id="status" data-final-status="idle">idle</output>
  <script>
    const events = [];
    document.querySelector('#create-order').addEventListener('click', async () => {
      const businessId = document.querySelector('#business-id').value;
      events.push('submit');
      const first = new AbortController();
      setTimeout(() => first.abort(), 20);
      try {
        await fetch('/orders', {
          method: 'POST', signal: first.signal,
          headers: {'content-type': 'application/json', 'x-request-id': 'HTTP-REQ-1',
                    'x-trace-id': 'TRACE-001'},
          body: JSON.stringify({business_id: businessId})
        });
      } catch (_) {
        events.push('timeout', 'retry');
      }
      await fetch('/orders', {
        method: 'POST',
        headers: {'content-type': 'application/json', 'x-request-id': 'HTTP-REQ-2',
                  'x-trace-id': 'TRACE-001'},
        body: JSON.stringify({business_id: businessId})
      });
      events.push('success');
      const state = await (await fetch('/state')).json();
      const status = document.querySelector('#status');
      status.dataset.finalStatus = 'success';
      status.dataset.businessId = businessId;
      status.dataset.backendStatus = state.first_backend_status;
      status.dataset.retryDetected = String(events.includes('retry'));
      status.dataset.databaseRecordCount = String(state.database_record_count);
      status.dataset.events = JSON.stringify(events);
      status.textContent = 'created';
    });
  </script>
</body></html>
"""


@dataclass
class LabState:
    requests: list[dict[str, str]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)


@dataclass
class LabServer:
    url: str
    state: LabState


@pytest.fixture
def browser_lab() -> Iterator[LabServer]:
    state = LabState()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/state":
                with state.lock:
                    count = len(state.requests)
                self._json(
                    {
                        "first_backend_status": "success" if count else "missing",
                        "database_record_count": count,
                    }
                )
                return
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(PAGE.encode())

        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("content-length", "0"))
            body = json.loads(self.rfile.read(length))
            with state.lock:
                state.requests.append(
                    {
                        "business_id": str(body["business_id"]),
                        "request_id": self.headers["x-request-id"],
                        "trace_id": self.headers["x-trace-id"],
                    }
                )
                sequence = len(state.requests)
            if sequence == 1:
                time.sleep(0.08)
            try:
                self._json({"created": True, "sequence": sequence})
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _json(self, value: object) -> None:
            payload = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield LabServer(f"http://127.0.0.1:{server.server_port}/", state)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
