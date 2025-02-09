from .client import TraderClient
from .feed.feed_client import FeedClient
from .signers.base import BaseSigner

__version__ = "0.7.0"

print(
    f"""
---------------------------------------------------------------------------------
⚠️ IMPORTANT: Avantis Contracts v1.5 Upgrade

Breaking changes are being introduced as part of the v1.5 Contracts Upgrade.
If you're using this SDK, please review the details to ensure compatibility.

Details: https://avantisfi.notion.site/avantis-contracts-v1-5-upgrade

Milestone 1: Completed on 24th January 2025
- Updates to PairStorage, PairInfos, and Multicall contracts.

Milestone 2: Scheduled for 21th February 2025
- Updates to Trading, Referral, TradingStorage, TradingCallbacks, and more.

Ensure your integration is updated to avoid disruptions.
---------------------------------------------------------------------------------
"""
)
