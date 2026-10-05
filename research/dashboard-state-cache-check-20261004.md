# Dashboard state cache: recorded checks, 4 October 2026

The promoted server caches **validated compact object inventory only**. It avoids repeatedly decoding large registry payloads during unchanged dashboard polling. It does not cache scientific objects, source replay, jobs, usage or provider accounting. This note reads current source and existing profiles/logs; it performs no provider calls or database writes.

Frozen implementation inspected:

| File | Binary SHA256 |
|---|---|
| [state_inventory_cache.py](../swarm_lab/state_inventory_cache.py) | 5a5e10f9ac545dd3eba039c1d8cf2be7792cf7e74418ce953a6a8ee33928eec3 |
| [server.py](../swarm_lab/server.py) | 76b3d8bc045346380214632f6aed87dfb818b7d51f031f5bd828dceec6684ee8 |

## What is retained and when it is invalidated

One persistent SQLite observer opens the host's fixed path with `mode=ro` and `query_only=ON`. A lock serializes inventory access. The hit gate combines that connection's `PRAGMA data_version` with DB/WAL identity, size and timestamp signatures, checked before and after copying the result. File signatures are change detectors, not cryptographic filesystem attestation.

A miss selects at most 200 latest object versions in created-time order, within one read transaction. Each body passes the existing `Store._decode` immutable fingerprint check before becoming a small summary. Large payload bodies are not retained in the cache. Returned summaries are deep copies, so caller mutation cannot change later responses.

An ordinary committed payload change with the old stored hash invalidates the gate and reaches the fingerprint rejection. A correctly resealed update is reflected in the inventory; hash consistency does not establish its scientific correctness or authorize a historical change. Replacement reconnects or fails closed. Missing files, non-SQLite replacements, observer errors and validation failures discard summaries and close the observer rather than serve an old hot result.

A commit racing a rebuild can leave a **valid earlier read-transaction snapshot** as that call's response. It is not published under the new hot-cache gate; the next call must revalidate. This is not a promise of the newest possible inventory or atomic agreement between inventory, jobs and usage. Closing the cache evicts summaries; a later call reconnects and validates again. Server shutdown closes the observer.

`/api/state` separately reads jobs and usage on each request. Exact `/api/object` and history reads still use the full uncached Store reader, including its body-hash checks. Scientific workflows, action traces and call reservations remain outside this presentation cache. Commits to jobs/calls conservatively invalidate `data_version` too, so active work can require repeated cold rebuilds.

## Recorded timings

| Measurement | Scope and recorded wall time |
|---|---|
| [Baseline profile](../.runtime/state-performance-profile-20261004.json) | 112 latest objects, 49,369,828 payload characters; unchanged `Store.list` took **7.025 s** under concurrent load. Registry hashes matched. This is a component profile, not an end-to-end API request. |
| [Staged read-only cache profile](../.runtime/state-cache-readonly-profile-20261004.json) | Same 112-object scope: cold get **4.035 s**, subsequent gets **2.619, 4.746, 5.959 ms**. Diagnostics record one payload fetch/publication and three hits. |
| [Actual loopback API](../.runtime/live-state-api-latency-20261004.json) | Three real GETs at 06:53 UTC: **0.133, 0.074, 0.097 s**, all HTTP 200; 112 objects, calls=400, zero active jobs; each response 69,176 bytes. Browser polling may already have warmed inventory. |

These conditions differ. There is **no controlled before/after speedup ratio** or general latency guarantee. The first cold inventory remains large, while actual API time also includes fresh state fields, encoding and transport. The profiles assert zero provider calls and production application-database writes. They are engineering measurements, not new scientific observations, raw-source verification or behavioral evidence.

## Focused validation, with overlap preserved

The terminal [promoted owner/peer log](../.runtime/promoted-state-cache-20261004.log) reports **24 checks passed**. It covers tampering with unchanged hashes, resealed updates, races, concurrent readers, replacement/errors, limits, copying and close/reopen. The [public interface log](../.runtime/state-inventory-interfaces-20261004.log) reports **five passed**, including fresh jobs/usage, uncached exact-object rejection, queued measurement-result visibility and shutdown eviction. The [combined cache/role integration log](../.runtime/state-cache-role-integration-20261004.log) reports **69 passed**.

These cohorts overlap and must not be added into a new total. They establish tested cache/interface contracts, not all possible filesystem attacks or scientific validity. No completion or count is asserted for the separate full-suite run.
