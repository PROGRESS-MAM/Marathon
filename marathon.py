"""Marathon start file; the logic lives in the core folder."""
# --------- IMPORTS ---------
from toolbox import tb_write_log

from core.app import main
from core.config import main_log

# --------- EXEC ---------
if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print(f"Marathon abgebrochen: {exc}")
        try:
            tb_write_log(main_log, f"Marathon abgebrochen: {exc}")
        except OSError:
            pass
        raise SystemExit(1) from exc
