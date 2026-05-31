import csv
import tempfile
import unittest
from pathlib import Path

from v_invest_pipeline import MAX_POST_CHARS, TickerQueue, fallback_post, sanitize_post


class SanitizePostTests(unittest.TestCase):
    def test_removes_emoji_hype_and_limits_length(self) -> None:
        text = (
            "TSXV idea 🚀 is the next big thing. Don't miss this rocket. "
            + "a" * 400
        )
        cleaned = sanitize_post(text)

        self.assertLessEqual(len(cleaned), MAX_POST_CHARS)
        self.assertNotIn("🚀", cleaned)
        self.assertNotIn("next big thing", cleaned.lower())
        self.assertNotIn("rocket", cleaned.lower())

    def test_fallback_post_is_always_within_limit(self) -> None:
        post = fallback_post(
            ticker="ABC.V",
            company_name="Example Minerals Inc.",
            fundamentals={
                "pe_ratio": 8.2,
                "price_to_book": 0.9,
                "free_cashflow": 1_250_000,
                "debt_to_equity": 0.25,
            },
        )
        self.assertLessEqual(len(post), MAX_POST_CHARS)


class TickerQueueTests(unittest.TestCase):
    def test_next_unprocessed_and_mark_processed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "tickers.csv"
            with queue_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=["ticker", "company_name", "processed"]
                )
                writer.writeheader()
                writer.writerow(
                    {"ticker": "AAA.V", "company_name": "Alpha", "processed": "true"}
                )
                writer.writerow(
                    {"ticker": "BBB.TO", "company_name": "Beta", "processed": "false"}
                )

            queue = TickerQueue(queue_path)
            item = queue.next_unprocessed()

            self.assertIsNotNone(item)
            self.assertEqual(item.ticker, "BBB.TO")
            self.assertEqual(item.company_name, "Beta")
            queue.mark_processed("BBB.TO")

            with queue_path.open("r", newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[1]["processed"], "true")

    def test_next_unprocessed_returns_none_when_queue_is_done(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "tickers.csv"
            with queue_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=["ticker", "company_name", "processed"]
                )
                writer.writeheader()
                writer.writerow(
                    {"ticker": "AAA.V", "company_name": "Alpha", "processed": "true"}
                )

            queue = TickerQueue(queue_path)
            self.assertIsNone(queue.next_unprocessed())


if __name__ == "__main__":
    unittest.main()
