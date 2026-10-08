"""File access on the share: listing, moving, deleting, delivering and creating folders."""
# --------- IMPORTS ---------
import json
import stat
import os
import shutil
from pathlib import Path

from .constants import collection_boxes, inbox, invalid_path_chars, outbox, pool_boxes, stages, worker_dir
from .config import cfg
from .util import file_name, issue, stamp
from .layout import job_folder, share_path, stage_folder


# --------- INIT ---------
ensured_folders: set[str] = set()


# --------- FUNC ---------
def scan(relative: str) -> dict[str, tuple[str, int]]:
    """Files of a share folder: casefolded name -> (name, size); empty if the folder does not exist."""
    entries = {}
    try:
        with os.scandir(share_path(relative)) as items:
            for item in items:
                try:
                    if item.is_file(follow_symlinks=False):
                        entries[item.name.casefold()] = (item.name, item.stat(follow_symlinks=False).st_size)
                except FileNotFoundError:
                    continue  # Files may arrive or disappear during the scan.
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise RuntimeError(f"Ordner nicht lesbar: {share_path(relative)}; Zustand unverändert.") from exc
    return entries


def subfolders(relative: str) -> list[str]:
    """Sorted subfolder names of a share folder; empty if the folder does not exist."""
    try:
        with os.scandir(share_path(relative)) as items:
            return sorted(item.name for item in items if item.is_dir(follow_symlinks=False))
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise RuntimeError(f"Ordner nicht lesbar: {share_path(relative)}; Zustand unverändert.") from exc


def listing(ctx: dict, relative: str) -> dict[str, tuple[str, int]]:
    """Scan of a share folder, cached in the run context."""
    if relative not in ctx["listings"]:
        ctx["listings"][relative] = scan(relative)
    return ctx["listings"][relative]


def dirs(ctx: dict, relative: str) -> set[str]:
    """Subfolder names of a share folder, cached in the run context."""
    key = ("dirs", relative)
    if key not in ctx["listings"]:
        ctx["listings"][key] = set(subfolders(relative))
    return ctx["listings"][key]


def has_file(ctx: dict, relative: str, name: str) -> bool:
    """True if the folder holds a non-empty file with this name (case-insensitive)."""
    item = listing(ctx, relative).get(name.casefold())
    return item is not None and item[1] > 0


def running(ctx: dict, folder: str) -> dict[str, tuple[str, str]]:
    """Job files in laufend: casefolded name -> (worker, real name)."""
    key = ("running", folder)
    if key not in ctx["listings"]:
        ctx["listings"][key] = {name_key: (worker, name) for worker in subfolders(f"{folder}/laufend")
                                for name_key, (name, _) in scan(f"{folder}/laufend/{worker}").items()}
    return ctx["listings"][key]


def write_text_atomic(path: Path, text: str) -> None:
    """Write a text file via a temporary file and replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def move(relative: str, target_folder: str, name: str | None = None, replace: bool = False) -> bool:
    """Move a file or folder on the share; False if another process moved it first."""
    source = safe_work_path(relative)
    target_name = name or source.name
    if file_name(target_name) != target_name or any(char in invalid_path_chars for char in target_name):
        raise ValueError(f"Unsicherer Arbeitsdateiname: {target_name!r}")
    target = safe_work_path(target_folder) / target_name
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not replace:
        target = target.with_name(f"{target.stem}.{stamp()}{target.suffix}")
    try:
        (os.replace if replace else os.rename)(source, target)
    except FileNotFoundError:
        return False
    return True


def remove_tree(relative: str, ctx: dict, category: str) -> None:
    """Delete a folder inside the work folders; problems become notes in the run context."""
    try:
        path = safe_work_path(relative)
        work_inventory([relative])
        shutil.rmtree(path)
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        issue(ctx, "note", category, relative, f"{relative}: {exc}")


def rmdir(relative: str) -> None:
    """Remove an empty folder inside the work folders; failures are ignored."""
    try:
        safe_work_path(relative).rmdir()
    except (OSError, ValueError):
        pass  # Not empty, outside work folders or already gone.


def delete_job_file(relative: str) -> bool:
    """Delete a job file; False if it cannot be deleted."""
    path = safe_work_path(relative)
    try:
        path.unlink()
    except OSError:
        return False
    return True


def job_output(relative: str, job_id: str) -> str | None:
    """Checked output_folder of a job file; None if unreadable or not matching job_id."""
    try:
        data = json.loads(safe_work_path(relative).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    output = data.get("output_folder") if isinstance(data, dict) else None
    if not isinstance(output, str) or output.split("/")[-2:] != [outbox, job_id]:
        return None
    try:
        safe_work_path(output)
    except ValueError:
        return None
    return output


def output_archive(output_folder: str) -> str:
    """Archive folder next to the outbox of an output folder."""
    return f"{output_folder.rsplit('/', 2)[0]}/archiv"


class DeliveryBlocked(Exception):
    """Raised when a proxy cannot be delivered safely; proxy and master stay in place."""


class MasterBlocked(DeliveryBlocked):
    """Raised when a new master cannot be stored safely in master_dir; nothing is deleted."""


def _is_link(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def safe_work_path(relative: str) -> Path:
    """Allow only root/work_dir and root/<collection>/work_dir; reject links and path aliases."""
    parts = relative.split("/")
    if any(not part or part in (".", "..") or part != part.rstrip(". ") or
           any(char in invalid_path_chars for char in part) for part in parts):
        raise ValueError(f"Unsicherer Arbeitsordner-Pfad: {relative}")
    work = cfg["work_dir"].casefold()
    positions = [i for i, part in enumerate(parts) if part.casefold() == work]
    if not positions or positions[0] not in (0, 1):
        raise ValueError(f"Nicht innerhalb eines Marathon-Arbeitsordners: {relative}")
    root = Path(cfg["root_path"])
    path = root
    for part in parts:
        path /= part
        if os.path.lexists(path) and _is_link(path):
            raise ValueError(f"Verknüpfung/Junction wird nicht verändert: {relative}")
    return path


def _place(relative: str, folder: str, name: str, blocked: type[DeliveryBlocked], keep: str) -> None:
    """Move a work file into folder without overwriting, even when a file arrives after the existence check."""
    source = safe_work_path(relative)
    target = share_path(folder) / name
    if file_name(name) != name or any(c in invalid_path_chars for c in name):
        raise blocked(f"Unsicherer Dateiname: {name!r}; {keep}")
    if any(key == name.casefold() for key in scan(folder)) or os.path.lexists(target):
        raise blocked(f"Namenskonflikt: {target}; neue Datei={source}; {keep}")
    try:
        if os.name == "nt":
            os.rename(source, target)  # Windows refuses an existing target.
        else:
            size = source.stat().st_size
            with source.open("rb") as reader, target.open("xb") as writer:
                shutil.copyfileobj(reader, writer)
                writer.flush()
                os.fsync(writer.fileno())
            if source.stat().st_size != size or target.stat().st_size != size:
                raise blocked(f"Dateigröße beim Verschieben nach {target} geändert; Quelldatei bleibt erhalten; {keep}")
            source.unlink()
    except FileExistsError:
        raise blocked(f"Namenskonflikt: {target}; {keep}") from None
    except OSError as exc:
        raise blocked(f"Verschieben nach {target} nicht möglich: {exc}; {keep}") from exc
    if not target.is_file() or target.stat().st_size == 0:
        raise blocked(f"Verschieben nach {target} konnte nicht bestätigt werden; {keep}")


def deliver_proxy(relative: str, final: str, name: str) -> None:
    """Deliver a proxy into its final folder; raises DeliveryBlocked instead of overwriting."""
    _place(relative, final, name, DeliveryBlocked, "Proxy und Master bleiben erhalten")


def store_master(relative: str, folder: str, name: str) -> None:
    """Move a new master from Transcode into master_dir; raises MasterBlocked instead of overwriting."""
    _place(relative, folder, name, MasterBlocked, "Ausgang wird archiviert, nichts gelöscht")


def work_inventory(roots: list[str]) -> dict[str, tuple[str, int, int]]:
    """Snapshot all entries; any links, special files or unreadable folders block deletion."""
    entries = {}
    for relative in roots:
        pending = [safe_work_path(relative)]
        while pending:
            path = pending.pop()
            if _is_link(path):
                raise ValueError(f"Verknüpfung/Junction im Löschumfang: {path}")
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode) and not stat.S_ISREG(info.st_mode):
                raise ValueError(f"Kein normaler Ordner oder normale Datei: {path}")
            is_dir = stat.S_ISDIR(info.st_mode)
            key = path.relative_to(Path(cfg["root_path"])).as_posix()
            entries[key] = ("dir" if is_dir else "file", info.st_size, info.st_mtime_ns)
            if is_dir:
                pending.extend(path.iterdir())
    return dict(sorted(entries.items()))


def ensure_folders(mapping: list[dict], force: bool = False) -> int:
    """Create missing work and stage folders; returns how many were created."""
    folders = {cfg["work_dir"], f"{cfg['work_dir']}/{worker_dir}"}
    for stage in stages:
        folders |= {f"{job_folder(stage)}/{box}" for box in pool_boxes}
        for entry in mapping:
            base = stage_folder(entry["name"], stage)
            folders |= {f"{base}/{box}" for box in (*collection_boxes, *((inbox,) if stage != "restore" else ()))}
    parts = [relative.split("/") for relative in folders]
    folders |= {"/".join(items[:end]) for items in parts for end in range(1, len(items))}
    created = 0
    for relative in sorted(folders):  # Parents sort before their children.
        if cfg["work_dir"] in relative.split("/"):
            safe_work_path(relative)
        if force or relative not in ensured_folders:
            if not share_path(relative).is_dir():
                share_path(relative).mkdir(parents=True, exist_ok=True)
                created += 1
            ensured_folders.add(relative)
    return created
