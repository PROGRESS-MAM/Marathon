"""Console output, progress display and main log."""
# --------- IMPORTS ---------
import threading

from toolbox import tb_write_log

from .config import main_log


# --------- INIT ---------
progress_lock = threading.Lock()
progress_width = 0


# --------- FUNC ---------
def _finish_progress() -> None:
    global progress_width
    with progress_lock:
        if progress_width:
            print(flush=True)
            progress_width = 0


def search_progress(message: str) -> None:
    """Print search progress; transient messages overwrite the current console line."""
    global progress_width
    transient = message.startswith("Cached [") or "warte seit " in message or "lade " in message
    with progress_lock:
        if transient:
            print("\r" + message + " " * max(0, progress_width - len(message)), end="", flush=True)
            progress_width = len(message)
        else:
            if progress_width:
                print(flush=True)
                progress_width = 0
            print(message, flush=True)


def log(message: str) -> None:
    """Print a message and append it to the main log."""
    _finish_progress()
    print(message, flush=True)
    tb_write_log(main_log, message)
