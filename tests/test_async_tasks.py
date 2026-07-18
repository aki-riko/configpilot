import threading
import time
import unittest

from PySide6.QtCore import QTimer

from backend.async_tasks import SerialTaskRunner
from tests.qt_test_utils import APP, wait_for_idle, wait_until


class AsyncTaskTests(unittest.TestCase):
    def test_slow_task_does_not_block_qt_event_loop(self):
        _ = APP
        runner = SerialTaskRunner(thread_name="ConfigPilotResponsivenessTest")
        timer_fired = []
        completed = []
        errors = []
        started = time.perf_counter()

        QTimer.singleShot(
            10,
            lambda: timer_fired.append(time.perf_counter() - started),
        )
        runner.submit(
            lambda: time.sleep(0.2),
            lambda result: completed.append(True),
            errors.append,
        )

        wait_until(lambda: bool(timer_fired), timeout=0.15)
        self.assertTrue(runner.busy)
        self.assertLess(timer_fired[0], 0.15)
        wait_for_idle(runner, "busy")
        self.assertEqual(completed, [True])
        self.assertEqual(errors, [])

    def test_result_callback_returns_to_gui_thread(self):
        _ = APP
        runner = SerialTaskRunner(thread_name="ConfigPilotThreadAffinityTest")
        main_thread = threading.get_ident()
        delivered = []
        errors = []

        runner.submit(
            threading.get_ident,
            lambda worker_thread: delivered.append(
                (worker_thread, threading.get_ident())
            ),
            errors.append,
        )
        wait_for_idle(runner, "busy")

        self.assertEqual(len(delivered), 1)
        worker_thread, callback_thread = delivered[0]
        self.assertNotEqual(worker_thread, main_thread)
        self.assertEqual(callback_thread, main_thread)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
