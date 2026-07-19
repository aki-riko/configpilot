import subprocess
import unittest
from unittest import mock

from backend import system_launcher


class SystemLauncherTests(unittest.TestCase):
    def test_http_url_validation_rejects_local_and_malformed_targets(self):
        self.assertTrue(system_launcher.is_http_url("https://example.com/release"))
        self.assertTrue(system_launcher.is_http_url("http://127.0.0.1:8080/release"))
        self.assertFalse(system_launcher.is_http_url("file:///tmp/release"))
        self.assertFalse(system_launcher.is_http_url("javascript:alert(1)"))
        self.assertFalse(system_launcher.is_http_url("https://[invalid"))
        self.assertFalse(system_launcher.is_http_url(""))

    def test_windows_uses_shell_association_without_subprocess_shell(self):
        with (
            mock.patch.object(system_launcher.sys, "platform", "win32"),
            mock.patch.object(system_launcher.os, "startfile") as startfile,
        ):
            self.assertTrue(system_launcher.open_external_target("C:/Temp/ConfigPilot"))

        startfile.assert_called_once_with("C:/Temp/ConfigPilot")

    def test_linux_uses_resolved_xdg_open_without_shell(self):
        process = mock.Mock(spec=subprocess.Popen)
        with (
            mock.patch.object(system_launcher.sys, "platform", "linux"),
            mock.patch.object(
                system_launcher.shutil,
                "which",
                return_value="/usr/bin/xdg-open",
            ),
            mock.patch.object(system_launcher.subprocess, "Popen", return_value=process) as popen,
        ):
            self.assertTrue(system_launcher.open_external_target("/tmp/ConfigPilot.dmg"))

        self.assertEqual(popen.call_args.args[0], ["/usr/bin/xdg-open", "/tmp/ConfigPilot.dmg"])
        self.assertNotIn("shell", popen.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
