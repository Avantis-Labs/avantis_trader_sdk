"""BatchedMarketClient unit tests: SSE parsing (heartbeats, ids, comments),
terminal mapping, non-terminal AttemptFailed events, machine-readable Error
codes (STREAM_TIMEOUT -> status-replay fallback, others -> RelayError.code),
unknown-event tolerance, and 4xx error mapping."""

import json

import httpx
import pytest
import respx

from avantis_trader_sdk.errors import ApiError, RelayError
from avantis_trader_sdk.execution.batched_market import BatchedMarketClient
from avantis_trader_sdk.transport import HttpTransport

BASE = "https://batched.test"

ERC712 = {"userIntent": "0x" + "ab" * 8, "userSignature": "0x" + "cd" * 65}
EIP7702 = {
    "chainId": "31337",
    "to": "0x1111111111111111111111111111111111111111",
    "data": "0xdeadbeef",
    "gas": "2500000",
    "authorizationList": [],
}


def _sse_bytes(*events: tuple[int | None, str, dict], heartbeats: bool = True) -> bytes:
    frames = ["retry: 3000\n\n", ": open\n\n"]
    for i, (seq, event_type, payload) in enumerate(events):
        if heartbeats and i == 1:
            frames.append(": hb\n\n")  # keep-alive comment mid-stream
        frame = ""
        if seq is not None:
            frame += f"id: {seq}\n"
        frame += f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
        frames.append(frame)
    return "".join(frames).encode()


def _sse_response(*events, **kw) -> httpx.Response:
    return httpx.Response(
        200,
        content=_sse_bytes(*events, **kw),
        headers={"content-type": "text/event-stream; charset=utf-8"},
    )


@pytest.fixture
async def client():
    transport = HttpTransport()
    yield BatchedMarketClient(transport, BASE, poll_interval_s=0.01, timeout_s=1.0)
    await transport.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_execute_success_parses_lifecycle(client):
    route = respx.post(f"{BASE}/market/execute-batched").mock(
        return_value=_sse_response(
            (0, "MarketOrderAccepted", {"trackingId": "trk-1"}),
            (1, "MarketOrderInitiated", {"orderId": 9, "transactionHash": "0xinit"}),
            (2, "MarketOrderExecuted", {"orderId": 9, "transactionHash": "0xdone"}),
        )
    )

    outcome = await client.execute(0, ERC712, EIP7702)

    assert outcome.tracking_id == "trk-1"
    assert outcome.terminal is not None and outcome.terminal.type == "MarketOrderExecuted"
    assert outcome.terminal.seq == 2
    assert outcome.tx_hash == "0xdone"  # latest transactionHash wins
    assert outcome.order_id == 9
    assert [e.type for e in outcome.events] == [
        "MarketOrderAccepted",
        "MarketOrderInitiated",
        "MarketOrderExecuted",
    ]
    body = json.loads(route.calls[0].request.content)
    assert body == {"orderType": 0, "erc712": ERC712, "eip7702": EIP7702}


@pytest.mark.asyncio
@respx.mock
async def test_execute_without_eip7702_omits_field(client):
    """The EIP-7702 leg is optional (MM fast path): when not provided the
    request body must not carry an ``eip7702`` key at all."""
    route = respx.post(f"{BASE}/market/execute-batched").mock(
        return_value=_sse_response(
            (0, "MarketOrderAccepted", {"trackingId": "trk-fast"}),
            (1, "MarketOrderExecuted", {"orderId": 7, "transactionHash": "0xfast"}),
        )
    )

    outcome = await client.execute(0, ERC712)

    assert outcome.tracking_id == "trk-fast"
    assert outcome.tx_hash == "0xfast"
    body = json.loads(route.calls[0].request.content)
    assert body == {"orderType": 0, "erc712": ERC712}


@pytest.mark.asyncio
@respx.mock
async def test_execute_no_wait_returns_after_accepted(client):
    respx.post(f"{BASE}/market/execute-batched").mock(
        return_value=_sse_response((0, "MarketOrderAccepted", {"trackingId": "trk-2"}))
    )
    outcome = await client.execute(1, ERC712, EIP7702, wait=False)
    assert outcome.tracking_id == "trk-2"
    assert outcome.terminal is None and outcome.tx_hash is None


@pytest.mark.asyncio
@respx.mock
async def test_terminal_error_with_seq_raises(client):
    respx.post(f"{BASE}/market/execute-batched").mock(
        return_value=_sse_response(
            (0, "MarketOrderAccepted", {"trackingId": "trk-3"}),
            (1, "Error", {"message": "no price available"}),
        )
    )
    with pytest.raises(RelayError, match="no price available") as exc:
        await client.execute(0, ERC712, EIP7702)
    assert exc.value.request_id == "trk-3"


@pytest.mark.asyncio
@respx.mock
async def test_stream_timeout_falls_back_to_status_replay(client):
    """The expiry Error has NO id line (not persisted); the client must poll
    the status endpoint instead of failing."""
    respx.post(f"{BASE}/market/execute-batched").mock(
        return_value=_sse_response(
            (0, "MarketOrderAccepted", {"trackingId": "trk-4"}),
            (None, "Error", {"message": "Stream timed out. The request may still be executing", "trackingId": "trk-4"}),
        )
    )
    status_route = respx.get(f"{BASE}/tracking-id/trk-4/status").mock(
        side_effect=[
            httpx.Response(200, json={"events": []}),
            httpx.Response(
                200,
                json={
                    "events": [
                        {"seq": 1, "type": "MarketOrderInitiated", "payload": {"orderId": 3, "transactionHash": "0xi"}},
                        {"seq": 2, "type": "MarketOrderExecuted", "payload": {"orderId": 3, "transactionHash": "0xok"}},
                    ]
                },
            ),
        ]
    )

    outcome = await client.execute(0, ERC712, EIP7702)

    assert outcome.tx_hash == "0xok"
    assert outcome.terminal.type == "MarketOrderExecuted"
    # resume passed the last persisted seq (0 = the accepted event)
    assert status_route.calls[0].request.url.params["afterSeq"] == "0"


@pytest.mark.asyncio
@respx.mock
async def test_stream_ending_without_terminal_polls_status(client):
    respx.post(f"{BASE}/market/execute-batched").mock(
        return_value=_sse_response((0, "MarketOrderAccepted", {"trackingId": "trk-5"}))
    )
    respx.get(f"{BASE}/tracking-id/trk-5/status").mock(
        return_value=httpx.Response(
            200,
            json={
                "events": [
                    {"seq": 1, "type": "MarketOrderCanceled", "payload": {"orderId": 4}}
                ]
            },
        )
    )
    with pytest.raises(RelayError, match="canceled"):
        await client.execute(0, ERC712, EIP7702)


@pytest.mark.asyncio
@respx.mock
async def test_enqueue_failure_error_raises_immediately(client):
    respx.post(f"{BASE}/market/execute-batched").mock(
        return_value=_sse_response(
            (0, "MarketOrderAccepted", {"trackingId": "trk-6"}),
            (None, "Error", {"message": "Could not schedule execution: queue full"}),
        )
    )
    with pytest.raises(RelayError, match="queue full"):
        await client.execute(0, ERC712, EIP7702)


@pytest.mark.asyncio
@respx.mock
async def test_attempt_failed_events_are_non_terminal(client):
    """AttemptFailed reports one retryable attempt while the backend keeps
    working the request — the stream must continue to the real terminal, and
    the failures stay inspectable on the outcome."""
    respx.post(f"{BASE}/market/execute-batched").mock(
        return_value=_sse_response(
            (0, "MarketOrderAccepted", {"trackingId": "trk-af"}),
            (1, "AttemptFailed", {"attempt": 1, "code": "NO_PRICE", "message": "no fresh price", "willRetry": True}),
            (2, "AttemptFailed", {"attempt": 2, "code": "SPREAD_BLOCKED", "message": "spread too wide", "willRetry": True}),
            (3, "MarketOrderInitiated", {"orderId": 12, "transactionHash": "0xinit"}),
            (4, "MarketOrderExecuted", {"orderId": 12, "transactionHash": "0xok"}),
        )
    )

    outcome = await client.execute(0, ERC712, EIP7702)

    assert outcome.terminal.type == "MarketOrderExecuted"
    assert [e.data["code"] for e in outcome.attempt_failures] == [
        "NO_PRICE",
        "SPREAD_BLOCKED",
    ]


@pytest.mark.asyncio
@respx.mock
async def test_unknown_event_types_are_ignored(client):
    """The server adds non-terminal event types without a version bump; the
    client must skip anything not on the terminal allow-list."""
    respx.post(f"{BASE}/market/execute-batched").mock(
        return_value=_sse_response(
            (0, "MarketOrderAccepted", {"trackingId": "trk-unk"}),
            (1, "SomeFutureDiagnostic", {"detail": "ignore me"}),
            (2, "MarketOrderExecuted", {"orderId": 5, "transactionHash": "0xok"}),
        )
    )

    outcome = await client.execute(0, ERC712, EIP7702)
    assert outcome.terminal.type == "MarketOrderExecuted"
    assert outcome.tx_hash == "0xok"


@pytest.mark.asyncio
@respx.mock
async def test_terminal_error_carries_machine_code(client):
    """Persisted terminal Errors now carry a machine-readable ``code`` (bare
    contract error name or synthetic backend code) — surfaced on RelayError."""
    respx.post(f"{BASE}/market/execute-batched").mock(
        return_value=_sse_response(
            (0, "MarketOrderAccepted", {"trackingId": "trk-code"}),
            (1, "Error", {"status": "failed", "code": "WrongSl", "message": "execution reverted: WrongSl"}),
        )
    )
    with pytest.raises(RelayError, match=r"\[WrongSl\]") as exc:
        await client.execute(0, ERC712, EIP7702)
    assert exc.value.code == "WrongSl"
    assert exc.value.request_id == "trk-code"


@pytest.mark.asyncio
@respx.mock
async def test_stream_timeout_code_falls_back_to_status_replay(client):
    """code=STREAM_TIMEOUT means only this connection's view expired — the
    client must recover via the status endpoint even though the payload no
    longer matches the old 'timed out' message sniff exactly."""
    respx.post(f"{BASE}/market/execute-batched").mock(
        return_value=_sse_response(
            (0, "MarketOrderAccepted", {"trackingId": "trk-st"}),
            (None, "Error", {"code": "STREAM_TIMEOUT", "message": "Stream view expired", "trackingId": "trk-st"}),
        )
    )
    respx.get(f"{BASE}/tracking-id/trk-st/status").mock(
        return_value=httpx.Response(
            200,
            json={
                "events": [
                    {"seq": 1, "type": "MarketOrderExecuted", "payload": {"orderId": 8, "transactionHash": "0xrec"}}
                ]
            },
        )
    )

    outcome = await client.execute(0, ERC712, EIP7702)
    assert outcome.tx_hash == "0xrec"


@pytest.mark.asyncio
@respx.mock
async def test_enqueue_failed_code_raises_with_code(client):
    respx.post(f"{BASE}/market/execute-batched").mock(
        return_value=_sse_response(
            (0, "MarketOrderAccepted", {"trackingId": "trk-eq"}),
            (None, "Error", {"code": "ENQUEUE_FAILED", "message": "Could not schedule execution"}),
        )
    )
    with pytest.raises(RelayError, match="Could not schedule") as exc:
        await client.execute(0, ERC712, EIP7702)
    assert exc.value.code == "ENQUEUE_FAILED"


@pytest.mark.asyncio
@respx.mock
async def test_http_400_maps_to_api_error(client):
    respx.post(f"{BASE}/market/execute-batched").mock(
        return_value=httpx.Response(
            400,
            json={
                "statusCode": 400,
                "message": ["orderType must be one of the supported values"],
                "error": "Bad Request",
            },
        )
    )
    with pytest.raises(ApiError, match="orderType must be one of") as exc:
        await client.execute(99, ERC712, EIP7702)
    assert exc.value.status == 400
