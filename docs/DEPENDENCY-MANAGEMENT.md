# Dependency management & reproducibility

This repo separates **policy** (minimum supported versions) from **reproducibility** (an exact,
known-good pin). That split is deliberate and is the Cycle 4 hardening for dependencies.

## The three files

| File | Role | Operator |
|------|------|----------|
| `requirements.txt` | Version **floors** — the minimum each direct dep must satisfy (ADR-0001 bake-off set). Tracks upstream; CI installs this to catch breakage early. | `>=` |
| `constraints.txt` | Exact pin of the **direct** deps, set to the versions under which live smoke (6/6) and the offline suite (1419) passed. | `==` |
| `constraints.lock.txt` | (Generated, optional) full **transitive** lock from `pip freeze`. Not committed by default — regenerate per environment. | `==` |

## Install modes

**Newest-resolvable (CI default today)** — exercises the latest versions that satisfy the floors:
```
pip install -r requirements.txt
```

**Reproducible direct-dep baseline** — the live-smoke-verified versions:
```
pip install -r requirements.txt -c constraints.txt
```

**Fully frozen build** — regenerate a transitive lock in a clean virtualenv, then install from it:
```
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip freeze > constraints.lock.txt
# later / elsewhere:
pip install -r requirements.txt -c constraints.lock.txt
```

## Strategy & rationale

- **Why floors in `requirements.txt`?** The platform is pre-1.0 and tracks fast-moving SDKs
  (litellm, google-cloud-*). Floors let CI surface upstream breakage on the newest resolvable
  set instead of silently freezing on a stale version.
- **Why a separate `constraints.txt`?** A reproducible build needs an exact pin, but pinning in
  `requirements.txt` would conflate "minimum we support" with "exact we shipped". Keeping the
  pin in a constraints file lets either intent be selected at install time without editing the
  dependency list.
- **Why not freeze CI now?** Switching CI to `-c constraints.txt` would stop exercising newer
  versions and could mask a real upstream regression before release. The pin is captured and
  documented; promotion to CI is a one-line change when the team wants a frozen release build.

## Promotion checklist (when freezing for release)
1. Regenerate `constraints.lock.txt` from a clean venv (full transitive lock).
2. Re-run the offline suite and the live GCP smoke gate against the lock.
3. Add `-c constraints.lock.txt` to the `pip install` steps in `.github/workflows/ci.yaml`.
4. Record the freeze (date + commit) in `docs/CYCLE-4-HARDENING.md`.

## Updating the verified baseline
When deps are intentionally bumped: bump the floor in `requirements.txt`, re-run offline + live
gates, then update the matching `==` pin in `constraints.txt` and the "Verified baseline"
date in its header.
