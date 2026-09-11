# Engineering Reflection

## 1. Key Design Decisions

- **Adapter Pattern over Database**: The Urja portal is the sole source of truth. Adding a database or external cache would introduce cache invalidation complexity, stale state risks, and unnecessary deployment dependencies.
- **3-File Architecture**: Grouping related code into `app/main.py`, `app/client.py`, and `app/models.py` keeps the system immediately understandable for any engineer in under 5 minutes without premature layering or boilerplate.
- **Dynamic Pagination**: Instead of assuming a fixed count (such as 403 meters), `get_meters()` paginates dynamically until the portal returns an empty result set, bounded by a safe upper limit.
- **Strict Separation of Concerns**: All SvelteKit traversal, CSRF header requirements, and cookie management reside exclusively inside `UrjaClient`. `main.py` simply maps client domain exceptions to clean HTTP status codes.

---

## 2. Tradeoffs & Assumptions

- **Eager Aggregation for List**: `GET /api/v1/meters` aggregates all pages into memory before responding. For 400+ records, this takes ~1.5 seconds. For tens of thousands of records, forward-facing cursor or streaming pagination would be necessary.
- **Preserving Raw Timestamps**: Telemetry timestamps (`"23/06/2026 23:30"`) lack timezone metadata. We preserved the raw string rather than guessing timezone offsets.
- **Coupling to SvelteKit Internal Format**: Meter detail relies on SvelteKit's `__data.json` interned structure. If upstream upgrades SvelteKit's serialization format, `_parse_sveltekit_nodes` would need an update.

---

## 3. What Could Be Improved with More Time

1. **Short-lived In-Memory Cache**: Adding a 60-second TTL cache for `/api/v1/meters` would reduce upstream portal hits during bursts of traffic.
2. **Asynchronous Parallel Worker Pool**: Fetching subsequent pages concurrently with `asyncio.gather` once total pages are known would reduce list latency from ~1.5s to ~300ms.
3. **Structured Logging**: Adding request-ID tracing and structured JSON logs to monitor upstream portal latency and error rates.
