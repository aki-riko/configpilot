# coding: utf-8
"""将阻塞任务串行放到后台线程，并在 QObject 所在线程交付结果。"""

from __future__ import annotations

from collections.abc import Callable
import itertools
import logging
import queue
import threading
from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, Property, QTimer, Signal, Slot


LOGGER = logging.getLogger(__name__)
_STOP = object()


class SerialTaskRunner(QObject):
    """后台串行执行任务，避免阻塞 GUI，同时保留任务提交顺序。"""

    busyChanged = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        thread_name: str,
        drain_on_close: bool = False,
    ):
        super().__init__(parent)
        self._tasks: queue.Queue = queue.Queue()
        self._results: queue.Queue = queue.Queue()
        self._callbacks: dict[
            int,
            tuple[Callable[[Any], None], Callable[[Exception], None]],
        ] = {}
        self._ids = itertools.count(1)
        self._pending = 0
        self._drain_on_close = bool(drain_on_close)
        self._closed = threading.Event()
        self._result_timer = QTimer(self)
        self._result_timer.setInterval(5)
        self._result_timer.timeout.connect(self._drain_results)
        self._thread = threading.Thread(
            target=self._worker_loop,
            args=(self._tasks, self._results, self._closed),
            daemon=True,
            name=thread_name,
        )
        self._thread.start()
        app = QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.close)
        if parent is not None:
            parent.destroyed.connect(self.close)

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._pending > 0

    def submit(
        self,
        operation: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> int:
        if self._closed.is_set():
            raise RuntimeError("后台任务队列已关闭")
        task_id = next(self._ids)
        was_busy = self.busy
        self._callbacks[task_id] = (on_success, on_error)
        self._pending += 1
        if not was_busy:
            self.busyChanged.emit()
        if not self._result_timer.isActive():
            self._result_timer.start()
        self._tasks.put((task_id, operation))
        return task_id

    @staticmethod
    def _worker_loop(tasks: queue.Queue, results: queue.Queue, closed: threading.Event) -> None:
        while True:
            item = tasks.get()
            if item is _STOP:
                return
            task_id, operation = item
            try:
                result = operation()
                error = None
            except Exception as exc:  # 后台异常统一交回主线程处理
                result = None
                error = exc
            if closed.is_set():
                continue
            results.put((task_id, result, error))

    @Slot()
    def _drain_results(self) -> None:
        while True:
            try:
                task_id, result, error = self._results.get_nowait()
            except queue.Empty:
                break
            self._deliver(task_id, result, error)
        if self._pending == 0:
            self._result_timer.stop()

    @Slot(int, object, object)
    def _deliver(self, task_id: int, result: object, error: object) -> None:
        callbacks = self._callbacks.pop(task_id, None)
        if callbacks is None:
            return
        on_success, on_error = callbacks
        try:
            if isinstance(error, Exception):
                on_error(error)
            else:
                on_success(result)
        except Exception:
            LOGGER.exception("后台任务结果交付失败")
        finally:
            if self._closed.is_set():
                return
            self._pending -= 1
            if self._pending == 0:
                self.busyChanged.emit()

    @Slot()
    def close(self) -> None:
        """停止接收任务；需要排空的队列在后台完成，调用线程不等待。"""
        if self._closed.is_set():
            return
        self._closed.set()
        try:
            self._result_timer.stop()
        except RuntimeError:
            LOGGER.debug("任务队列销毁期间结果计时器已释放", exc_info=True)
        was_busy = self._pending > 0
        self._callbacks.clear()
        self._pending = 0
        while True:
            try:
                self._results.get_nowait()
            except queue.Empty:
                break
        if not self._drain_on_close:
            while True:
                try:
                    self._tasks.get_nowait()
                except queue.Empty:
                    break
        self._tasks.put(_STOP)
        if was_busy:
            try:
                self.busyChanged.emit()
            except RuntimeError:
                LOGGER.debug("任务队列销毁期间无法发送忙碌状态", exc_info=True)
