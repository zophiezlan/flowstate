# Extensions (Legacy / Inactive in v1)

The extension system is **not part of the active FlowState v1 runtime path**.

## Current status

- Extension runtime is not initialized by active `tap_station/main.py` v1 startup path.
- Active v1 server/API does not expose extension-driven route registration.
- This document is retained only as historical reference for pre-v1 architecture.

## For v1 deployments

Do **not** use extension configuration as part of active setup.
Use fixed-stage v1 behavior documented in:

- `README.md`
- `docs/SETUP.md`
- `docs/MOBILE.md`

## Recommendation

If repository cleanup is prioritized later, extension docs/modules should be archived or removed in a dedicated legacy-pruning pass.
