"""Phase 2 flow tests: off-chain TP/SL, gasless referral, direct route via
RPC, delegate registration, and the delegate-identity guard."""

import json

import httpx
import pytest
import respx

from avantis_trader_sdk import AsyncAvantis
from avantis_trader_sdk.errors import ConfigError
from avantis_trader_sdk.intents_schema import INTENT_TYPES
from tests.conftest import META, TEST_ADDRESS, TEST_KEY, TRADER, VECTORS, mock_data_api

TXB = "https://txb.test"
RELAYER = "https://relayer.test"
CORE = "https://core.test"
TWAP = "https://twap.test"
RPC = "https://rpc.test"
DATA = "https://data.test"


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
        twap_api_url=TWAP,
        data_api_url=DATA,
        relay_poll_interval_s=0.01,
    )
    defaults.update(kw)
    return AsyncAvantis(**defaults)


def _mock_read_rpc():
    """Trader-EOA relayer mode needs an RPC for the EIP-7702 authorization
    nonce (delegate/API keys are fresh EOAs and need none)."""

    def handler(request):
        body = json.loads(request.content)
        result = {"eth_getTransactionCount": "0x7", "eth_estimateGas": "0x30d40"}.get(
            body["method"], "0x0"
        )
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result})

    respx.post(RPC).mock(side_effect=handler)


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


# documentId from the CancelOffchainOrder golden vector (conftest META uses
# the golden-vector domain: chainId 31337 + same router).
DOCUMENT_ID = "665f1c2ab7a1b2c3d4e5f601"


@pytest.mark.asyncio
@respx.mock
async def test_offchain_partial_tpsl_submit():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    respx.post(f"{TXB}/v2/intents/tpsl-partial").mock(
        return_value=_ok(_vector_payload("TpSlReq"))
    )
    post_route = respx.post(f"{CORE}/offchain-orders").mock(
        return_value=httpx.Response(200, json={"documentId": DOCUMENT_ID})
    )

    async with _client() as client:
        submission = await client.trade.partial_tp_sl(
            "ETH/USD", 0, side="long", kind="tp", coin_exposure="0.5", price=4000
        )

    assert post_route.called
    body = json.loads(post_route.calls[0].request.content)
    vec_msg = next(v for v in VECTORS["vectors"] if v["kind"] == "TpSlReq")["message"]
    assert body["trader"] == vec_msg["trader"]
    assert body["signTimestamp"] == int(vec_msg["signTimestamp"])
    assert body["signedMessage"].startswith("0x") and len(body["signedMessage"]) == 132
    assert submission["orderType"] == int(vec_msg["orderType"])
    # the stored order's documentId (needed for update/cancel) is surfaced
    assert submission["documentId"] == DOCUMENT_ID


@pytest.mark.asyncio
@respx.mock
async def test_offchain_partial_tpsl_update_puts_to_document():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    respx.post(f"{TXB}/v2/intents/tpsl-partial").mock(
        return_value=_ok(_vector_payload("TpSlReq"))
    )
    put_route = respx.put(f"{CORE}/offchain-orders/{DOCUMENT_ID}").mock(
        return_value=httpx.Response(200, json={"documentId": DOCUMENT_ID})
    )

    async with _client() as client:
        updated = await client.trade.update_partial_tp_sl(
            DOCUMENT_ID, "ETH/USD", 0,
            side="long", kind="tp", coin_exposure="0.5", price=4200,
        )

    assert put_route.called
    body = json.loads(put_route.calls[0].request.content)
    assert body["signedMessage"].startswith("0x") and len(body["signedMessage"]) == 132
    assert updated["documentId"] == DOCUMENT_ID


@pytest.mark.asyncio
@respx.mock
async def test_offchain_partial_tpsl_cancel_signs_document_id():
    """Cancel signs an EIP-712 CancelOffchainOrder over the documentId and
    DELETEs with a JSON body — proven against the ethers golden vector."""
    from eth_account import Account

    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    respx.post(f"{TXB}/v2/intents/tpsl-partial").mock(
        return_value=_ok(_vector_payload("TpSlReq"))
    )
    respx.post(f"{CORE}/offchain-orders").mock(
        return_value=httpx.Response(200, json={"documentId": DOCUMENT_ID})
    )
    delete_route = respx.delete(f"{CORE}/offchain-orders").mock(
        return_value=httpx.Response(200, json={})
    )

    async with _client() as client:
        submission = await client.trade.partial_tp_sl(
            "ETH/USD", 0, side="long", kind="tp", coin_exposure="0.5", price=4000
        )
        await client.trade.cancel_partial_tp_sl(submission)

    assert delete_route.called
    body = json.loads(delete_route.calls[0].request.content)
    assert body["documentId"] == DOCUMENT_ID
    # the signature recovers to the signer over the golden-vector digest
    golden = next(
        v for v in VECTORS["vectors"] if v["kind"] == "CancelOffchainOrder"
    )
    recovered = Account._recover_hash(
        golden["digest"], signature=bytes.fromhex(body["signedMessage"][2:])
    )
    from avantis_trader_sdk.signing import LocalSigner

    assert recovered.lower() == LocalSigner(TEST_KEY).address.lower()


@pytest.mark.asyncio
@respx.mock
async def test_twap_open_posts_signed_intent_to_twap_app():
    """twap_open: tx-builder intent -> local sign -> POST {twap}/twaps/open
    with DTO conventions (pairIndex number, __reserved1 -> reserved1)."""
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    respx.post(f"{TXB}/v2/intents/twap-open").mock(
        return_value=_ok(_vector_payload("TwapOpenOrder"))
    )
    open_route = respx.post(f"{TWAP}/twaps/open").mock(
        return_value=httpx.Response(
            201, json={"twapId": 12, "transactionHash": "0xtwap", "blockNumber": 99}
        )
    )

    async with _client() as client:
        receipt = await client.trade.twap_open(
            "ETH/USD", "long", collateral=100, run_time_seconds=3600,
            leverage=10, max_leverage=75,
        )

    assert receipt.route == "twap-api"
    assert receipt.tx_hash == "0xtwap"
    assert receipt.order_id == 12  # on-chain twapId

    vec_msg = next(
        v for v in VECTORS["vectors"] if v["kind"] == "TwapOpenOrder"
    )["message"]
    body = json.loads(open_route.calls[0].request.content)
    assert body["trader"] == vec_msg["trader"]
    assert body["pairIndex"] == int(vec_msg["pairIndex"])  # number, not string
    assert body["collateral"] == vec_msg["collateral"]
    assert body["buy"] is True and body["isCoin"] is False
    assert body["runTime"] == vec_msg["runTime"]
    assert "__reserved1" not in body and body["reserved1"] == "0"
    assert body["signature"].startswith("0x") and len(body["signature"]) == 132


@pytest.mark.asyncio
@respx.mock
async def test_twap_close_posts_signed_intent():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    mock_data_api(DATA)
    respx.post(f"{TXB}/v2/intents/twap-close").mock(
        return_value=_ok(_vector_payload("TwapCloseOrder"))
    )
    close_route = respx.post(f"{TWAP}/twaps/close").mock(
        return_value=httpx.Response(
            201, json={"twapId": 13, "transactionHash": "0xc", "blockNumber": 100}
        )
    )

    async with _client() as client:
        receipt = await client.trade.twap_close(
            "ETH/USD", 0, coin_exposure_to_close="0.25", run_time_seconds=1800
        )

    assert receipt.order_id == 13
    body = json.loads(close_route.calls[0].request.content)
    assert body["index"] == 0  # number, per the DTO
    vec_msg = next(
        v for v in VECTORS["vectors"] if v["kind"] == "TwapCloseOrder"
    )["message"]
    assert body["coinSizeToClose"] == vec_msg["coinSizeToClose"]


@pytest.mark.asyncio
@respx.mock
async def test_twap_cancel_builds_intent_locally():
    """No tx-builder route for TwapCancelReq: built + signed locally, POSTed
    to the twap-app."""
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    cancel_route = respx.post(f"{TWAP}/twaps/cancel").mock(
        return_value=httpx.Response(
            201, json={"twapId": 7, "transactionHash": "0xdead", "blockNumber": 101}
        )
    )

    async with _client() as client:
        receipt = await client.trade.twap_cancel(7)

    assert receipt.route == "twap-api"
    assert receipt.tx_hash == "0xdead"
    body = json.loads(cancel_route.calls[0].request.content)
    assert body["trader"] == TRADER
    assert body["twapId"] == "7"  # IsNumberString in the DTO
    assert body["nonce"].isdigit() and body["deadline"].isdigit()
    assert "reserved1" not in body  # cancel struct has no reserved slot
    assert body["signature"].startswith("0x") and len(body["signature"]) == 132


@pytest.mark.asyncio
@respx.mock
async def test_account_twaps_reads_from_twap_app():
    respx.get(f"{TXB}/v2/meta").mock(return_value=_ok(META))
    twaps_route = respx.get(f"{TWAP}/twaps").mock(
        return_value=httpx.Response(200, json=[{"twapId": 12}])
    )

    async with _client() as client:
        data = await client.account.twaps()

    assert data == [{"twapId": 12}]
    params = dict(twaps_route.calls[0].request.url.params)
    assert params["trader"] == TRADER
    assert params["pageNum"] == "0"  # twap-app pagination is 0-based


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

    _mock_read_rpc()
    # trader-key mode (signer == trader) so referral actions are allowed;
    # trader-EOA type-4 builds read the authorization nonce over RPC
    async with _client(trader_address=TEST_ADDRESS, rpc_url=RPC) as client:
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
    mock_data_api(DATA)
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

    _mock_read_rpc()
    async with _client(trader_address=TEST_ADDRESS, rpc_url=RPC) as client:
        receipt = await client.lp.deposit(100)

    assert receipt.tx_hash == "0xlp"
