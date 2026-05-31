# v-invest

Modular Python pipeline for weekly value-investing X posts on Canadian TSX/TSXV small-caps.

## Architecture

- **Queue:** local `tickers.csv` with columns `ticker,company_name,processed`
- **Fundamentals:** fetched via `yfinance`
- **AI generation:** OpenAI-compatible client routed through local Copilot proxy (`http://localhost:8080/v1`)

## Output policy

Generated posts are enforced to:
- stay at **260 characters max**
- remove emojis
- remove hype/promotional phrasing
- keep an objective, fundamental-analysis tone focused on valuation, balance-sheet safety, cash flow, and operational efficiency

## Quick start

```python
from v_invest_pipeline import (
    CopilotContentGenerator,
    FundamentalsFetcher,
    TickerQueue,
    WeeklyPipeline,
)

pipeline = WeeklyPipeline(
    queue=TickerQueue("tickers.csv"),
    fetcher=FundamentalsFetcher(),
    generator=CopilotContentGenerator(),
)

post = pipeline.run_next()
print(post)
```
