"""Generic Qt worker helpers for running blocking work off the UI thread."""

from __future__ import annotations

import traceback
from typing import Any, Callable

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot


class FunctionWorker(QObject):
    """Run an arbitrary function in a QThread and emit (result) or (error)."""

    finished = pyqtSignal(object)  # result
    failed = pyqtSignal(str, str)  # message, traceback

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc), traceback.format_exc())
            return
        self.finished.emit(result)

