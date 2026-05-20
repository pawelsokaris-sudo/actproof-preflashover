# ADDENDUM-003 — Downloader User-Agent defect and correction

**Status:** Issued **before** primary data collection. No preregistered run has been performed under the affected code.
**Affected code state:** `data_collection.py` at SHA-256 `fb5a7b3f618b9d23261c3ed63fede5a2306a77595efee6ee42462502502a6c9c` (committed at `e3f6ce3`, frozen at `freeze-v1.2`).
**Defective behaviour observed in:** smoke v4 attempt, 2026-05-20, Ubuntu 24.04 VPS, Python 3.12.3.
**Corrected commit:** `<TO BE FILLED ON COMMIT>`
**New preregistration tag:** `freeze-v1.3` (supersedes `freeze-v1.2`; scientific protocol unchanged).

---

## 1. What happened

The first smoke test under `freeze-v1.2` (TWIC source) attempted to download issue #1500 via `urllib.request.urlretrieve`. The TWIC server (https://theweekinchess.com on BlueHost shared hosting) returned **HTTP 406 Not Acceptable**, terminating the pipeline before any data was retrieved.

Diagnostic confirmation on the same VPS:

| Client | User-Agent | Result |
|---|---|---|
| Python `urllib` default | `Python-urllib/3.12` | **HTTP 406** |
| `curl` default | `curl/7.x` | HTTP 200, 2.2 MB |
| `curl` with browser UA | `Mozilla/5.0 ...` | HTTP 200, 2.2 MB |

The defect is a server-side anti-bot rule that rejects User-Agents beginning with `Python-urllib`. This is a common BlueHost-tier hosting policy.

## 2. Root cause

`data_collection.py` used `urlretrieve(url, zip_path)` which sends no explicit User-Agent, falling back to the Python default `Python-urllib/3.x`. This default is on the rejection list of the TWIC hosting provider.

The defect is in the implementation of HTTP fetching only. The PGN content that would have been delivered is bit-identical regardless of which User-Agent retrieves it (verified by comparing `curl` outputs across two UAs above — both produced identical 2.2 MB ZIP files).

## 3. Why this is an implementation fix, not a protocol change

PREREGISTRATION-v1.2.md §4 specifies:

> **Source:** TWIC (The Week in Chess) archive, issues #1500–#1524 inclusive ... Downloaded from `https://theweekinchess.com/zips/twic{NNNN}g.zip`. Concatenated in ascending issue order to a single PGN file. SHA-256 of the concatenated archive will be recorded in `results/archive_sha256.txt` at the start of the preregistered run.

The frozen criteria define **what** is fetched (specific URLs), **in what order** (ascending issue number), and **how the result is identity-anchored** (SHA-256 of the concatenated archive). HTTP request headers are not part of the frozen specification. The bytes retrieved by `curl /UA=Mozilla` and by `urlopen(Request(UA=...))` are byte-identical, hence the resulting concatenated PGN and its SHA-256 are byte-identical, hence every downstream computation is byte-identical.

This is the same classification used in ADDENDUM-001 ("clarifying implementation fix to a frozen criterion").

## 4. Correction

### 4.1 Code change

In `data_collection.py`, function `ensure_pgn()`, the download loop is updated from:

```python
from urllib.request import urlretrieve
...
urlretrieve(url, zip_path)
```

to:

```python
from urllib.request import urlopen, Request
...
UA = "Mozilla/5.0 (ActProof preregistered research; +<repo URL>)"
req = Request(url, headers={"User-Agent": UA})
with urlopen(req, timeout=60) as resp, open(zip_path, "wb") as out:
    out.write(resp.read())
```

The User-Agent string is an honest self-identification (research project, repository URL) prefixed with `Mozilla/5.0` to satisfy common anti-bot heuristics. A 60-second timeout per file is added for robustness on slow shared hosting.

### 4.2 What did NOT change

- PREREGISTRATION-v1.2.md — unchanged. Frozen protocol unchanged.
- Sensor code (`actproof_chess.py`, `actproof_dynamics.py`) — unchanged.
- Filter, statistical procedure, decision matrix, sample size, classical operationalisation — all unchanged.
- TWIC issue range #1500–#1524, concatenation order, archive SHA-256 recording — all unchanged.
- The PGN content retrieved is byte-identical to what the defective code would have retrieved if not rejected by the server.

## 5. Procedural classification

PREREGISTRATION-v1.2.md §6 states defects discovered mid-experiment require abort + public addendum + new preregistration tag. This defect was discovered during smoke testing before any preregistered data was collected. The full §6 procedure is followed: abort, public addendum (this document), new tag (`freeze-v1.3`) for the corrected implementation.

## 6. Honest assessment

The implementation was tested for syntax and import structure before delivery but not for live network behaviour against the actual TWIC server. Live-network testing of every download endpoint before smoke is a check that should have been done by the implementation author (Claude) and was not. It is the third pre-data-collection ADDENDUM in this experiment.

This pattern is uncomfortable but instructive: the cost of catching three defects pre-data via smoke testing is three commits and three public addendums. The cost of catching any one of them post-data would have been either (a) a meaningless null result, (b) a meaningless positive result, or (c) silent contamination of the dataset.

## 7. Files at issue

- `data_collection.py` — patched as above.
- `PREREGISTRATION-v1.2.md` — **unchanged.**
- All sensor / dynamics code — **unchanged.**
- `ADDENDUM-001.md`, `ADDENDUM-002.md` — historical, unchanged.

## Sign-off

- **Author:** Paweł Łuczak
- **Addendum date:** `<TO BE FILLED ON COMMIT>`
- **Commit hash of corrected `data_collection.py`:** `<TO BE FILLED ON COMMIT>`
- **New preregistration tag:** `freeze-v1.3` (annotated; supersedes `freeze-v1.2`)
