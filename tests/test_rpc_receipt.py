"""Receipt polling cadence of the direct-mode RPC client (Base Denim: 200 ms blocks)."""

import json

import httpx
import pytest
import respx

from veranta_sdk.execution.rpc import JsonRpcClient

RPC = "https://rpc.test"
RECEIPT = {"status": "0x1", "blockNumber": "0x10"}


def _receipt_arrives_on_poll(n: int) -> dict[str, int]:
    """Mock the RPC so the receipt shows up on the n-th eth_getTransactionReceipt call."""
    polls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        result = None
        if body["method"] == "eth_getTransactionReceipt":
            polls["count"] += 1
            result = RECEIPT if polls["count"] >= n else None
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result})

    respx.post(RPC).mock(side_effect=handler)
    return polls


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record every asyncio.sleep the client asks for, without sleeping."""
    recorded: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        recorded.append(seconds)

    monkeypatch.setattr("veranta_sdk.execution.rpc.asyncio.sleep", fake_sleep)
    return recorded


@respx.mock
async def test_wait_for_receipt_polls_every_quarter_second_by_default(sleeps: list[float]):
    polls = _receipt_arrives_on_poll(4)
    client = JsonRpcClient(RPC)
    try:
        receipt = await client.wait_for_receipt("0xabc")
    finally:
        await client.aclose()
    assert receipt == RECEIPT
    assert polls["count"] == 4
    assert sleeps == [0.25, 0.25, 0.25]


@respx.mock
async def test_wait_for_receipt_keeps_poll_s_as_an_option(sleeps: list[float]):
    polls = _receipt_arrives_on_poll(3)
    client = JsonRpcClient(RPC)
    try:
        receipt = await client.wait_for_receipt("0xabc", poll_s=1.0)
    finally:
        await client.aclose()
    assert receipt == RECEIPT
    assert polls["count"] == 3
    assert sleeps == [1.0, 1.0]
