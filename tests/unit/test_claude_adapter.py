import unittest

from integrations.hooks.contract import HookIntent
from integrations.hooks.hosts.claude.adapter import adapt_event


class ClaudeAdapterTest(unittest.TestCase):
    def test_maps_supported_events_without_runtime_behavior(self):
        self.assertEqual(
            adapt_event({"hook": "SessionStart"}).intent,
            HookIntent.SESSION_START,
        )
        self.assertEqual(
            adapt_event(
                {"hook": "PostToolUse", "tool": "Edit", "paths": ["a.py"]}
            ).changed_paths,
            ("a.py",),
        )
        self.assertEqual(
            adapt_event({"hook": "Stop", "paths": ["a.py"]}).intent,
            HookIntent.SESSION_STOP,
        )

    def test_ignores_unknown_or_non_edit_tool_events(self):
        self.assertIsNone(adapt_event({"hook": "PostToolUse", "tool": "Read"}))
        self.assertIsNone(adapt_event({"hook": "Other"}))
        self.assertIsNone(adapt_event(None))


if __name__ == "__main__":
    unittest.main()
