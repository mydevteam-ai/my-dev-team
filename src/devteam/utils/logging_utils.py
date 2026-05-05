import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

LOG_FILE_NAME = 'mycrew.log'
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB

LOG_BACKUP_COUNT = 3

NOISY_LOGGERS = [
    'aiosqlite',
    'asyncio',
    'httpx',
    'httpcore',
    'LiteLLM',
    'urllib3.connectionpool',
]

_MESSAGE_ICONS = (
    ("Starting new project",  "🚀"),
    ("Resuming existing",     "🔄"),
    ("Starting AI Dev Team",  "🚀"),
    ("Workspace:",            "📁"),
    ("Executing",             "🔄"),
    ("Routing on complexity", "🔀"),
    ("Rate limit reached",    "⏳"),
    ("Starting task:",        "📋"),
    ("LLM call failed",       "🔁"),
    ("failed",                "❌"),
    ("not found",             "🔔"),
    ("Import error",          "🚨"),
)

_LEVEL_ICONS = {
    logging.WARNING:  "🔔",
    logging.ERROR:    "❌",
    logging.CRITICAL: "🚨",
}


def _wildcard_match(pattern: str, text: str) -> bool:
    pattern, text = pattern.lower(), text.lower()
    parts = pattern.split('*')
    if len(parts) == 1:
        return pattern in text
    pos = 0
    for part in parts:
        if not part:
            continue
        found = text.find(part, pos)
        if found == -1:
            return False
        pos = found + len(part)
    return True


def _icon_for(record: logging.LogRecord) -> str:
    msg = record.getMessage()
    for pattern, icon in _MESSAGE_ICONS:
        if _wildcard_match(pattern, msg):
            return icon
    return _LEVEL_ICONS.get(record.levelno, "")


class ConsoleDispatchFormatter(logging.Formatter):
    """Custom formatter for console output."""

    def __init__(self):
        super().__init__()
        self.root_formatter = logging.Formatter(fmt='%(message)s')
        self.default_formatter = logging.Formatter(fmt='%(name)s: %(message)s')

    def format(self, record):
        if record.name == 'root':
            return self.root_formatter.format(record)
        icon = _icon_for(record)
        formatted = self.default_formatter.format(record)
        return f"{icon} {formatted}" if icon else formatted


def setup_file_handler(file_name: str | Path, file_level = logging.DEBUG, do_rollover = False) -> logging.Handler:
    file_handler = RotatingFileHandler(
        file_name,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    if do_rollover:
        file_handler.doRollover()
    file_handler.setLevel(file_level)
    file_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    file_handler.setFormatter(file_formatter)
    return file_handler


def setup_logging(*, file_level=logging.DEBUG, console_level=logging.INFO):
    file_handler = setup_file_handler(file_name=LOG_FILE_NAME, file_level=file_level, do_rollover=True)
    handlers = [file_handler]
    if console_level is not None:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(ConsoleDispatchFormatter())
        handlers.append(console_handler)
    logging.basicConfig(level=logging.DEBUG, handlers=handlers)

    for noisy_logger in NOISY_LOGGERS:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def add_file_handler(file_name: str | Path, file_level = logging.DEBUG, do_rollover = False) -> logging.Handler:
    file_handler = setup_file_handler(file_name=file_name, file_level=file_level, do_rollover=do_rollover)
    logging.getLogger().addHandler(file_handler)
    return file_handler


def remove_file_handler(handler: logging.Handler):
    logging.getLogger().removeHandler(handler)
