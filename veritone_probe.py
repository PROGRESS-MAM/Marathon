# --------- IMPORTS ---------
import argparse
import configparser
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# --------- STATIC ---------
token_key = "vt_api_token"
name_keys = ("name", "label", "displayName", "title", "filterName")
id_keys = ("id", "filterId")
count_keys = ("count", "docCount", "documentCount")

# --------- CONFIG ---------
app_name = "Veritone-Probe"
app_version = "0.2"
project_dir = Path(__file__).resolve().parent
res_dir = project_dir / "res"
probe_dir = project_dir / "probe"
default_base_url = "https://crxextapi.pd.dmh.veritone.com/assets-api"
timeout = 120


# --------- FUNC: ACCESS ---------
def _settings() -> tuple[str, Path]:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(res_dir / "config.ini", encoding="utf-8-sig")
    base_url = parser.get("veritone", "base_url", fallback="").strip() or default_base_url
    return base_url.rstrip("/"), res_dir / (parser.get("paths", "cred_file", fallback="").strip() or "cred.env")


def _token(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"{path} fehlt.")
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = line.strip().removeprefix("export ").partition("=")
        if separator and key.strip() == token_key and value.strip().strip("\"'"):
            return value.strip().strip("\"'")
    raise SystemExit(f"{path}: {token_key} fehlt oder ist leer.")


def _call(path: str, params: dict | None = None, body: dict | None = None, auth: str = "query"):
    """GET or POST (with body) against the Assets API; returns (status, parsed JSON or text)."""
    base_url, token_path = _settings()
    token, params = _token(token_path), dict(params or {})
    headers = {"Accept": "application/json"}
    if auth == "bearer":
        headers["Authorization"] = f"Bearer {token}"
    else:
        params["api_key"] = token
    if body is not None:
        headers["Content-Type"] = "application/json"
    url = f"{base_url}{path}" + (f"?{urlencode(params)}" if params else "")
    request = Request(url, data=None if body is None else json.dumps(body).encode("utf-8"), headers=headers)
    # Never print the URL, it may contain the token.
    try:
        with urlopen(request, timeout=timeout) as response:
            status, raw = response.status, response.read()
    except HTTPError as exc:
        status, raw = exc.code, exc.read()
    except (URLError, OSError) as exc:
        raise SystemExit(f"Veritone nicht erreichbar ({path}): {exc}") from None
    text = raw.decode("utf-8", "replace")
    try:
        return status, json.loads(text)
    except ValueError:
        return status, text


def _ok(status: int, data, path: str):
    if status != 200:
        raise SystemExit(f"HTTP {status} auf {path}: {str(data)[:500]}")
    return data


def _save(name: str, data) -> Path:
    probe_dir.mkdir(exist_ok=True)
    target = probe_dir / name
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


# --------- FUNC: ANALYSIS ---------
def _paths(data, prefix: str = ""):
    """Yield (path, scalar value) for every leaf; name/value pairs are shown as <name>."""
    if isinstance(data, dict):
        if isinstance(data.get("name"), str) and "value" in data and not isinstance(data["value"], (dict, list)):
            yield f"{prefix}<{data['name']}>", data["value"]
        for key, value in data.items():
            yield from _paths(value, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            yield from _paths(value, f"{prefix}[{index}]")
    else:
        yield prefix, data


def _short(value, width: int = 100) -> str:
    text = repr(value)
    return text if len(text) <= width else text[:width - 3] + "..."


def _outline(data, depth: int = 0):
    """Print filter-like nodes (name, id, count) of the filter tree, indented by depth."""
    if isinstance(data, list):
        for value in data:
            _outline(value, depth)
        return
    if not isinstance(data, dict):
        return
    label = next((data[key] for key in name_keys if isinstance(data.get(key), str)), None)
    if label is not None:
        extras = [f"{key}={data[key]}" for key in (*id_keys, *count_keys) if key in data and not isinstance(data[key], (dict, list))]
        print(f"{'  ' * depth}- {label}" + (f"  ({', '.join(extras)})" if extras else ""))
    for value in data.values():
        _outline(value, depth + (label is not None))


def _search(query: str, count: int) -> list:
    data = _ok(*_call("/v1/search", {"q": query, "n": count, "i": 0}), "/v1/search")
    print(f"totalCount={data.get('totalCount')}, Seitenfelder: {', '.join(key for key in data if key != 'items')}")
    return data.get("items") or []


# --------- FUNC: COMMANDS ---------
def cmd_check(args) -> None:
    for auth in ("query", "bearer"):
        status, data = _call("/v1/search", {"q": "", "n": 1}, auth=auth)
        total = data.get("totalCount") if isinstance(data, dict) else None
        print(f"Anmeldung per {auth:6}: HTTP {status}" + (f", totalCount={total}" if status == 200 else f", {str(data)[:200]}"))


def cmd_filters(args) -> None:
    data = _ok(*_call("/v1/filter/filterTree", {"counted": "true"}), "/v1/filter/filterTree")
    print(f"Gespeichert: {_save('filter_tree.json', data)}")
    _outline(data)


def cmd_sample(args) -> None:
    items = _search(args.query, args.count)
    print(f"Gespeichert: {_save('sample.json', items)}")
    for number, item in enumerate(items[:args.show], 1):
        print(f"\n--- Treffer {number} ---")
        for path, value in _paths(item):
            print(f"{path} = {_short(value)}")


def cmd_find(args) -> None:
    items, needle = _search(args.query or args.value, args.count), args.value.casefold()
    hits = {}
    for item in items:
        for path, value in _paths(item):
            text = str(value).casefold()
            if needle == text or (args.contains and needle in text):
                hits.setdefault(path, value)
    print(f"Gespeichert: {_save('find.json', items)}")
    print("\n".join(f"{path} = {_short(value)}" for path, value in hits.items()) or f"{args.value!r} in keinem Feld gefunden.")


def cmd_formats(args) -> None:
    data = _ok(*_call("/v1/clip/fieldFormats", {"fieldNames": ",".join(args.names)}), "/v1/clip/fieldFormats")
    known = {entry.get("name"): entry for entry in data if isinstance(entry, dict)} if isinstance(data, list) else {}
    for name in args.names:
        print(f"{name}: " + (json.dumps(known[name], ensure_ascii=False) if name in known else "unbekannt"))


def _expression(pairs: list[str], op: str) -> dict:
    parts = []
    for pair in pairs:
        field, separator, value = pair.partition("=")
        if not separator or not field.strip():
            raise SystemExit(f"Bedingung {pair!r}: erwartet FELD=WERT")
        parts.append({"fieldExpression": {"fieldName": field.strip(), "op": op, "value": value.strip()}})
    return parts[0] if len(parts) == 1 else {"and": parts}


def cmd_test(args) -> None:
    body = {"searchExpression": _expression(args.conditions, args.op), "pageSize": args.page_size}
    print("Anfrage:", json.dumps(body["searchExpression"], ensure_ascii=False))
    pages = []
    for number in (0, 1):
        data = _ok(*_call("/v1/search/advancedSearch", body={**body, "pageNumber": number}), "/v1/search/advancedSearch")
        items = data.get("items") or []
        pages.append(items)
        info = {key: data.get(key) for key in ("totalCount", "currentPage", "pageSize", "numberOfPages", "hasNextPage")}
        print(f"pageNumber={number}: {len(items)} Treffer, {info}")
        if args.clip_field:
            values = [value for item in items for path, value in _paths(item)
                      if path == args.clip_field or path.endswith((f".{args.clip_field}", f"<{args.clip_field}>"))]
            print(f"  {args.clip_field}: {values}")
    print(f"Gespeichert: {_save('test.json', pages)}")


def cmd_collections(args) -> None:
    import marathon

    problem = marathon._load_config()
    if problem:
        raise SystemExit(problem)
    mapping = marathon._load_mapping()
    for name, ids in marathon._veritone_clip_ids(mapping).items():
        print(f"{name}: {len(ids)} Clip IDs")


# --------- MAIN ---------
def main() -> None:
    parser = argparse.ArgumentParser(description=f"{app_name} {app_version}: Veritone-Felder und -Filter klären (nur lesend).")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="Token prüfen (api_key-Parameter und Bearer-Header)").set_defaults(run=cmd_check)
    commands.add_parser("filters", help="Filterbaum mit Namen, IDs und Anzahlen").set_defaults(run=cmd_filters)
    sample = commands.add_parser("sample", help="Rohtreffer mit allen Feldpfaden anzeigen")
    sample.add_argument("--query", default="", help="Suchtext (leer = alle)")
    sample.add_argument("--count", type=int, default=3, help="Anzahl Treffer (max. 200)")
    sample.add_argument("--show", type=int, default=1, help="Anzahl ausgegebener Treffer")
    sample.set_defaults(run=cmd_sample)
    find = commands.add_parser("find", help="Feldpfade finden, die einen bekannten Wert enthalten")
    find.add_argument("value", help="z. B. ein 001 Identifier, 'Historiathek' oder 'Dokumentarfilm'")
    find.add_argument("--query", help="abweichender Suchtext")
    find.add_argument("--count", type=int, default=20)
    find.add_argument("--contains", action="store_true", help="auch Teiltreffer anzeigen")
    find.set_defaults(run=cmd_find)
    formats = commands.add_parser("formats", help="Feldnamen gegen das Metadaten-Vokabular prüfen")
    formats.add_argument("names", nargs="+")
    formats.set_defaults(run=cmd_formats)
    test = commands.add_parser("test", help="advancedSearch wie in Marathon testen (Seiten 0 und 1)")
    test.add_argument("conditions", nargs="+", help="FELD=WERT, mehrere werden mit UND verknüpft")
    test.add_argument("--op", default="Is", choices=("Is", "Contains", "In"))
    test.add_argument("--page-size", type=int, default=2)
    test.add_argument("--clip-field", help="internes Feld der Clip ID zum Anzeigen")
    test.set_defaults(run=cmd_test)
    commands.add_parser("collections", help="Veritone-Abfrage aller Kollektionen wie in Marathon (nur Anzahlen)").set_defaults(run=cmd_collections)
    args = parser.parse_args()
    args.run(args)


# --------- EXEC ---------
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit("Abgebrochen.") from None
