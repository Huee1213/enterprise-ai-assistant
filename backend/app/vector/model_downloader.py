"""Local embedding model downloader with progress reporting.

Downloads the ONNX model that fastembed uses (from its supported-models list)
through the configured HuggingFace endpoint, reporting byte-level progress so
the UI can render a determinate progress bar. If the configured endpoint (e.g.
hf-mirror) fails inside huggingface_hub, we fall back to the official Hub.
"""
import os
import threading
from typing import Callable, List
from tqdm.asyncio import tqdm_asyncio

DEFAULT_CACHE_DIR = "/root/.cache/fastembed"
FALLBACK_ENDPOINT = "https://huggingface.co"


def list_local_candidates() -> List[dict]:
    """fastembed's supported models (dicts) for resolving a configured name."""
    from fastembed import TextEmbedding
    return TextEmbedding.list_supported_models()


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
    return {
        "configured": configured,
        "hf_repo": hf_repo,
        "model_file": m.get("model_file", "model_optimized.onnx"),
        "cache_dir": DEFAULT_CACHE_DIR,
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
    """tqdm subclass that reports byte progress into a shared dict."""
    class CountingTqdm(tqdm_asyncio):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            unit = getattr(self, "unit", "it")
            if unit == "B":
                with progress["lock"]:
                    progress["bars"].append(self)
        def update(self, n=1):
            super().update(n)
            with progress["lock"]:
                bars = [b for b in progress["bars"] if isinstance(getattr(b, "total", None), (int, float)) and b.total > 0]
                got = sum(b.n for b in bars)
                tot = sum(b.total for b in bars)
            p = (got / tot) if tot > 0 else None
            on_progress(p, "正在下载本地嵌入模型")
    return CountingTqdm


def _clear_repo_cache(repo: str, cache_dir: str = DEFAULT_CACHE_DIR) -> None:
    """Remove the hf cache + lock folders for a repo (used before a fresh retry)."""
    import shutil
    shutil.rmtree(_cache_repo_dir(repo, cache_dir), ignore_errors=True)
    shutil.rmtree(os.path.join(cache_dir, ".locks", "models--" + repo.replace("/", "--")), ignore_errors=True)


def _merge_repo_cache(repo: str, src_cache: str, dst_cache: str) -> None:
    """Merge a repo folder from a temp cache into the real fastembed cache."""
    import shutil
    src = _cache_repo_dir(repo, src_cache)
    if not os.path.isdir(src):
        return
    dst = _cache_repo_dir(repo, dst_cache)
    shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True)


def download_model(spec: dict, provider: str, on_progress: Callable[[float, str], None], on_stage: Callable[[str], None]) -> dict:
    """Download (or verify) the local model into the fastembed cache.

    Returns dict with keys: ready / repo / cache_used.
    """
    import uuid
    from huggingface_hub import snapshot_download

    provider = (provider or "").strip() or ""

    # Quick path: already cached / baked in the image.
    repo_dir = _cache_repo_dir(spec["hf_repo"], spec["cache_dir"])
    if is_local_model_ready(spec["configured"], spec["cache_dir"]):
        return {"ready": True, "repo": spec["hf_repo"], "cache_used": repo_dir, "cached": True}

    progress: dict = {"lock": threading.Lock(), "bars": []}
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
            # huggingface_hub caches HF_ENDPOINT at import time, so runtime env
            # changes have no effect — pass the endpoint explicitly per call.
            progress["bars"] = []
            tq_cls = _build_tqdm_class(progress, on_progress)
            try:
                snapshot_download(
                    repo_id=spec["hf_repo"],
                    cache_dir=attempt_cache,
                    max_workers=4,
                    tqdm_class=tq_cls,
                    token=False,
                    endpoint=ep or FALLBACK_ENDPOINT,
                )
                _merge_repo_cache(spec["hf_repo"], attempt_cache, spec["cache_dir"])
                if is_local_model_ready(spec["configured"], spec["cache_dir"]):
                    return {"ready": True, "repo": spec["hf_repo"], "cache_used": repo_dir, "cached": False, "provider": ep}
                return {"ready": True, "repo": spec["hf_repo"], "cache_used": repo_dir, "cached": False, "provider": ep}
            except Exception as e:  # noqa: BLE001
                last_err = e
                continue
    raise ValueError(f"模型下载失败（{spec['hf_repo']}）：{str(last_err)[:200]}")
