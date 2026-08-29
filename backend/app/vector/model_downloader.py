"""Local embedding model downloader with progress reporting.

Downloads the ONNX model that fastembed uses (from its supported-models list)
through the configured HuggingFace endpoint, reporting byte-level progress so
the UI can render a determinate progress bar. If the configured endpoint (e.g.
hf-mirror) fails inside huggingface_hub, we fall back to the official Hub.

Notes on tuning:
- HF_HUB_DISABLE_XET must be on. The Xet transfer backend streams via the
  `xet` native store and never feeds byte progress into tqdm, so the progress
  bar would stay at 0% until completion. It is set here (before any
  huggingface_hub import) and again right before each download to defend
  against gunicorn worker import-order surprises.
- Progress is monotonic: multiple concurrently-downloaded files each own a
  tqdm bar, and naive done/total across bars can visibly jump backwards. We
  clamp the reported ratio so it only moves forward.
"""
import os

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ["HF_HUB_DISABLE_XET"] = "1"  # hard-set: constant is read at hf import

import threading
from typing import Callable, List
from tqdm import tqdm as _base_tqdm

DEFAULT_CACHE_DIR = "/root/.cache/fastembed"
FALLBACK_ENDPOINT = "https://huggingface.co"


def list_local_candidates() -> List[dict]:
    """fastembed's supported models (dicts) for resolving a configured name.

    Cached: the supported list is static per fastembed version and the lookup
    runs once per candidate in hot paths (status checks, model listing).
    """
    from functools import lru_cache
    from fastembed import TextEmbedding

    @lru_cache(maxsize=1)
    def _cached() -> tuple:
        return tuple(TextEmbedding.list_supported_models())

    return list(_cached())


def resolve_local_model(model: str) -> dict:
    """Resolve a configured local model name to its HF repo + ONNX file.

    Accepts names with or without the ``local/`` prefix. Raises ValueError when
    the model is not in fastembed's supported set.
    """
    name = model.strip()
    if name.lower().startswith("local/"):
        name = name[len("local/"):].strip()
    if not name:
        raise ValueError("本地模型名为空")
    for m in list_local_candidates():
        try:
            mid = str(m["model"])
        except Exception:
            continue
        if mid.lower() == name.lower():
            return _as_spec(m, name)
    # prefix fallback: e.g. "bge-small" -> first match
    lower = name.lower()
    for m in list_local_candidates():
        try:
            mid = str(m["model"]).lower()
        except Exception:
            continue
        if mid.startswith(lower) or lower in mid:
            return _as_spec(m, name)
    raise ValueError(f"不支持的本地嵌入模型: {model}")

def _as_spec(m: dict, configured: str) -> dict:
    sources = m.get("sources") or {}
    hf_repo = sources.get("hf") or m.get("model", "")
    # fastembed lists the total on-disk footprint (size_in_GB) of the repo.
    try:
        size_bytes = int(float(m.get("size_in_GB") or 0) * 1e9)
    except Exception:
        size_bytes = 0
    return {
        "configured": configured,
        "hf_repo": hf_repo,
        "model_file": m.get("model_file", "model_optimized.onnx"),
        "cache_dir": DEFAULT_CACHE_DIR,
        "size_bytes": size_bytes,
    }


def _cache_repo_dir(hf_repo: str, cache_dir: str = DEFAULT_CACHE_DIR) -> str:
    # hf_hub cache folder: models--{org}--{name} (slash replaced by --)
    return os.path.join(cache_dir, "models--" + hf_repo.replace("/", "--"))


def is_local_model_ready(model: str, cache_dir: str = DEFAULT_CACHE_DIR) -> bool:
    """True when the model's ONNX file already exists in the cache."""
    try:
        spec = resolve_local_model(model)
    except Exception:
        return False
    repo_dir = _cache_repo_dir(spec["hf_repo"], cache_dir)
    if not os.path.isdir(repo_dir):
        return False
    snap_dir = os.path.join(repo_dir, "snapshots")
    if not os.path.isdir(snap_dir):
        return False
    try:
        revs = os.listdir(snap_dir)
    except OSError:
        return False
    for rev in revs:
        fp = os.path.join(snap_dir, rev, spec["model_file"])
        try:
            if os.path.isfile(fp) and os.path.getsize(fp) > 0:
                return True
        except OSError:
            continue
    return False


def _build_tqdm_class(progress: dict, on_progress: Callable[[float, str], None]):
    """tqdm subclass that reports byte progress into a shared dict.

    Two pitfalls make hf 1.28's own bars useless for progress reporting:
      1. With progress bars globally disabled (HF_HUB_DISABLE_PROGRESS_BARS=1,
         set to silence log spam) hf wraps bars with ``disable=True`` — and
         tqdm.update() is a NO-OP when disabled, so ``bar.n`` never grows.
      2. Large files go through hf's chunked/Xet transfer which reports bytes
         via ``update_transfer(n)`` instead of ``update(n)`` — and its bars
         have no total (``0B/0B``).

    So this subclass tracks bytes ITSELF: every ``update``/``update_transfer``
    accumulates into per-bar counters, and the ratio is computed against the
    model's known footprint (``progress["size_bytes"]``). The ratio is clamped
    to be monotonically increasing and capped below 100% until ready.
    """
    from tqdm import tqdm as _base_tqdm

    class CountingTqdm(_base_tqdm):
        def __init__(self, *a, **k):
            self._u_bytes = 0   # bytes reported via update()
            self._t_bytes = 0   # bytes reported via update_transfer()
            super().__init__(*a, **k)
            if getattr(self, "unit", "it") == "B":
                with progress["lock"]:
                    progress["bars"].append(self)
        def update(self, n=1):
            self._u_bytes += int(n)
            super().update(n)
            self._report()
        def update_transfer(self, n=1):
            self._t_bytes += int(n)
            self._report()
        def _report(self):
            with progress["lock"]:
                bars = [b for b in progress["bars"] if getattr(b, "unit", None) == "B"]
                size_bytes = int(progress.get("size_bytes") or 0)
                # update() and update_transfer() can both fire for the same chunk
                # (standard path); the Xet path fires only update_transfer(). The
                # max() of the two per-bar counters is correct in either case.
                done = sum(max(int(getattr(b, "_u_bytes", 0)), int(getattr(b, "_t_bytes", 0))) for b in bars)
            if size_bytes <= 0 or done <= 0:
                return
            p = min(0.99, done / size_bytes)
            with progress["lock"]:
                if p >= progress.get("max_p", 0.0):
                    progress["max_p"] = p
                else:
                    p = progress.get("max_p", 0.0)
            on_progress(min(1.0, p), "正在下载本地嵌入模型")
    return CountingTqdm


def _clear_repo_cache(repo: str, cache_dir: str = DEFAULT_CACHE_DIR) -> None:
    """Remove the hf cache + lock folders for a repo (used before a fresh retry)."""
    import shutil
    shutil.rmtree(_cache_repo_dir(repo, cache_dir), ignore_errors=True)
    shutil.rmtree(os.path.join(cache_dir, ".locks", "models--" + repo.replace("/", "--")), ignore_errors=True)


def remove_local_model(model: str, cache_dir: str = DEFAULT_CACHE_DIR) -> dict:
    """Delete a downloaded local model from the fastembed cache.

    Returns {removed: bool, repo: str}. Removing only touches the model's own
    cache folder; other models are untouched.
    """
    try:
        spec = resolve_local_model(model)
    except ValueError:
        # Unknown name — still try a best-effort cleanup by normalized folder.
        norm = model.strip().replace("local/", "", 1)
        repo = norm.replace("/", "--")
        _clear_repo_cache(norm, cache_dir)
        return {"removed": False, "repo": norm}
    before = is_local_model_ready(model, cache_dir)
    _clear_repo_cache(spec["hf_repo"], cache_dir)
    after = is_local_model_ready(model, cache_dir)
    return {"removed": before and not after, "repo": spec["hf_repo"]}


def _merge_repo_cache(repo: str, src_cache: str, dst_cache: str) -> None:
    """Merge a repo folder from a temp cache into the real fastembed cache."""
    import shutil
    src = _cache_repo_dir(repo, src_cache)
    if not os.path.isdir(src):
        return
    dst = _cache_repo_dir(repo, dst_cache)
    shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True)


def _scan_downloaded_bytes(repo: str, cache_dir: str) -> int:
    """Sum bytes actually written under the repo cache folder.

    HF streams through `blobs/*` and `blobs/*.incomplete` files (and symlink
    targets); scanning the whole repo folder captures all of them, so progress
    reflects real disk bytes whether or not tqdm reports a total.
    """
    total = 0
    base = _cache_repo_dir(repo, cache_dir)
    try:
        if not os.path.isdir(base):
            return 0
        for root, _dirs, files in os.walk(base):
            for fn in files:
                fp = os.path.join(root, fn)
                try:
                    total += os.path.getsize(fp)
                except OSError:
                    continue
    except OSError:
        return 0
    return total


def _watch_on_disk(repo: str, cache_dir: str, size_bytes: int,
                   on_progress: Callable[[float, str], None], stop_event) -> None:
    """Background monitor: report real disk byte progress every ~0.4s.

    Because huggingface_hub may download the bulk of a file quickly in between
    its own tqdm refreshes, we derive progress from the actual bytes on disk so
    the UI bar moves smoothly from 0 → ~99% during ALL of the download, not just
    the final merge.
    """
    last_p = -1.0
    while not stop_event.wait(0.4):
        done = _scan_downloaded_bytes(repo, cache_dir)
        if size_bytes > 0 and done > 0:
            p = min(0.99, done / size_bytes)
            if p - last_p >= 0.01:
                last_p = p
                on_progress(p, "正在下载本地嵌入模型")


def download_model(spec: dict, provider: str, on_progress: Callable[[float, str], None], on_stage: Callable[[str], None]) -> dict:
    """Download (or verify) the local model into the fastembed cache.

    Returns dict with keys: ready / repo / cache_used.
    """
    import uuid
    import time
    from huggingface_hub import snapshot_download

    provider = (provider or "").strip() or ""

    # Quick path: already cached / baked in the image.
    repo_dir = _cache_repo_dir(spec["hf_repo"], spec["cache_dir"])
    if is_local_model_ready(spec["configured"], spec["cache_dir"]):
        return {"ready": True, "repo": spec["hf_repo"], "cache_used": repo_dir, "cached": True}

    progress: dict = {"lock": threading.Lock(), "bars": [], "max_p": 0.0, "size_bytes": int(spec.get("size_bytes") or 0)}
    size_bytes = int(spec.get("size_bytes") or 0)
    endpoints = [provider] if provider else []
    if FALLBACK_ENDPOINT not in endpoints:
        endpoints.append(FALLBACK_ENDPOINT)

    last_err: Exception | None = None
    for i, ep in enumerate(endpoints):
        # For the first (configured) provider use the real cache; for retries use
        # a pristine temp cache — hf-mirror etc. can poison the cache with partial
        # state that breaks a later clean download.
        attempt_cache = spec["cache_dir"] if i == 0 else os.path.join("/tmp", "fastembed-dl-" + uuid.uuid4().hex[:8])
        # Retry each endpoint (head/etag on large files can be flaky).
        for attempt in range(3):
            on_stage(f"正在通过 {ep} 下载模型…（第 {attempt + 1} 次尝试）")
            # Xet must stay disabled for byte-level progress to flow through tqdm.
            os.environ["HF_HUB_DISABLE_XET"] = "1"
            # huggingface_hub caches HF_ENDPOINT at import time, so runtime env
            # changes have no effect — pass the endpoint explicitly per call.
            # Disk-based watchdog gives smooth 0→99% progress even though hf's
            # own tqdm often lacks a total (0B/0B) and refreshes erratically.
            stop_watch = threading.Event()
            watcher = threading.Thread(
                target=_watch_on_disk,
                args=(spec["hf_repo"], attempt_cache, size_bytes, on_progress, stop_watch),
                daemon=True,
            )
            progress["bars"] = []
            progress["max_p"] = 0.0
            tq_cls = _build_tqdm_class(progress, on_progress)
            watcher.start()
            try:
                snapshot_download(
                    repo_id=spec["hf_repo"],
                    cache_dir=attempt_cache,
                    max_workers=1,  # serial: byte-progress 0 → 1 smoothly (no interleaving jumps)
                    tqdm_class=tq_cls,
                    token=False,
                    endpoint=ep or FALLBACK_ENDPOINT,
                )
                stop_watch.set()
                on_progress(1.0, "正在下载本地嵌入模型")
                _merge_repo_cache(spec["hf_repo"], attempt_cache, spec["cache_dir"])
                if is_local_model_ready(spec["configured"], spec["cache_dir"]):
                    return {"ready": True, "repo": spec["hf_repo"], "cache_used": repo_dir, "cached": False, "provider": ep}
                return {"ready": True, "repo": spec["hf_repo"], "cache_used": repo_dir, "cached": False, "provider": ep}
            except Exception as e:  # noqa: BLE001
                stop_watch.set()
                last_err = e
                continue
    raise ValueError(f"模型下载失败（{spec['hf_repo']}）：{str(last_err)[:200]}")
