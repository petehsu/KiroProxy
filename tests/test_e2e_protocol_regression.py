import json
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from kiro_proxy.main import app
from kiro_proxy.core import state


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "e2e"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _aws_event_chunk(payload: dict, header_hint: str) -> bytes:
    payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    header_bytes = header_hint.encode("utf-8")
    total_len = 12 + len(header_bytes) + len(payload_bytes) + 4
    return (
        total_len.to_bytes(4, "big")
        + len(header_bytes).to_bytes(4, "big")
        + b"\x00\x00\x00\x00"
        + header_bytes
        + payload_bytes
        + b"\x00\x00\x00\x00"
    )


class _DummyCreds:
    def __init__(self):
        self.profile_arn = "arn:aws:codewhisperer:us-east-1:123456789012:profile/test"
        self.client_id = "client-id"


class _DummyAccount:
    def __init__(self):
        self.id = "test-account"
        self.name = "test-account"
        self.request_count = 0
        self.last_used = None
        self._creds = _DummyCreds()

    def is_token_expiring_soon(self, _minutes=5):
        return False

    async def refresh_token(self):
        return True, "ok"

    def get_token(self):
        return "test-token"

    def get_credentials(self):
        return self._creds

    def get_machine_id(self):
        return "test-machine-id"

    def mark_quota_exceeded(self, _reason=""):
        return None

    def get_proxy_url(self):
        return None


class _FakeHTTPResponse:
    def __init__(self, status_code=200, content=b"", chunks=None, text=None):
        self.status_code = status_code
        if isinstance(content, str):
            content = content.encode("utf-8")
        self.content = content or b""
        self._chunks = chunks if chunks is not None else [self.content]
        self._text = text

    @property
    def text(self):
        if self._text is not None:
            return self._text
        return self.content.decode("utf-8", errors="ignore")

    async def aread(self):
        return self.content

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class _FakeStreamContext:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _UpstreamStub:
    def __init__(self, post_response=None, stream_response=None):
        self.post_requests = []
        self.stream_requests = []
        self.post_response = post_response or _FakeHTTPResponse(
            status_code=200,
            content=_aws_event_chunk(
                {"assistantResponseEvent": {"content": "ok"}},
                "assistantResponseEvent",
            ),
        )
        self.stream_response = stream_response or _FakeHTTPResponse(
            status_code=200,
            chunks=[
                _aws_event_chunk(
                    {"assistantResponseEvent": {"content": "ok"}},
                    "assistantResponseEvent",
                )
            ],
        )

    def _resolve(self, configured):
        if callable(configured):
            return configured()
        return configured

    def client_class(self):
        stub = self

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                return None

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, json=None, headers=None):
                stub.post_requests.append({"url": url, "json": json, "headers": headers})
                return stub._resolve(stub.post_response)

            def stream(self, method, url, json=None, headers=None):
                stub.stream_requests.append(
                    {"method": method, "url": url, "json": json, "headers": headers}
                )
                return _FakeStreamContext(stub._resolve(stub.stream_response))

        return FakeAsyncClient


class ProtocolE2ERegressionTests(unittest.TestCase):
    def _patch_runtime(self, upstream, account):
        stack = ExitStack()
        fake_client = upstream.client_class()

        stack.enter_context(patch("kiro_proxy.main.scheduler.start", new=AsyncMock(return_value=None)))
        stack.enter_context(patch("kiro_proxy.main.scheduler.stop", new=AsyncMock(return_value=None)))

        stack.enter_context(patch.object(state, "get_available_account", return_value=account))
        stack.enter_context(patch.object(state, "get_next_available_account", return_value=None))

        for module in (
            "kiro_proxy.handlers.anthropic",
            "kiro_proxy.handlers.openai",
            "kiro_proxy.handlers.gemini",
            "kiro_proxy.handlers.responses",
        ):
            stack.enter_context(patch(f"{module}.httpx.AsyncClient", fake_client))
            stack.enter_context(
                patch(f"{module}.ensure_profile_arn_ready", new=AsyncMock(return_value=(True, "")))
            )

        return stack

    def test_claude_code_stream_fixture_regression(self):
        fixture = _load_fixture("anthropic_claude_code_stream.json")
        stream_chunks = [
            _aws_event_chunk({"assistantResponseEvent": {"content": "你好，"}}, "assistantResponseEvent"),
            _aws_event_chunk(
                {"assistantResponseEvent": {"content": "我会先检查项目状态。"}}, "assistantResponseEvent"
            ),
            _aws_event_chunk(
                {
                    "toolUseId": "shell_call_1",
                    "name": "shell_command",
                    "input": "{\"command\":\"pwd\"}",
                },
                "toolUseEvent",
            ),
        ]
        upstream = _UpstreamStub(stream_response=_FakeHTTPResponse(status_code=200, chunks=stream_chunks))
        account = _DummyAccount()

        with self._patch_runtime(upstream, account):
            with TestClient(app) as client:
                resp = client.post("/v1/messages?beta=true", json=fixture["request"])

        self.assertEqual(resp.status_code, 200)
        self.assertIn('"type":"message_start"', resp.text)
        self.assertIn('"type":"content_block_delta"', resp.text)
        self.assertIn('"type":"tool_use"', resp.text)
        self.assertIn("shell_call_1", resp.text)

        self.assertEqual(len(upstream.stream_requests), 1)
        payload = upstream.stream_requests[0]["json"]
        self.assertEqual(payload.get("profileArn"), account.get_credentials().profile_arn)

        user_input = payload["conversationState"]["currentMessage"]["userInputMessage"]
        self.assertTrue(user_input["content"].startswith("x-anthropic-billing-header:"))
        self.assertEqual(len(user_input["userInputMessageContext"]["tools"]), 2)

    def test_codex_responses_stream_fixture_regression(self):
        fixture = _load_fixture("responses_codex_stream.json")
        stream_chunks = [
            _aws_event_chunk(
                {"assistantResponseEvent": {"content": "Summary: profileArn missing."}},
                "assistantResponseEvent",
            ),
            _aws_event_chunk(
                {"assistantResponseEvent": {"content": " Token import is stale."}},
                "assistantResponseEvent",
            ),
            _aws_event_chunk(
                {
                    "toolUseId": "call_fix",
                    "name": "local_shell",
                    "input": "{\"command\":[\"python3\",\"run.py\"]}",
                },
                "toolUseEvent",
            ),
        ]
        upstream = _UpstreamStub(stream_response=_FakeHTTPResponse(status_code=200, chunks=stream_chunks))
        account = _DummyAccount()

        with self._patch_runtime(upstream, account):
            with TestClient(app) as client:
                resp = client.post("/v1/responses", json=fixture["request"])

        self.assertEqual(resp.status_code, 200)
        self.assertIn("event: response.created", resp.text)
        self.assertIn("event: response.output_text.delta", resp.text)
        self.assertIn("event: response.completed", resp.text)
        self.assertIn('"type": "function_call"', resp.text)
        self.assertIn("call_fix", resp.text)

        self.assertEqual(len(upstream.stream_requests), 1)
        payload = upstream.stream_requests[0]["json"]
        self.assertEqual(payload.get("profileArn"), account.get_credentials().profile_arn)

        user_input = payload["conversationState"]["currentMessage"]["userInputMessage"]
        self.assertIn("You are Codex.", user_input["content"])
        self.assertIn("Continue and summarize what failed.", user_input["content"])

        ctx = user_input["userInputMessageContext"]
        self.assertTrue(any("webSearchTool" in t for t in ctx.get("tools", [])))

        history = payload["conversationState"].get("history", [])
        history_tool_result_ids = set()
        for item in history:
            user = item.get("userInputMessage")
            if not user:
                continue
            for tr in user.get("userInputMessageContext", {}).get("toolResults", []) or []:
                if tr.get("toolUseId"):
                    history_tool_result_ids.add(tr["toolUseId"])
        self.assertTrue({"fc_1", "sh_1", "ts_1"}.issubset(history_tool_result_ids))

        assistant_texts = [
            m["assistantResponseMessage"]["content"]
            for m in history
            if "assistantResponseMessage" in m
        ]
        self.assertTrue(any("[web_search_call:" in t for t in assistant_texts))
        self.assertTrue(any("[image_generation_call:" in t for t in assistant_texts))

        tool_use_ids = set()
        for item in history:
            if "assistantResponseMessage" not in item:
                continue
            for tool_use in item["assistantResponseMessage"].get("toolUses", []) or []:
                tool_use_ids.add(tool_use.get("toolUseId"))
        self.assertTrue({"fc_1", "sh_1", "ts_1"}.issubset(tool_use_ids))

    def test_gemini_generate_content_fixture_regression(self):
        fixture = _load_fixture("gemini_cli_generate_content.json")
        post_content = b"".join(
            [
                _aws_event_chunk(
                    {"assistantResponseEvent": {"content": "已读取 README，项目用于协议代理。"}},
                    "assistantResponseEvent",
                ),
                _aws_event_chunk(
                    {
                        "toolUseId": "call_followup",
                        "name": "read_file",
                        "input": "{\"path\":\"README_EN.md\"}",
                    },
                    "toolUseEvent",
                ),
            ]
        )

        upstream = _UpstreamStub(post_response=_FakeHTTPResponse(status_code=200, content=post_content))
        account = _DummyAccount()

        with self._patch_runtime(upstream, account):
            with TestClient(app) as client:
                path = f"/v1/models/{fixture['path_model']}:generateContent"
                resp = client.post(path, json=fixture["request"])

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        parts = data["candidates"][0]["content"]["parts"]
        self.assertEqual(parts[0]["text"], "已读取 README，项目用于协议代理。")
        self.assertEqual(parts[1]["functionCall"]["id"], "call_followup")
        self.assertEqual(parts[1]["functionCall"]["name"], "read_file")

        self.assertEqual(len(upstream.post_requests), 1)
        payload = upstream.post_requests[0]["json"]
        self.assertEqual(payload.get("profileArn"), account.get_credentials().profile_arn)

        user_input = payload["conversationState"]["currentMessage"]["userInputMessage"]
        self.assertEqual(user_input["content"], "再看这张图并继续。")
        self.assertEqual(len(user_input.get("images", [])), 1)
        self.assertEqual(user_input["images"][0]["source"]["bytes"], "QUJD")

        ctx = user_input["userInputMessageContext"]
        self.assertTrue(any("toolSpecification" in t for t in ctx.get("tools", [])))
        self.assertGreaterEqual(sum(1 for t in ctx.get("tools", []) if "webSearchTool" in t), 2)

        history = payload["conversationState"].get("history", [])
        has_tool_result = False
        for item in history:
            user = item.get("userInputMessage")
            if not user:
                continue
            if "你是 Gemini CLI。" in user.get("content", ""):
                self.assertIn("Allowed tools: read_file", user["content"])
            tr = user.get("userInputMessageContext", {}).get("toolResults", [])
            if tr and tr[0].get("toolUseId") == "call_readme":
                has_tool_result = True
                break
        self.assertTrue(has_tool_result)


if __name__ == "__main__":
    unittest.main()
