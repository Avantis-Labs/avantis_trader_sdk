"""Batched-market execution client (``POST /market/execute-batched``).

The batched-market service (avantis-backend-monorepo
src/market-app/batched-market) is the front door for market execution: one
endpoint for every supported order type, streaming the order lifecycle back
as Server-Sent Events over the POST response.

Request body (``erc712`` required, ``eip7702`` OPTIONAL — when present the
server picks which mechanism to act on via its own strategy switch, so ops
can move between EIP-712 and EIP-7702 without client releases; when omitted
the server executes the EIP-712 intent directly, which is the market-maker
fast path with zero extra round-trips):

    {
      "orderType": <AggregatorOrderType int>,
      "erc712":  { "userIntent": "0x…", "userSignature": "0x…" },
      "eip7702": { "chainId": "8453", "to": "0x…", "data": "0x…",
                   "gas": "2500000", "authorizationList": [...] }   # optional
    }

Stream: ``MarketOrderAccepted`` (seq 0, carries trackingId) -> one initiation
event (``MarketOrderInitiated`` for opens/closes, ``IncreasePositionRequested``
for increases) -> exactly one terminal event (``MarketOrderExecuted`` /
``PositionSizeIncreased`` on success; ``MarketOrderCanceled`` when the protocol
declined the fill, e.g. slippage; ``Error``). The success terminals carry the
final on-chain fill (server market-fill-details.ts, a published contract):
``MarketOrderExecuted`` has ``orderId``, ``transactionHash``, ``price``,
``positionSizeUSDC``, ``percentProfit``, ``usdcSentToTrader``, ``isPnl``,
``coinExposure`` and the stored trade tuple ``t`` (incl. ``initialPosToken``
= final collateral, ``leverage``, ``openPrice``, ``tp``/``sl``);
``PositionSizeIncreased`` has ``coinExposureAdded`` + ``t`` = the blended
resulting position. All uints are strings in raw units (1e6 USDC, 1e10
prices/leverage). Keep-alives are SSE comments
(``: hb``). A dropped stream is recoverable via
``GET /tracking-id/{trackingId}/status?afterSeq={lastSeenSeq}`` — every event
is persisted with its seq, so the replay is complete.

Transport-only quirk: the server's stream-expiry / enqueue-failure ``Error``
events are written without an ``id:`` line (they are not persisted). An
``Error`` WITHOUT a seq therefore means "stream view timed out — the order may
still execute", and this client falls back to status polling; an ``Error``
WITH a seq is a real terminal failure.
"""

from __future__ import annotations

import asyncio
import json as jsonlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from ..errors import ApiError, RelayError, RelayTimeoutError
from ..transport import HttpTransport

ACCEPTED = "MarketOrderAccepted"
TERMINAL_SUCCESS = frozenset({"MarketOrderExecuted", "PositionSizeIncreased"})
TERMINAL_FAILURE = frozenset({"MarketOrderCanceled", "Error"})
TERMINAL = TERMINAL_SUCCESS | TERMINAL_FAILURE

# Server heartbeats every 15s; anything above that with margin works.
_SSE_READ_TIMEOUT_S = 45.0


@dataclass
class BatchedMarketEvent:
    type: str
    data: dict[str, Any]
    seq: int | None = None


@dataclass
class BatchedMarketOutcome:
    """Result of a batched-market execution.

    ``terminal`` is None only for ``wait=False`` submissions (accepted, not
    yet settled). Failure terminals raise instead of being returned.
    """

    tracking_id: str
    terminal: BatchedMarketEvent | None
    events: list[BatchedMarketEvent]

    @property
    def tx_hash(self) -> str | None:
        for ev in reversed(self.events):
            h = ev.data.get("transactionHash")
            if h:
                return str(h)
        return None

    @property
    def order_id(self) -> int | None:
        for ev in reversed(self.events):
            if "orderId" in ev.data:
                return int(ev.data["orderId"])
        return None


class BatchedMarketClient:
    def __init__(
        self,
        transport: HttpTransport,
        base_url: str,
        *,
        poll_interval_s: float = 1.0,
        timeout_s: float = 90.0,
    ) -> None:
        self._t = transport
        self._base = base_url.rstrip("/")
        self.poll_interval_s = poll_interval_s
        self.timeout_s = timeout_s

    # ------------------------------------------------------------------ execute

    async def execute(
        self,
        order_type: int,
        erc712: dict[str, Any],
        eip7702: dict[str, Any] | None = None,
        *,
        wait: bool = True,
    ) -> BatchedMarketOutcome:
        """Submit a signed order and follow its lifecycle stream.

        ``eip7702`` is optional: when provided the server may execute either
        leg (server-side mechanism switch); when omitted the EIP-712 intent
        executes directly (market-maker fast path).

        With ``wait=False`` returns as soon as the request is accepted
        (trackingId minted); settle later with :meth:`wait`.
        Raises :class:`RelayError` on ``MarketOrderCanceled`` / terminal
        ``Error``, :class:`ApiError` on a 4xx/5xx rejection.
        """
        body: dict[str, Any] = {"orderType": int(order_type), "erc712": erc712}
        if eip7702 is not None:
            body["eip7702"] = eip7702
        url = f"{self._base}/market/execute-batched"

        tracking_id: str | None = None
        events: list[BatchedMarketEvent] = []
        try:
            async with self._t.stream(
                "POST", url, json=body, read_timeout_s=_SSE_READ_TIMEOUT_S
            ) as resp:
                if resp.status_code >= 400:
                    raise await _http_error(resp, url)
                async for ev in _iter_sse(resp):
                    events.append(ev)
                    if ev.type == ACCEPTED:
                        tracking_id = str(ev.data.get("trackingId") or "") or tracking_id
                        if not wait:
                            return BatchedMarketOutcome(
                                tracking_id=tracking_id or "", terminal=None, events=events
                            )
                        continue
                    if ev.type in TERMINAL:
                        if ev.type == "Error" and ev.seq is None:
                            # Transport-only event: stream expiry (order may
                            # still land -> poll) or enqueue failure (final).
                            msg = str(ev.data.get("message", ""))
                            if "timed out" in msg.lower() and tracking_id:
                                break  # fall through to status polling
                            raise RelayError(
                                f"batched-market rejected the order: {msg or ev.data}",
                                request_id=tracking_id,
                            )
                        return self._settle(tracking_id, ev, events)
        except httpx.HTTPError as exc:
            # Connection dropped mid-stream; the order may still be executing.
            if tracking_id is None:
                raise ApiError(f"batched-market stream failed: {exc}", url=url) from exc

        if tracking_id is None:
            raise ApiError(
                "batched-market stream ended before MarketOrderAccepted", url=url
            )
        return await self.wait(tracking_id, after_seq=_last_seq(events), events=events)

    # ------------------------------------------------------------------ status

    async def status(
        self, tracking_id: str, after_seq: int | None = None
    ) -> list[BatchedMarketEvent]:
        """Replay the persisted lifecycle events for a trackingId."""
        params = {"afterSeq": after_seq} if after_seq is not None else None
        data = await self._t.json(
            "GET", f"{self._base}/tracking-id/{tracking_id}/status", params=params
        )
        return [
            BatchedMarketEvent(
                type=str(e.get("type")), data=e.get("payload") or {}, seq=e.get("seq")
            )
            for e in (data or {}).get("events", [])
        ]

    async def wait(
        self,
        tracking_id: str,
        *,
        after_seq: int | None = None,
        events: list[BatchedMarketEvent] | None = None,
        timeout_s: float | None = None,
    ) -> BatchedMarketOutcome:
        """Poll the status replay until a terminal event lands."""
        collected = list(events or [])
        seen_seq = after_seq
        deadline = asyncio.get_event_loop().time() + (
            timeout_s if timeout_s is not None else self.timeout_s
        )
        while asyncio.get_event_loop().time() < deadline:
            for ev in await self.status(tracking_id, after_seq=seen_seq):
                collected.append(ev)
                if ev.seq is not None:
                    seen_seq = ev.seq
                if ev.type in TERMINAL:
                    return self._settle(tracking_id, ev, collected)
            await asyncio.sleep(self.poll_interval_s)
        raise RelayTimeoutError(
            f"batched-market order {tracking_id} not settled after "
            f"{timeout_s if timeout_s is not None else self.timeout_s:.0f}s",
            request_id=tracking_id,
        )

    # ------------------------------------------------------------------ internal

    def _settle(
        self,
        tracking_id: str | None,
        terminal: BatchedMarketEvent,
        events: list[BatchedMarketEvent],
    ) -> BatchedMarketOutcome:
        outcome = BatchedMarketOutcome(
            tracking_id=tracking_id or "", terminal=terminal, events=events
        )
        if terminal.type == "MarketOrderCanceled":
            raise RelayError(
                "order canceled by the protocol (the transaction succeeded but the "
                f"fill was declined, e.g. slippage): {terminal.data}",
                request_id=tracking_id,
            )
        if terminal.type == "Error":
            raise RelayError(
                f"batched-market execution failed: "
                f"{terminal.data.get('message') or terminal.data}",
                request_id=tracking_id,
            )
        return outcome


def _last_seq(events: list[BatchedMarketEvent]) -> int | None:
    seqs = [ev.seq for ev in events if ev.seq is not None]
    return max(seqs) if seqs else None


async def _http_error(resp: httpx.Response, url: str) -> ApiError:
    raw = (await resp.aread()).decode(errors="replace")
    message = raw[:300]
    try:
        body = jsonlib.loads(raw)
        m = body.get("message")
        message = "; ".join(m) if isinstance(m, list) else str(m or raw[:300])
    except ValueError:
        pass
    return ApiError(
        f"batched-market rejected the request ({resp.status_code}): {message}",
        status=resp.status_code,
        url=url,
    )


async def _iter_sse(resp: httpx.Response) -> AsyncIterator[BatchedMarketEvent]:
    """Minimal SSE parser: ``id:``/``event:``/``data:`` fields, blank-line
    dispatch, ``:`` comments and ``retry:`` ignored. Multi-line data joined
    per the SSE spec."""
    event_type: str | None = None
    data_lines: list[str] = []
    seq: int | None = None

    async for line in resp.aiter_lines():
        line = line.rstrip("\r")
        if line == "":
            if event_type is not None or data_lines:
                data: dict[str, Any] = {}
                raw = "\n".join(data_lines)
                if raw:
                    try:
                        parsed = jsonlib.loads(raw)
                        data = parsed if isinstance(parsed, dict) else {"value": parsed}
                    except ValueError:
                        data = {"raw": raw}
                yield BatchedMarketEvent(type=event_type or "message", data=data, seq=seq)
            event_type, data_lines, seq = None, [], None
            continue
        if line.startswith(":"):
            continue  # comment / keep-alive
        field, _, value = line.partition(":")
        value = value.removeprefix(" ")
        if field == "event":
            event_type = value
        elif field == "data":
            data_lines.append(value)
        elif field == "id":
            try:
                seq = int(value)
            except ValueError:
                seq = None
        # "retry" and unknown fields are ignored
