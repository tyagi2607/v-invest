from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_POST_CHARS = 260

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\U00002700-\U000027BF"
    "]+",
    flags=re.UNICODE,
)

HYPE_TERMS = (
    "to the moon",
    "rocket",
    "gem",
    "100x",
    "massive upside",
    "next big thing",
    "buy now",
    "don't miss",
    "must buy",
    "get rich",
)


@dataclass
class QueueItem:
    ticker: str
    company_name: str


class TickerQueue:
    def __init__(self, csv_path: str | Path = "tickers.csv") -> None:
        self.csv_path = Path(csv_path)

    def _read_rows(self) -> list[dict[str, str]]:
        if not self.csv_path.exists():
            return []
        with self.csv_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return [
                {
                    "ticker": (row.get("ticker") or "").strip(),
                    "company_name": (row.get("company_name") or "").strip(),
                    "processed": (row.get("processed") or "").strip(),
                }
                for row in reader
            ]

    def _write_rows(self, rows: list[dict[str, str]]) -> None:
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        with self.csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["ticker", "company_name", "processed"]
            )
            writer.writeheader()
            writer.writerows(rows)

    def next_unprocessed(self) -> QueueItem | None:
        rows = self._read_rows()
        for row in rows:
            if row["ticker"] and row["processed"].lower() != "true":
                company_name = row["company_name"] or row["ticker"]
                return QueueItem(ticker=row["ticker"], company_name=company_name)
        return None

    def mark_processed(self, ticker: str) -> None:
        rows = self._read_rows()
        changed = False
        for row in rows:
            if row["ticker"].upper() == ticker.upper() and row["processed"].lower() != "true":
                row["processed"] = "true"
                changed = True
        if changed:
            self._write_rows(rows)


class FundamentalsFetcher:
    def fetch(self, ticker: str) -> dict[str, Any]:
        import yfinance as yf

        info = yf.Ticker(ticker).info or {}
        return {
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "price_to_book": info.get("priceToBook"),
            "free_cashflow": info.get("freeCashflow"),
            "operating_margin": info.get("operatingMargins"),
            "debt_to_equity": info.get("debtToEquity"),
        }


class CopilotContentGenerator:
    def __init__(
        self,
        base_url: str = "http://localhost:8080/v1",
        model: str = "gpt-4.1-mini",
        client: Any | None = None,
    ) -> None:
        self.base_url = base_url
        self.model = model
        self.client = client

    def _get_client(self) -> Any:
        if self.client is not None:
            return self.client

        from openai import OpenAI

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=os.getenv("OPENAI_API_KEY", "copilot-session"),
        )
        return self.client

    def _prompt(self, ticker: str, company_name: str, fundamentals: dict[str, Any]) -> str:
        return (
            "Write ONE X post for weekly value-investing analysis on Canadian small-caps. "
            "Use only fundamental safety and efficiency framing inspired by Graham/Buffett. "
            "No emojis, no hype, no promotional language, no momentum indicators. "
            "Objective, analytical tone. Max 260 characters. "
            f"Ticker: {ticker}. Company: {company_name}. Fundamentals: {json.dumps(fundamentals, default=str)}"
        )

    def generate(self, ticker: str, company_name: str, fundamentals: dict[str, Any]) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a strict financial analyst."},
                {"role": "user", "content": self._prompt(ticker, company_name, fundamentals)},
            ],
            temperature=0.2,
        )
        raw = response.choices[0].message.content or ""
        cleaned = sanitize_post(raw)
        return cleaned or fallback_post(ticker, company_name, fundamentals)


def sanitize_post(text: str) -> str:
    cleaned = EMOJI_PATTERN.sub("", text)

    for term in HYPE_TERMS:
        cleaned = re.sub(re.escape(term), "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if len(cleaned) <= MAX_POST_CHARS:
        return cleaned

    trimmed = cleaned[:MAX_POST_CHARS]
    if " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0]
    return trimmed.strip()


def fallback_post(ticker: str, company_name: str, fundamentals: dict[str, Any]) -> str:
    pe = fundamentals.get("pe_ratio")
    pb = fundamentals.get("price_to_book")
    fcf = fundamentals.get("free_cashflow")
    debt = fundamentals.get("debt_to_equity")

    base = (
        f"{company_name} ({ticker}): valuation screen shows "
        f"P/E {pe}, P/B {pb}, FCF {fcf}, debt/equity {debt}. "
        "Focus remains balance-sheet safety, cash-flow resilience, and operational discipline over narrative-driven price action."
    )
    return sanitize_post(base)


class WeeklyPipeline:
    def __init__(
        self,
        queue: TickerQueue,
        fetcher: FundamentalsFetcher,
        generator: CopilotContentGenerator,
    ) -> None:
        self.queue = queue
        self.fetcher = fetcher
        self.generator = generator

    def run_next(self) -> str | None:
        item = self.queue.next_unprocessed()
        if item is None:
            return None

        fundamentals = self.fetcher.fetch(item.ticker)
        post = self.generator.generate(item.ticker, item.company_name, fundamentals)
        self.queue.mark_processed(item.ticker)
        return post
