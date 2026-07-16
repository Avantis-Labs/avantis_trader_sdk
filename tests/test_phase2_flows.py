"""Phase 2 flow tests: off-chain TP/SL, gasless referral, direct route via
RPC, delegate registration, and the delegate-identity guard."""

import json

import httpx
import pytest
import respx

from avantis_trader_sdk import AsyncAvantis
from avantis_trader_sdk.errors import ConfigError
from avantis_trader_sdk.intents_schema import INTENT_TYPES
from tests.conftest import META, TEST_ADDRESS, TEST_KEY, TRADER, VECTORS

TXB = "https://txb.test"
RELAYER = "https://relayer.test"
CORE = "https://core.test"
RPC = "https://rpc.test"


def _ok(data):
    return httpx.Response(200, json={"ok": True, "data": data})


def _client(**kw) -> AsyncAvantis:
    defaults = dict(
        network="testnet",
        private_key=TEST_KEY,
        trader_address=TRADER,
        tx_builder_url=TXB,
        relayer_url=RELAYER,
        core_api_url=CORE,
        relay_poll_interval_s=0.01,
    )
    defaults.update(kw)
    return AsyncAvantis(**defaults)


def _vector_payload(kind: str, **extra) -> dict:
    vector = next(v for v in VECTORS["vectors"] if v["kind"] == kind)
    return {
        "intent": kind,
        "signerRule": "trader-or-delegate",
        "domain": VECTORS["domain"],
        "primaryType": kind,
        "types": INTENT_TYPES[kind],
        "message": vector["message"],
        "digest": vector["digest"],
        "encodedIntent": "0x" + "cd" * 32,
        **extra,
    }


@pytest.mark.asyncio
@respx.mock
async def test_offchain_partial_tpsl_submit():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/intents/tpsl-partial").mock(
        return_value=_ok(_vector_payload("TpSlReq"))
    )
    put_route = respx.put(f"{CORE}/offchain-orders").mock(
        return_value=httpx.Response(200, json={})
    )

    async with _client() as client:
        submission = await client.trade.partial_tp_sl(
            "ETH/USD", 0, side="long", kind="tp", coin_exposure="0.5", price=4000
        )

    assert put_route.called
    body = json.loads(put_route.calls[0].request.content)
    vec_msg = next(v for v in VECTORS["vectors"] if v["kind"] == "TpSlReq")["message"]
    assert body["trader"] == vec_msg["trader"]
    assert body["signTimestamp"] == int(vec_msg["signTimestamp"])
    assert body["signedMessage"].startswith("0x") and len(body["signedMessage"]) == 132
    assert submission["orderType"] == int(vec_msg["orderType"])


@pytest.mark.asyncio
@respx.mock
async def test_offchain_partial_tpsl_cancel_signs_same_digest():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/intents/tpsl-partial").mock(
        return_value=_ok(_vector_payload("TpSlReq"))
    )
    respx.put(f"{CORE}/offchain-orders").mock(return_value=httpx.Response(200, json={}))
    delete_route = respx.delete(f"{CORE}/offchain-orders").mock(
        return_value=httpx.Response(200, json={})
    )

    async with _client() as client:
        submission = await client.trade.partial_tp_sl(
            "ETH/USD", 0, side="long", kind="tp", coin_exposure="0.5", price=4000
        )
        await client.trade.cancel_partial_tp_sl(submission)

    assert delete_route.called
    params = dict(delete_route.calls[0].request.url.params)
    # cancel re-signs the same TpSlReq -> byte-identical signature.
    # (conftest META uses the golden-vector domain: chainId 31337 + same router)
    assert params["signedMessage"] == submission["signedMessage"]


@pytest.mark.asyncio
@respx.mock
async def test_referral_register_gasless_wraps_with_sig():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    payload = _vector_payload("RegisterCodeReq")
    payload["domain"] = dict(VECTORS["domain"])  # referral domain (same shape)
    respx.post(f"{TXB}/v2/intents/referral-register-code").mock(return_value=_ok(payload))
    queue_route = respx.post(f"{RELAYER}/relays").mock(
        return_value=httpx.Response(200, json={"requestId": "r1"})
    )
    respx.get(f"{RELAYER}/relays/r1").mock(
        return_value=httpx.Response(
            200,
            json={"requestId": "r1", "status": "Finalised",
                  "receipt": {"transactionHash": "0xr", "status": "0x1"}},
        )
    )

    # trader-key mode (signer == trader) so referral actions are allowed
    async with _client(trader_address=TEST_ADDRESS) as client:
        receipt = await client.referral.register_code_gasless("MYCODE")

    assert receipt.tx_hash == "0xr"
    body = json.loads(queue_route.calls[0].request.content)
    tx = body["txParams"]
    assert tx["transactionType"] == 4
    assert tx["data"].startswith("0xe9ae5c53")  # execute() wrapper


@pytest.mark.asyncio
@respx.mock
async def test_referral_direct_action_blocked_in_delegate_mode():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    async with _client() as client:  # trader != signer -> delegate mode
        with pytest.raises(ConfigError, match="delegate"):
            await client.referral.register_code("MYCODE")


@pytest.mark.asyncio
@respx.mock
async def test_direct_route_via_rpc():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/trade/open").mock(
        return_value=_ok(
            {
                "to": META["addresses"]["tradingRouter"],
                "from": TEST_ADDRESS,
                "data": "0xdeadbeef",
                "value": "0x0",
                "chainId": 31337,
                "description": "open",
            }
        )
    )

    sent = {}

    def rpc_handler(request):
        body = json.loads(request.content)
        method = body["method"]
        result = {
            "eth_getTransactionCount": "0x5",
            "eth_estimateGas": "0x30d40",
            "eth_maxPriorityFeePerGas": "0xf4240",
            "eth_getBlockByNumber": {"baseFeePerGas": "0x3b9aca00"},
            "eth_sendRawTransaction": "0x" + "11" * 32,
            "eth_getTransactionReceipt": {"status": "0x1", "transactionHash": "0x" + "11" * 32},
        }[method]
        if method == "eth_sendRawTransaction":
            sent["raw"] = body["params"][0]
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result})

    respx.post(RPC).mock(side_effect=rpc_handler)

    # trader-key mode, direct execution
    async with _client(
        trader_address=TEST_ADDRESS, execution="direct", rpc_url=RPC
    ) as client:
        receipt = await client.trade.market_open("ETH/USD", "long", collateral=100, leverage=10)

    assert receipt.route == "rpc"
    assert receipt.tx_hash is not None
    assert sent["raw"].startswith("0x02")  # EIP-1559 tx
    assert receipt.raw["status"] == "0x1"


@pytest.mark.asyncio
@respx.mock
async def test_register_delegate_flow():
    from avantis_trader_sdk.signing import LocalSigner

    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    payload = _vector_payload("DelegateReq", signerRule="trader-only")
    respx.post(f"{TXB}/v2/intents/delegate-set").mock(return_value=_ok(payload))
    queue_route = respx.post(f"{RELAYER}/relays").mock(
        return_value=httpx.Response(200, json={"requestId": "d1"})
    )
    respx.get(f"{RELAYER}/relays/d1").mock(
        return_value=httpx.Response(
            200,
            json={"requestId": "d1", "status": "Finalised",
                  "receipt": {"transactionHash": "0xd", "status": "0x1"}},
        )
    )

    async with _client() as client:
        receipt = await client.account.register_delegate(
            TEST_ADDRESS, expiry_seconds=1900000000, trader_signer=LocalSigner(TEST_KEY)
        )

    assert receipt.tx_hash == "0xd"
    body = json.loads(queue_route.calls[0].request.content)
    # inner calldata targets setDelegateWithSig on the router (via execute wrapper)
    assert body["txParams"]["transactionType"] == 4
    assert body["txParams"]["data"].startswith("0xe9ae5c53")


@pytest.mark.asyncio
@respx.mock
async def test_lp_deposit_trader_mode():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    respx.post(f"{TXB}/v2/lp/deposit").mock(
        return_value=_ok(
            {
                "to": "0x9999999999999999999999999999999999999999",
                "from": TEST_ADDRESS,
                "data": "0xabcd",
                "value": "0x0",
                "chainId": 31337,
                "description": "Deposit 100 USDC",
            }
        )
    )
    respx.post(f"{RELAYER}/relays").mock(
        return_value=httpx.Response(200, json={"requestId": "lp1"})
    )
    respx.get(f"{RELAYER}/relays/lp1").mock(
        return_value=httpx.Response(
            200,
            json={"requestId": "lp1", "status": "Finalised",
                  "receipt": {"transactionHash": "0xlp", "status": "0x1"}},
        )
    )

    async with _client(trader_address=TEST_ADDRESS) as client:
        receipt = await client.lp.deposit(100)

    assert receipt.tx_hash == "0xlp"
