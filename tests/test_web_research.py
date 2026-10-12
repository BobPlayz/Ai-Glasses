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
        search.news.return_value = [
            {"title": "Example report", "url": "https://example.com/report", "body": "A useful snippet.", "date": "today", "source": "Example"},
            {"title": "Duplicate", "url": "https://example.com/report", "body": "Duplicate result."},
            {"title": "Unsafe scheme", "url": "javascript:alert(1)", "body": "Ignore this."},
            {"title": "India News Today, Breaking News in India", "url": "https://example.com/india", "body": "Read the latest and breaking news"},
        ]
        search.text.return_value = []

        result = search_web("latest news today", max_results=1)

        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["url"], "https://example.com/report")
        self.assertEqual(result["results"][0]["snippet"], "A useful snippet.")
        search.news.assert_called_once_with("latest news today", max_results=5, timelimit="w")

    @patch("laptop.assistant.web_research.DDGS")
    def test_india_query_uses_multiple_article_oriented_searches(self, ddgs_type):
        search = ddgs_type.return_value.__enter__.return_value
        search.news.side_effect = [
            [{"title": "Government faces scrutiny after inquiry", "url": "https://example.com/story-1", "body": "A reported development."}],
            [{"title": "Court hears petition over public policy", "url": "https://example.com/story-2", "body": "A separate reported development."}],
        ]
        result = search_web("What happened in India over the past few days?", max_results=5)
        self.assertGreaterEqual(search.news.call_count, 2)
        self.assertEqual(len(result["results"]), 2)

    def test_generic_news_homepage_blurbs_are_rejected(self):
        from laptop.assistant.web_research import _result_to_record
        self.assertIsNone(_result_to_record({
            "title": "India News Today, Breaking News in India",
            "url": "https://example.com/india",
            "body": "Read the latest and breaking news from India.",
        }))

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
