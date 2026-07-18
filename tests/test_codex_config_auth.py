import importlib
import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.qt_test_utils import wait_for_idle


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class CodexConfigAuthTests(unittest.TestCase):
    def load_module(self):
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
            wait_for_idle(config)
            config.setKey("new-key")
            wait_for_idle(config)

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
            wait_for_idle(config)

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
            wait_for_idle(config)
            notices = []
            config.notify.connect(
                lambda level, title, message: notices.append((level, title, message))
            )
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
                notices[-1],
                (2, "参数无效", "gpt-5.6-sol 不支持思考等级 max"),
            )
            with config_path.open("rb") as handle:
                rejected = tomllib.load(handle)
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
            wait_for_idle(config)

            with config_path.open("rb") as handle:
                saved = tomllib.load(handle)
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
            wait_for_idle(config)
            notices = []
            config.notify.connect(
                lambda level, title, message: notices.append((level, title, message))
            )

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
                        {
                            "data": [
                                {
                                    "id": model_id,
                                    **(
                                        {
                                            "supported_reasoning_levels": [
                                                {"effort": "low"},
                                                {"effort": "medium"},
                                                {"effort": "high"},
                                                {"effort": "xhigh"},
                                                {"effort": "max"},
                                                {"effort": "ultra"},
                                            ]
                                        }
                                        if model_id == "gpt-5.6-sol"
                                        else {}
                                    ),
                                }
                                for model_id in model_ids
                            ]
                        }
                    ).encode("utf-8")

            with patch("urllib.request.urlopen", return_value=Response()):
                config.fetchModels("https://example.test/v1", "")
                wait_for_idle(config, "modelsLoading")

            self.assertEqual(config.availableModels, model_ids)
            self.assertEqual(
                notices[-1],
                (1, "获取到 11 个模型", "思考等级已从远端同步"),
            )
            self.assertEqual(
                config.reasoningOptionsForModel("gpt-5.6-sol"),
                [
                    {"value": "low", "text": "轻度"},
                    {"value": "medium", "text": "中"},
                    {"value": "high", "text": "高"},
                    {"value": "xhigh", "text": "极高"},
                ],
            )

    def test_real_relay_host_gets_v1_for_config_and_model_fetch(self):
        codex_config = self.load_module()

        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            codex_home.mkdir()
            codex_config._codex_home = lambda: str(codex_home)
            codex_config._app_dir = lambda: str(ROOT)
            config = codex_config.CodexConfig()
            wait_for_idle(config)

            config.applyConfig(
                {
                    "baseUrl": "https://api.9li.life",
                    "provider": "relay",
                    "wireApi": "responses",
                    "model": "gpt-5.6-sol",
                }
            )
            wait_for_idle(config)
            with (codex_home / "config.toml").open("rb") as handle:
                saved = tomllib.load(handle)
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

            with (
                patch("urllib.request.urlopen", return_value=Response()) as mocked,
                patch(
                    "backend.codex_config.fetch_codex_model_catalog",
                    return_value=[],
                ),
            ):
                config.fetchModels("https://api.9li.life", "")
                wait_for_idle(config, "modelsLoading")
            self.assertEqual(
                mocked.call_args.args[0].full_url,
                "https://api.9li.life/v1/models",
            )


if __name__ == "__main__":
    unittest.main()
