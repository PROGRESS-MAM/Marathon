"""Master review folders, moves on the share and location updates in the existing JSON history."""
# --------- IMPORTS ---------
from pathlib import Path
import os
import stat
import unicodedata

from .config import cfg
from .constants import ingest_source, invalid_path_chars, master_blocked, reserved_names
from .layout import share_path
from .share import MasterBlocked, safe_work_path
from .state import add_event, set_issue
from .util import issue, now


# --------- CONFIG ---------
app_name = "Marathon Masterablage"
app_version = "1.18.2"
review_name = "manuelle Überprüfung"
new_event = "Neuer Master abgelegt"
old_origin_event = "Alter Master ursprünglich"


# --------- FUNC PATHS ---------
def _safe(path: Path) -> Path:
    path = path.absolute()
    if any(part == ".." for part in path.parts):
        raise MasterBlocked(f"Unsicherer Ablagepfad: {path}")
    for item in (*reversed(path.parents), path):
        if os.path.lexists(item):
            info = item.lstat()
            if stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400):
                raise MasterBlocked(f"Verknüpfung/Junction nicht erlaubt: {item}")
    return path


def _root() -> Path:
    root = _safe(share_path(cfg["master_dir"]))
    if root == Path(root.anchor):
        raise MasterBlocked("Masterablage darf nicht das Stammverzeichnis eines Laufwerks sein")
    return root


def review_folder(clip: dict) -> Path:
    """Review directory for the clip name; reject unsafe names instead of changing scope."""
    name = Path(clip["clip_name_with_extension"]).stem
    name = "".join("_" if char in invalid_path_chars else char for char in unicodedata.normalize("NFC", name))
    name = name.strip().rstrip(". ")
    if not name or name in (".", "..") or name.startswith(".") or name.split(".")[0].upper() in reserved_names:
        raise MasterBlocked("Clipname kann nicht als Prüfungsordner verwendet werden")
    return _safe(_root() / review_name / name)


def _last_path(clip: dict, event: str) -> Path | None:
    item = next((item for item in reversed(clip["history"]) if item["event"] == event), None)
    return share_path(item["detail"]).absolute() if item else None


def new_master_path(clip: dict) -> Path | None:
    """Last recorded master location; do not inspect final files after delivery."""
    return _last_path(clip, new_event)


def _checkpoint(ctx: dict) -> None:
    if callback := ctx.get("checkpoint"):
        callback()


# --------- FUNC TRANSFER ---------
def _size(path: Path) -> int:
    info = _safe(path).lstat()
    if not stat.S_ISREG(info.st_mode):
        raise MasterBlocked(f"Keine reguläre Datei: {path}")
    return info.st_size


def _existing(target: Path) -> Path | None:
    """Entry with the target name in any case; None if the folder or entry does not exist."""
    if not target.parent.is_dir():
        return None
    return next((item for item in target.parent.iterdir() if item.name.casefold() == target.name.casefold()), None)


def _rename(source: Path, target: Path) -> None:
    if os.name == "nt":
        os.rename(source, target)  # Windows refuses an existing target; on one share the server moves the data.
    else:
        os.link(source, target)  # POSIX rename would overwrite; a hard link refuses an existing target.
        source.unlink()


def _check_target(target: Path) -> None:
    if _existing(target):
        raise MasterBlocked(f"Namenskonflikt: {target}; Quelle bleibt erhalten")


def _place(source: Path, target: Path) -> None:
    """Move a file on the share without reading its content; never overwrite."""
    source, target = _safe(source), _safe(target)
    size = _size(source)
    if not size:
        raise MasterBlocked(f"Leere Masterdatei: {source}")
    _check_target(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    _rename(source, target)
    if _size(target) != size:
        raise MasterBlocked(f"Verschieben nach {target} konnte nicht bestätigt werden")


def new_master_target(clip: dict, name: str) -> Path:
    """Storage path of a new master for the current keep_old_master setting."""
    folder = review_folder(clip) / "neu" if cfg.get("keep_old_master", False) else _root()
    return _safe(folder / name)


def store_new_master(clip: dict, relative: str, name: str, ctx: dict) -> Path:
    """Move a generated master; the location is recorded before the move, so a restart can finish it."""
    target = new_master_target(clip, name)
    source = safe_work_path(relative).absolute()
    if os.path.lexists(source) and new_master_path(clip) == target and target.is_file() and _size(target) == _size(source):
        source.unlink()  # 1.18.0 recorded the location only after a verified copy; the work copy is left over.
    elif os.path.lexists(source):
        _check_target(target)
        if new_master_path(clip) != target:
            add_event(clip, new_event, str(target))
            _checkpoint(ctx)
        _place(source, target)
    elif new_master_path(clip) != target or not target.is_file() or not _size(target):
        raise MasterBlocked(f"Neuer Master fehlt: {source}")
    return target


def archive_old_master(clip: dict, ctx: dict) -> None:
    """Move all files of a restored master into alt after QC; ingested masters stay untouched."""
    master = clip["files"]["master"]
    if not master or master.get("deleted_at") or master["source"] == ingest_source:
        return
    target = _safe(review_folder(clip) / "alt")
    source = _safe(share_path(master["folder"]))
    if source == target:
        return
    names = master["names"]
    if len({name.casefold() for name in names}) != len(names):
        raise MasterBlocked("Mehrdeutige Dateinamen im alten Master")
    for name in names:
        if Path(name).name != name or any(char in invalid_path_chars for char in name):
            raise MasterBlocked(f"Unsicherer Masterdateiname: {name!r}")
    for name in names:
        if os.path.lexists(source / name):
            _place(source / name, target / name)
        elif not (target / name).is_file():  # Moved by an interrupted run.
            raise MasterBlocked(f"Alte Masterdatei fehlt: {source / name}")
    add_event(clip, old_origin_event, str(source))
    master.update(folder=str(target), last_seen_at=now())
    add_event(clip, "Alter Master gesichert", str(target))
    _checkpoint(ctx)
    try:
        source.rmdir()
    except OSError:
        pass  # Not empty or already gone.


# --------- FUNC REVIEW CLEANUP ---------
def _inventory(folder: Path) -> dict[Path, tuple[int, int]]:
    result, pending = {}, [folder]
    while pending:
        path = _safe(pending.pop())
        info = path.lstat()
        if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            raise MasterBlocked(f"Unbekannter Dateityp: {path}")
        result[path] = (info.st_mode, info.st_size if stat.S_ISREG(info.st_mode) else 0)
        if stat.S_ISDIR(info.st_mode):
            pending.extend(path.iterdir())
    return result


def _owner(state: dict, group: Path) -> dict | None:
    matches = []
    for clip in state["clips"].values():
        master = clip["files"]["master"]
        location = new_master_path(clip)
        if ((master and share_path(master["folder"]).absolute().is_relative_to(group))
                or (location and location.is_relative_to(group)) or review_folder(clip) == group):
            matches.append(clip)
    if len(matches) > 1:
        raise MasterBlocked(f"Prüfungsordner gehört zu mehreren Clips: {group}")
    return matches[0] if matches else None


def _delete_old(folder: Path, expected: dict | None = None) -> None:
    if not os.path.lexists(folder):
        return
    snapshot = _inventory(folder)
    if expected is not None and snapshot != expected:
        raise MasterBlocked(f"Alte Master seit der Vorprüfung verändert: {folder}")
    if snapshot != _inventory(folder):
        raise MasterBlocked(f"Prüfungsablage verändert: {folder}")
    for path, expected in sorted(snapshot.items(), key=lambda item: len(item[0].parts), reverse=True):
        info = _safe(path).lstat()
        if (info.st_mode, info.st_size if stat.S_ISREG(info.st_mode) else 0) != expected:
            raise MasterBlocked(f"Datei/Ordner verändert; nicht gelöscht: {path}")
        if stat.S_ISDIR(info.st_mode):
            path.rmdir()
        else:
            path.unlink()


def cleanup_review(state: dict, ctx: dict) -> None:
    """Flatten neu trees, delete verified alt trees and empty review directories when keep_old_master is false."""
    if cfg.get("keep_old_master", False):
        return
    root = share_path(cfg["master_dir"]).absolute() / review_name
    try:
        root, destination = _safe(root), _root()
        if not os.path.lexists(root):
            return
        snapshot = _inventory(root)
        groups = {}
        for path, info in snapshot.items():
            parts = path.relative_to(root).parts
            index = next((i for i, part in enumerate(parts) if part in ("alt", "neu")), None)
            if index is None:
                if stat.S_ISREG(info[0]):
                    raise MasterBlocked(f"Unerwartete Datei außerhalb alt/neu: {path}")
                continue
            group = root.joinpath(*parts[:index])
            if group == root:
                raise MasterBlocked(f"Clipordner fehlt: {path}")
            groups.setdefault(group, {"new": [], "owner": None})
            if parts[index] == "neu" and stat.S_ISREG(info[0]):
                groups[group]["new"].append(path)
        targets = {}
        for group, record in groups.items():
            record["old"] = {path: info for path, info in snapshot.items() if path.is_relative_to(group / "alt")}
            record["owner"] = _owner(state, group)
            for source in record["new"]:
                key = source.name.casefold()
                if key in targets:
                    raise MasterBlocked(f"Doppelter Zielname in der Prüfungsablage: {source.name}")
                targets[key] = source
                target = destination / source.name
                clashes = [item for item in destination.iterdir() if item.name.casefold() == key]
                if clashes:
                    raise MasterBlocked(f"Namenskonflikt im Master-Ziel: {target}")
        if snapshot != _inventory(root):
            raise MasterBlocked("Prüfungsablage während der Vorprüfung verändert")
    except (OSError, ValueError, MasterBlocked) as exc:
        issue(ctx, "note", master_blocked, str(root), str(exc))
        return
    for group, record in sorted(groups.items(), key=lambda item: str(item[0]).casefold()):
        clip = record["owner"]
        try:
            for source in sorted(record["new"]):
                target = destination / source.name
                if clip and new_master_path(clip) == source:
                    add_event(clip, new_event, str(target))
                    _checkpoint(ctx)
                _place(source, target)
            location = new_master_path(clip) if clip else None
            if location and location.is_relative_to(group):
                target = destination / location.name
                if not target.is_file() or target.stat().st_size == 0:
                    raise MasterBlocked(f"Neuer Master noch nicht final übernommen: {location}")
                add_event(clip, new_event, str(target))
                _checkpoint(ctx)
            if not clip and not record["new"] and os.path.lexists(group / "alt"):
                raise MasterBlocked(f"Keine Zuordnung/Übernahmebestätigung für alte Master: {group}")
            _delete_old(group / "alt", record["old"])
            if clip and clip["files"]["master"]:
                master = clip["files"]["master"]
                if share_path(master["folder"]).absolute() == group / "alt":
                    origin = _last_path(clip, old_origin_event)
                    if master["source"] == ingest_source and origin:  # Copy made by 1.18.1; the original stays.
                        master.update(folder=str(origin), last_seen_at=now())
                    else:
                        master["deleted_at"] = now()
                    add_event(clip, "Prüfungsablage bereinigt", str(group))
                    _checkpoint(ctx)
            for path in sorted(_inventory(group), key=lambda item: len(item.parts), reverse=True):
                if path.is_dir():
                    path.rmdir()
        except (OSError, ValueError, MasterBlocked) as exc:
            issue(ctx, "note", master_blocked, str(group), str(exc))
            if clip:
                set_issue(clip, "sticky", master_blocked, str(exc))
    for path in sorted(_inventory(root), key=lambda item: len(item.parts), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
