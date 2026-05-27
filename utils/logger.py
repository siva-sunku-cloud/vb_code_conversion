import logging
import sys
from datetime import date
from pathlib import Path
from rich.logging import RichHandler


def setup_logging() -> None:
    from config import Config

    level = getattr(logging, Config.LOG_LEVEL, logging.DEBUG)

    log_dir = Path(Config.LOG_FOLDER)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"code_conversion_{date.today().strftime('%Y_%m_%d')}.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  %(name)-25s  %(levelname)-8s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    console_handler = RichHandler(rich_tracebacks=True, show_path=False)
    console_handler.setLevel(level)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[console_handler, file_handler],
    )

    logging.getLogger(__name__).debug(
        f"Logging initialised — level={Config.LOG_LEVEL}  file={log_file}"
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
