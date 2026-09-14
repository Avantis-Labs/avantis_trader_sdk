# avantis-trader-sdk (compatibility release)

Avantis is now **Veranta**. This package is the final release under the old
name: it only depends on [`veranta-sdk`](https://pypi.org/project/veranta-sdk/)
and re-exports it, so existing code keeps working while you migrate:

```python
from avantis_trader_sdk import AsyncAvantis   # DeprecationWarning, still works
# becomes
from veranta_sdk import AsyncVeranta
```

Submodule imports (`avantis_trader_sdk.signing`, `avantis_trader_sdk.compute`, ...)
resolve to their `veranta_sdk` twins. No further updates ship under this name.
See https://sdk.veranta.com/migration/rename.
