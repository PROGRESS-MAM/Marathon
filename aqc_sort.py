# --------- IMPORTS ---------
import argparse
import configparser
import csv
import os
import traceback
from datetime import datetime
from pathlib import Path

from toolbox import tb_write_log

# --------- STATIC ---------
csv_columns = ("Unterordner", "Datei", "Endung", "Groesse_Bytes", "Geaendert", "Schema", "Identifier", "Titel")

# --------- CONFIG ---------
app_name = "AQC-Sort"
app_version = "0.1.0"
project_dir = Path(__file__).resolve().parent
config_path = project_dir / "res" / "config.ini"  # Marathon's config: root_path, defa_dir, proxy_prefix
output_dir = project_dir / "reports" / "aqc"
main_log = project_dir / "log" / "aqc_sort.log"
aqc_dir = "AQC"  # Below defa_dir

# --------- INIT ---------
main_log.parent.mkdir(parents=True, exist_ok=True)
tb_write_log(main_log, f"{app_name} {app_version} started.")


# --------- FUNC ---------
def _log(message: str) -> None:
    print(message, flush=True)
    tb_write_log(main_log, message)


def _read_paths() -> dict[str, str]:
    parser = configparser.ConfigParser(interpolation=None)
    with config_path.open(encoding="utf-8-sig") as handle:
        parser.read_file(handle)
    values = {key: parser.get("paths", key, fallback="").strip() for key in ("root_path", "defa_dir", "proxy_prefix")}
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise ValueError(f"In {config_path} fehlt [paths] {', '.join(missing)}.")
    return values


def _parse_name(name: str, prefix: str) -> tuple[str, str] | None:
    """Identifier and title without extension from <prefix>__<Identifier>__<Titel>.<Endung>; None if not in scheme."""
    prefix += "__"
    if not name.casefold().startswith(prefix.casefold()):
        return None
    identifier, separator, title = name[len(prefix):].partition("__")
    identifier, title = identifier.strip(), Path(title).stem.strip()
    return (identifier, title) if separator and identifier and title else None


def _list_files(source: Path, prefix: str) -> tuple[list[dict], list[str]]:
    rows, errors = [], []
    for folder, dirs, files in os.walk(source, onerror=lambda exc: errors.append(f"{exc.filename}: {exc.strerror}")):
        dirs.sort(key=str.casefold)
        subfolder = Path(folder).relative_to(source).as_posix()
        for name in sorted(files, key=str.casefold):
            try:
                info = (Path(folder) / name).stat()
            except OSError as exc:
                errors.append(f"{Path(folder) / name}: {exc.strerror}")
                continue
            parsed = _parse_name(name, prefix)
            rows.append(dict(zip(csv_columns, (
                "" if subfolder == "." else subfolder, name, Path(name).suffix.casefold(), info.st_size,
                datetime.fromtimestamp(info.st_mtime).isoformat(timespec="seconds"),
                "ja" if parsed else "nein", *(parsed or ("", ""))))))
    return rows, errors


def _write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8-sig", newline="") as handle:  # BOM so Excel shows umlauts correctly.
        writer = csv.DictWriter(handle, fieldnames=csv_columns, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


# --------- MAIN ---------
def main() -> None:
    parser = argparse.ArgumentParser(description="AQC-Dateien auflisten (Grundlage für die Zuordnung zur Marathon-JSON)")
    parser.add_argument("--source", type=Path, help="anderer AQC-Ordner als <root_path>/<defa_dir>/AQC")
    args = parser.parse_args()
    paths = _read_paths()
    source = args.source or Path(paths["root_path"]) / paths["defa_dir"] / aqc_dir
    if not source.is_dir():
        raise FileNotFoundError(f"AQC-Ordner nicht erreichbar: {source}")
    _log(f"Liste AQC-Dateien in {source} ...")
    rows, errors = _list_files(source, paths["proxy_prefix"])
    target = output_dir / f"aqc_files_{datetime.now():%Y-%m-%d_%H-%M-%S}.csv"
    _write_csv(rows, target)
    for error in errors:
        _log(f"Nicht lesbar: {error}")
    in_scheme = sum(row["Schema"] == "ja" for row in rows)
    _log(f"{len(rows)} Dateien gelistet, davon {in_scheme} im Namensschema, {len(errors)} nicht lesbar. Liste: {target}")


# --------- EXEC ---------
if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        error_message = f"Unhandled error in main: {exc}"
        print(error_message)
        tb_write_log(main_log, error_message)
        tb_write_log(main_log, traceback.format_exc())
        raise SystemExit(1) from exc
