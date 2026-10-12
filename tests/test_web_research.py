import unittest
from unittest.mock import patch

from laptop.assistant.web_research import (
    WebResearchError,
    format_research_context,
    search_web,
    should_research,
)


class WebResearchTests(unittest.TestCase):
    def test_current_events_questions_trigger_research(self):
        self.assertTrue(should_research("Criticize India on what has been going on these past few days"))
        self.assertTrue(should_research("What is the latest news today?"))

    def test_stable_questions_stay_local(self):
        self.assertFalse(should_research("Explain how photosynthesis works"))

    @patch("laptop.assistant.web_research.DDGS")
    def test_search_returns_deduplicated_http_sources(self, ddgs_type):
        search = ddgs_type.return_value.__enter__.return_value
        search.text.return_value = [
            {"title": "Example report", "href": "https://example.com/report", "body": "A useful snippet.", "date": "today"},
            {"title": "Duplicate", "href": "https://example.com/report", "body": "Duplicate result."},
            {"title": "Unsafe scheme", "href": "javascript:alert(1)", "body": "Ignore this."},
        ]

        result = search_web("latest news today", max_results=5)

        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["url"], "https://example.com/report")
        self.assertEqual(result["results"][0]["snippet"], "A useful snippet.")
        search.text.assert_called_once_with("latest news today", max_results=5, timelimit="w")

    def test_research_context_marks_sources_as_untrusted(self):
        context = format_research_context({
            "results": [{
                "title": "Report",
                "url": "https://example.com/report",
                "source": "example.com",
                "date": "today",
                "snippet": "Reported facts.",
            }]
        })
        self.assertIn("untrusted source excerpts", context)
        self.assertIn("https://example.com/report", context)
        self.assertIn("Reported facts.", context)

    @patch("laptop.assistant.web_research.DDGS")
    def test_search_provider_failure_is_reported_cleanly(self, ddgs_type):
        ddgs_type.side_effect = RuntimeError("network unavailable")
        with self.assertRaises(WebResearchError):
            search_web("latest news today")


if __name__ == "__main__":
    unittest.main()
