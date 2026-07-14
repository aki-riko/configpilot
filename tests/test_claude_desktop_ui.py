from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ClaudeDesktopUiTests(unittest.TestCase):
    def read(self, relative_path):
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_backend_is_registered_and_navigation_opens_new_page(self):
        main_py = self.read("main.py")
        main_qml = self.read("qml/main.qml")

        self.assertIn("ClaudeDesktopConfig", main_py)
        self.assertIn(
            'setContextProperty("ClaudeDesktopConfig", claude_desktop)', main_py
        )
        self.assertIn('"text": "Claude"', main_qml)
        self.assertIn('Qt.resolvedUrl("views/ClaudeDesktopView.qml")', main_qml)

    def test_page_wires_gateway_sensitive_fields_and_status_sections(self):
        page = self.read("qml/views/ClaudeDesktopView.qml")
        gateway = self.read("qml/views/ClaudeGatewaySection.qml")
        advanced = self.read("qml/views/ClaudeAdvancedSection.qml")

        for component in (
            "ClaudeStatusSection",
            "ClaudeGatewaySection",
            "ClaudeAdvancedSection",
        ):
            self.assertIn(component, page)
        self.assertIn("ClaudeDesktopConfig.applyConfig", page)
        self.assertIn('"clearApiKey": fClearApiKey', page)
        self.assertIn('"clearHeaders": fClearHeaders', page)
        self.assertIn("完全退出并重新打开 Claude Desktop", page)

        self.assertIn("Authorization: Bearer", gateway)
        self.assertIn("x-api-key", gateway)
        self.assertIn("type_password", gateway)
        self.assertIn("留空保持不变", gateway)

        self.assertIn("/v1/models", advanced)
        self.assertIn("输入 JSON 对象会覆盖现有 Header", advanced)
        self.assertIn("界面不会回显已保存的值", advanced)


if __name__ == "__main__":
    unittest.main()
