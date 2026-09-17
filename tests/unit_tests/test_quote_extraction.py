"""Unit tests for agent.quote_extraction, with a scripted stand-in for the model.

No Ollama needed: ChatOllama is replaced by a fake that returns canned
replies, so the parsing and retry behavior is tested deterministically.
"""

import json

import pytest

from agent import quote_extraction
from agent.quote_extraction import extract_quote_fields

pytestmark = pytest.mark.anyio

VALID_REPLY = json.dumps(
    {
        "vendor_name": "Acme Co.",
        "quote_no": "QT-1",
        "quote_date": "08/09/2026",
        "buyer_name": "Agent Tech",
        "items": [
            {
                "description": "Chair",
                "qty": "10",
                "unit_price": "2,500.00",
                "amount": "25,000.00",
            }
        ],
        "subtotal": "25,000.00",
        "vat": "1,750.00",
        "grand_total": "26,750.00",
    }
)


class _Reply:
    def __init__(self, content: str) -> None:
        self.content = content


class ScriptedChat:
    """Replays scripted replies (or raises scripted exceptions) in order."""

    def __init__(self, *replies: str | Exception) -> None:
        self.replies = list(replies)
        self.calls: list[list[tuple[str, str]]] = []

    def __call__(self, **_kwargs: object) -> "ScriptedChat":
        return self

    async def ainvoke(self, messages: list[tuple[str, str]]) -> _Reply:
        self.calls.append(list(messages))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return _Reply(reply)


def _use(monkeypatch: pytest.MonkeyPatch, chat: ScriptedChat) -> ScriptedChat:
    monkeypatch.setattr(quote_extraction, "ChatOllama", chat)
    return chat


async def _extract() -> quote_extraction.QuoteFields:
    return await extract_quote_fields("quote text", model="m", base_url="http://x")


async def test_valid_reply_needs_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    chat = _use(monkeypatch, ScriptedChat(VALID_REPLY))

    fields = await _extract()

    assert fields.error is None
    assert fields.vendor_name == "Acme Co."
    assert fields.items[0].amount == "25,000.00"
    assert len(chat.calls) == 1


async def test_code_fenced_reply_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, ScriptedChat(f"```json\n{VALID_REPLY}\n```"))

    fields = await _extract()

    assert fields.error is None
    assert fields.grand_total == "26,750.00"


async def test_invalid_json_is_retried_with_feedback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat = _use(monkeypatch, ScriptedChat("Sure! Here is the data: {oops", VALID_REPLY))

    fields = await _extract()

    assert fields.error is None
    assert fields.quote_no == "QT-1"
    assert len(chat.calls) == 2
    # The retry must carry the rejected reply and the reason, not just repeat
    # the original prompt (at temperature=0 that would repeat the bad reply).
    retry = chat.calls[1]
    assert ("ai", "Sure! Here is the data: {oops") in retry
    assert "rejected" in retry[-1][1]


async def test_non_object_json_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    chat = _use(monkeypatch, ScriptedChat("[]", VALID_REPLY))

    fields = await _extract()

    assert fields.error is None
    assert len(chat.calls) == 2
    assert "expected a JSON object, got list" in chat.calls[1][-1][1]


async def test_gives_up_after_max_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    chat = _use(monkeypatch, ScriptedChat("nope", "still nope", "nope again"))

    fields = await _extract()

    assert fields.error is not None
    assert "after 3 attempts" in fields.error
    assert fields.vendor_name == ""
    assert len(chat.calls) == 3


async def test_failed_model_call_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat = _use(
        monkeypatch, ScriptedChat(ConnectionError("All connection attempts failed"))
    )

    fields = await _extract()

    assert fields.error == "Model call failed: All connection attempts failed"
    assert len(chat.calls) == 1
