import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class DummySignal:
    def __init__(self, *args, **kwargs):
        self.emissions = []

    def emit(self, *args):
        self.emissions.append(args)


class DummyQObject:
    def __init__(self, parent=None):
        pass


def dummy_slot(*args, **kwargs):
    def decorate(func):
        return func

    return decorate


def dummy_property(*args, **kwargs):
    def decorate(func):
        return property(func)

    return decorate


def install_pyside_stub():
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QObject = DummyQObject
    qtcore.Signal = DummySignal
    qtcore.Slot = dummy_slot
    qtcore.Property = dummy_property

    pyside = types.ModuleType("PySide6")
    pyside.QtCore = qtcore

    sys.modules["PySide6"] = pyside
    sys.modules["PySide6.QtCore"] = qtcore


class CodexConfigAuthTests(unittest.TestCase):
    def load_module(self):
        install_pyside_stub()
        sys.modules.pop("backend.codex_config", None)
        return importlib.import_module("backend.codex_config")

    def test_set_key_moves_old_auth_to_backup_and_writes_clean_auth(self):
        codex_config = self.load_module()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            codex_home = tmp_path / ".codex"
            codex_home.mkdir()
            old_auth = {
                "OPENAI_API_KEY": "old-key",
                "auth_mode": "chatgpt",
                "access_token": "old-access-token",
                "refresh_token": "old-refresh-token",
            }
            auth_path = codex_home / "auth.json"
            auth_path.write_text(json.dumps(old_auth), encoding="utf-8")

            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(tmp_path)
            (tmp_path / "model_profiles.json").write_text(
                (ROOT / "model_profiles.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            config = codex_config.CodexConfig()
            config.setKey("new-key")

            new_auth = json.loads(auth_path.read_text(encoding="utf-8"))
            backup_auth = json.loads((codex_home / "auth.json.bak").read_text(encoding="utf-8"))

            self.assertEqual(
                new_auth,
                {
                    "OPENAI_API_KEY": "new-key",
                    "auth_mode": "apikey",
                },
            )
            self.assertEqual(backup_auth, old_auth)
            self.assertNotIn("access_token", new_auth)
            self.assertNotIn("refresh_token", new_auth)

    def test_model_profiles_match_gpt56_and_preserve_other_models(self):
        codex_config = self.load_module()

        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()

            expected_values = ["low", "medium", "high", "xhigh"]
            expected_text = ["轻度", "中", "高", "极高"]
            for model in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"):
                options = config.reasoningOptionsForModel(model)
                self.assertEqual([item["value"] for item in options], expected_values)
                self.assertEqual([item["text"] for item in options], expected_text)
                self.assertEqual(
                    config.highestReasoningEffortForModel(model), "xhigh"
                )
                self.assertEqual(
                    config.contextPresetForModel(model),
                    {
                        "menuText": "稳定上下文",
                        "contextWindow": 258400,
                        "autoCompactLimit": 245000,
                        "toolOutputLimit": 6000,
                        "maxContextWindow": 258400,
                        "maxAutoCompactLimit": 245000,
                    },
                )

            gpt55_options = config.reasoningOptionsForModel("gpt-5.5")
            self.assertEqual(
                [item["value"] for item in gpt55_options],
                ["", "low", "medium", "high", "xhigh"],
            )
            self.assertEqual(
                config.highestReasoningEffortForModel("gpt-5.5"), "xhigh"
            )
            self.assertEqual(
                config.contextPresetForModel("gpt-5.5"),
                {
                    "menuText": "稳定上下文",
                    "contextWindow": 258400,
                    "autoCompactLimit": 245000,
                    "toolOutputLimit": 6000,
                    "maxContextWindow": 258400,
                    "maxAutoCompactLimit": 245000,
                },
            )

            other_options = config.reasoningOptionsForModel("custom-model")
            self.assertEqual(
                [item["value"] for item in other_options],
                ["", "low", "medium", "high", "xhigh"],
            )
            self.assertEqual(
                config.highestReasoningEffortForModel("custom-model"), "xhigh"
            )
            self.assertEqual(config.contextPresetForModel("custom-model"), {})
            self.assertEqual(
                config.stableContextPreset(),
                {
                    "menuText": "稳定上下文",
                    "contextWindow": 258400,
                    "autoCompactLimit": 245000,
                    "toolOutputLimit": 6000,
                    "maxContextWindow": 258400,
                    "maxAutoCompactLimit": 245000,
                },
            )

    def test_apply_real_gpt56_config_sample(self):
        codex_config = self.load_module()

        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            config_path = codex_home / "config.toml"
            config_path.write_text(
                'model_provider = "relay"\n\n[model_providers.relay]\n'
                'name = "relay"\nbase_url = "https://api.9li.life/v1"\n'
                'wire_api = "responses"\n',
                encoding="utf-8",
            )
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()

            config.notify.emissions.clear()
            config.applyConfig(
                {
                    "baseUrl": "https://api.9li.life/v1",
                    "provider": "relay",
                    "wireApi": "responses",
                    "model": "gpt-5.6-sol",
                    "reasoningEffort": "max",
                }
            )
            self.assertEqual(
                config.notify.emissions[-1],
                (2, "参数无效", "gpt-5.6-sol 不支持思考等级 max"),
            )
            with config_path.open("rb") as handle:
                rejected = codex_config.tomllib.load(handle)
            self.assertNotIn("model", rejected)
            self.assertNotIn("model_reasoning_effort", rejected)

            config.applyConfig(
                {
                    "baseUrl": "https://api.9li.life/v1",
                    "provider": "relay",
                    "wireApi": "responses",
                    "model": "gpt-5.6-sol",
                    "reasoningEffort": "xhigh",
                    "modelContextWindow": "372000",
                    "modelAutoCompactTokenLimit": "353000",
                    "toolOutputTokenLimit": "6000",
                }
            )

            with config_path.open("rb") as handle:
                saved = codex_config.tomllib.load(handle)
            self.assertEqual(saved["model"], "gpt-5.6-sol")
            self.assertEqual(saved["model_reasoning_effort"], "xhigh")
            self.assertEqual(saved["model_context_window"], 258400)
            self.assertEqual(saved["model_auto_compact_token_limit"], 245000)
            self.assertEqual(saved["tool_output_token_limit"], 6000)

    def test_model_fetch_notification_does_not_embed_model_list(self):
        codex_config = self.load_module()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            codex_home = tmp_path / ".codex"
            codex_home.mkdir()
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            config.notify.emissions.clear()

            model_ids = [
                "codex-auto-review",
                "gpt-5.4",
                "gpt-5.4-mini",
                "gpt-5.5",
                "gpt-5.5-openai-compact",
                "gpt-5.6-luna",
                "gpt-5.6-sol",
                "gpt-5.6-terra",
                "model-9",
                "model-10",
                "model-11",
            ]

            class Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    return False

                def read(self):
                    return json.dumps(
                        {"data": [{"id": model_id} for model_id in model_ids]}
                    ).encode("utf-8")

            with patch("urllib.request.urlopen", return_value=Response()):
                config._fetch_models_worker("https://example.test/v1", "")

            self.assertEqual(config.availableModels, model_ids)
            self.assertEqual(
                config.notify.emissions[-1],
                (1, "获取到 11 个模型", "可在模型下拉列表中选择"),
            )

    def test_real_relay_host_gets_v1_for_config_and_model_fetch(self):
        codex_config = self.load_module()

        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()

            config.applyConfig(
                {
                    "baseUrl": "https://api.9li.life",
                    "provider": "relay",
                    "wireApi": "responses",
                    "model": "gpt-5.6-sol",
                }
            )
            with (codex_home / "config.toml").open("rb") as handle:
                saved = codex_config.tomllib.load(handle)
            self.assertEqual(
                saved["model_providers"]["relay"]["base_url"],
                "https://api.9li.life/v1",
            )

            class Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, traceback):
                    return False

                def read(self):
                    return b'{"data":[{"id":"gpt-5.6-sol"}]}'

            with patch("urllib.request.urlopen", return_value=Response()) as mocked:
                config._fetch_models_worker("https://api.9li.life", "")
            self.assertEqual(
                mocked.call_args.args[0].full_url,
                "https://api.9li.life/v1/models",
            )


if __name__ == "__main__":
    unittest.main()
