"""Rename compatibility: Avantis -> Veranta must not break existing integrations.

Covers the deprecated class aliases, the ``AVANTIS_*`` env-var fallback, the
byte-exact Veranta Terms-of-Service constant, and the ``avantis-trader-sdk``
compatibility shim in ``compat/`` (module aliasing + re-exports).
"""

from __future__ import annotations

import importlib
import os
import pathlib
import sys
import warnings

import pytest

import veranta_sdk
from tests.conftest import TEST_KEY
from veranta_sdk import AsyncVeranta, Veranta, VerantaConfig, VerantaError
from veranta_sdk.intents_schema import TNC_STRING

COMPAT = pathlib.Path(__file__).resolve().parents[1] / "compat" / "avantis-trader-sdk"

# SignatureHelpers._TNC_TO_SIGN_V2 in avantis-contracts-v2 (note the space after "tos.").
CONTRACT_TNC_V2 = (
    "I accept the Veranta Terms of Service: https://www.veranta.xyz/docs/tos. I confirm that I am "
    "not a resident of any of the following countries/regions: Belarus, Cuba, Iran, North Korea, "
    "Russia, Syria, Crimea, United Kingdom, United States of America."
)


def test_tnc_string_is_the_contracts_v2_constant():
    assert TNC_STRING == CONTRACT_TNC_V2


def test_deprecated_class_aliases_warn_and_resolve():
    with pytest.warns(DeprecationWarning, match="AsyncAvantis"):
        assert veranta_sdk.AsyncAvantis is AsyncVeranta
    with pytest.warns(DeprecationWarning):
        assert veranta_sdk.Avantis is Veranta
    with pytest.warns(DeprecationWarning):
        assert veranta_sdk.AvantisConfig is VerantaConfig
    with pytest.warns(DeprecationWarning):
        assert veranta_sdk.AvantisError is VerantaError
    with pytest.raises(AttributeError):
        _ = veranta_sdk.DoesNotExist  # type: ignore[attr-defined]


def _clear_sdk_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith(("VERANTA_", "AVANTIS_")):
            monkeypatch.delenv(key)


def test_legacy_env_vars_fall_back_with_a_warning(monkeypatch: pytest.MonkeyPatch):
    _clear_sdk_env(monkeypatch)
    monkeypatch.setenv("AVANTIS_PRIVATE_KEY", TEST_KEY)
    monkeypatch.setenv("AVANTIS_NETWORK", "testnet")
    monkeypatch.setenv("AVANTIS_TX_BUILDER_URL", "https://txb.legacy")

    with pytest.warns(DeprecationWarning, match="AVANTIS_PRIVATE_KEY is deprecated"):
        cfg = VerantaConfig.load()

    assert cfg.private_key == TEST_KEY
    assert cfg.network == "testnet"
    assert cfg.tx_builder_url == "https://txb.legacy"


def test_new_env_vars_win_silently(monkeypatch: pytest.MonkeyPatch):
    _clear_sdk_env(monkeypatch)
    monkeypatch.setenv("AVANTIS_NETWORK", "testnet")
    monkeypatch.setenv("VERANTA_NETWORK", "mainnet")
    monkeypatch.setenv("VERANTA_PRIVATE_KEY", TEST_KEY)

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        cfg = VerantaConfig.load()

    assert cfg.network == "mainnet"
    assert cfg.private_key == TEST_KEY
    assert cfg.tx_builder_url.endswith("veranta.xyz")


def test_compat_shim_reexports_and_aliases_submodules(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(COMPAT))
    for name in [m for m in sys.modules if m == "avantis_trader_sdk" or m.startswith("avantis_trader_sdk.")]:
        monkeypatch.delitem(sys.modules, name)
    try:
        with pytest.warns(DeprecationWarning, match="avantis_trader_sdk is now veranta_sdk"):
            shim = importlib.import_module("avantis_trader_sdk")

        assert shim.AsyncVeranta is AsyncVeranta
        assert shim.AsyncAvantis is AsyncVeranta
        assert shim.AvantisConfig is VerantaConfig
        assert shim.__version__ == veranta_sdk.__version__
        assert "AsyncAvantis" in shim.__all__ and "AsyncVeranta" in shim.__all__

        # Submodule imports resolve to the veranta_sdk twins (same objects).
        signing = importlib.import_module("avantis_trader_sdk.signing")
        from veranta_sdk.signing import LocalSigner

        assert signing.LocalSigner is LocalSigner
        pnl = importlib.import_module("avantis_trader_sdk.compute.pnl")
        from veranta_sdk.compute import pnl as real_pnl

        assert pnl.gross_pnl is real_pnl.gross_pnl
        errors = importlib.import_module("avantis_trader_sdk.errors")
        assert errors.ConfigError is veranta_sdk.ConfigError
        # The real modules are untouched by the aliasing.
        assert real_pnl.__name__ == "veranta_sdk.compute.pnl"
    finally:
        sys.meta_path[:] = [f for f in sys.meta_path if type(f).__name__ != "_AliasFinder"]
        for name in [m for m in sys.modules if m == "avantis_trader_sdk" or m.startswith("avantis_trader_sdk.")]:
            sys.modules.pop(name, None)
