"""Minimal local stand-in for the Anthropic Messages API, for end-to-end hook tests.

Every POST to /v1/messages streams one assistant text reply. The reply text is
taken from MOCK_REPLY (JSON-escaped string, so it can carry invisible Unicode).
No real model or credentials are involved.
"""

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REPLY = json.loads(os.environ.get("MOCK_REPLY", '"A\\u200bB"'))
LOG = os.environ.get("MOCK_LOG")


def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    do_HEAD = do_GET

    def do_POST(self):
        n = int(self.headers.get("content-length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if LOG:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(self.path + "\n")
        body_log = os.environ.get("MOCK_BODY_LOG")
        if body_log:
            with open(body_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(body, ensure_ascii=False) + "\n")
        if "count_tokens" in self.path:
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"input_tokens": 10}')
            return
        model = body.get("model", "claude-test")
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.end_headers()
        usage = {"input_tokens": 10, "output_tokens": 3}
        w = self.wfile.write
        w(sse("message_start", {"type": "message_start", "message": {
            "id": "msg_mock", "type": "message", "role": "assistant", "model": model,
            "content": [], "stop_reason": None, "stop_sequence": None, "usage": usage}}))
        w(sse("content_block_start", {"type": "content_block_start", "index": 0,
                                      "content_block": {"type": "text", "text": ""}}))
        n = max(1, int(os.environ.get("MOCK_SPLIT", "1")))
        step = max(1, -(-len(REPLY) // n))
        for i in range(0, len(REPLY), step):
            w(sse("content_block_delta", {"type": "content_block_delta", "index": 0,
                                          "delta": {"type": "text_delta", "text": REPLY[i:i + step]}}))
            self.wfile.flush()
            if n > 1:
                time.sleep(float(os.environ.get("MOCK_DELAY", "0.4")))
        w(sse("content_block_stop", {"type": "content_block_stop", "index": 0}))
        w(sse("message_delta", {"type": "message_delta",
                                "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                                "usage": {"output_tokens": 3}}))
        w(sse("message_stop", {"type": "message_stop"}))


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H)
    srv.serve_forever()
