from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QObject, Signal


class StatusLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class StatusMessage:
    text: str
    level: StatusLevel = StatusLevel.INFO


class StatusController(QObject):
    changed = Signal(StatusMessage)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current = StatusMessage("Ready")

    def post(self, text: str, level: StatusLevel = StatusLevel.INFO) -> None:
        self.current = StatusMessage(text, level)
        self.changed.emit(self.current)

    def info(self, text: str) -> None:
        self.post(text, StatusLevel.INFO)

    def warning(self, text: str) -> None:
        self.post(text, StatusLevel.WARNING)

    def error(self, text: str) -> None:
        self.post(text, StatusLevel.ERROR)
