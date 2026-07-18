import unittest

from backend.endpoint_urls import append_api_path, normalize_v1_base_url


class EndpointUrlTests(unittest.TestCase):
    def test_missing_v1_is_appended_without_duplication(self):
        cases = {
            "https://api.9li.life": "https://api.9li.life/v1",
            "https://api.9li.life/": "https://api.9li.life/v1",
            "https://api.9li.life/v1": "https://api.9li.life/v1",
            "https://api.9li.life/v1/": "https://api.9li.life/v1",
            "https://example.test/openai": "https://example.test/openai/v1",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(normalize_v1_base_url(source), expected)

    def test_resource_path_is_inserted_before_query_and_fragment(self):
        self.assertEqual(
            append_api_path("https://example.test?tenant=demo#models", "models"),
            "https://example.test/v1/models?tenant=demo#models",
        )


if __name__ == "__main__":
    unittest.main()
