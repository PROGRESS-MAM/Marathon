"""Proxy names and DEFA-IDs from file names."""
# --------- IMPORTS ---------
import re
import string
from pathlib import Path

from .constants import field_names, ingest_separator
from .config import cfg
from .share import listing


# --------- FUNC ---------
def proxy_name(clip: dict) -> str | None:
    """Proxy file name of a clip by proxy_name; None without Veritone-ID."""
    veritone_id = clip.get("veritone_id")
    return cfg["proxy_name"].format(veritone_id=veritone_id, clip_id=clip["clip_id"]) if veritone_id else None


def proxy_ids(name: str) -> tuple[str, str] | None:
    """(veritone_id, clip_id) of a file name by proxy_name."""
    pattern = "".join(re.escape(text) + (rf"(?P<{field}>\d+)" if field else "")
                      for text, field, _, _ in string.Formatter().parse(cfg["proxy_name"]))
    match = re.fullmatch(pattern, name, re.IGNORECASE)
    return (match["veritone_id"], match["clip_id"]) if match else None


def proxy_text(name: str) -> str:
    """Text with veritone_id and clip_id of a proxy name; empty if the name does not match proxy_name."""
    ids = proxy_ids(name)
    return f", veritone_id={ids[0]}, {field_names['clip_id']}={ids[1]}" if ids else ""


def find_proxy(ctx: dict, folder: str, clip: dict) -> str | None:
    """Real name of the clip's non-empty proxy in folder, if present."""
    name = proxy_name(clip)
    item = listing(ctx, folder).get(name.casefold()) if name else None
    return item[0] if item and item[1] else None


def defa_id(name: str) -> str | None:
    """DEFA-ID of a name <DEFA-ID>__<title>.<suffix>; None if the name does not match."""
    identifier, separator, title = name.partition(ingest_separator)
    return identifier.strip() if separator and identifier.strip() and Path(title).stem.strip() else None


def proxy_defa_id(name: str) -> str | None:
    """DEFA-ID of a name <proxy_prefix>__<DEFA-ID>__<title>.mp4; None if the name does not match."""
    prefix = cfg["proxy_prefix"] + ingest_separator
    return defa_id(name[len(prefix):]) if name.casefold().startswith(prefix.casefold()) else None
