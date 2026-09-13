# NewsAggregator & Processing Engine

An automated, real-time news aggregation and summarization pipeline. It continuously monitors global publishers, national news, regional categories, and all 28 Indian states, deduplicates articles across multiple news outlets, summarizes stories with AI into concise 200-word cards, and ranks them by objective importance.

---

## Key Features

1. **Automated 10-Minute Crawler (`auto_news_crawler.py`)**:
   - Polls feeds every 10 minutes in the background.
   - Strictly deduplicates by article URL so no story link is recorded twice.
   - Appends fresh articles to `news.json`.
   - Covers all 28 Indian States, 8 Indian categories, 8 global categories, and global baseline publishers (BBC, NYT, The Hindu, Times of India, etc.).

2. **Deduplication & Summarization Engine (`process_news.py`)**:
   - **Cross-Outlet Duplicate Detection**: Uses TF-IDF cosine similarity to cluster multiple outlets covering the same event into a single story.
   - **Importance Ranking ("Important-Wise")**: Automatically scores news significance based on multi-source corroboration, publisher trust tiers, impact keywords (*elections, emergency, accidents, deaths, war, budget, summit*), and recency.
   - **200-Word Factual Summaries**: Summarizes top stories using AI (Groq / Gemini / OpenAI / OpenRouter) with an automatic high-density fallback if no API key is provided.
   - **Structured Outputs**: Saves results to `summarized_news.json` and local SQLite database `news.db`.

3. **Interactive Telegram Bot (`main.py`)**:
   - Inline-keyboard menu for browsing headlines, searching keywords, or filtering by source.
   - Formatted Telegram MarkdownV2 articles with direct source links.

---

## Project Structure

```
website_scraping/
├── auto_news_crawler.py             # 10-minute automated multi-category news crawler
├── process_news.py                  # Deduplication, AI summarizer, and importance ranker
├── main.py                          # Telegram bot daemon
├── news.json                        # Raw aggregated article dataset
├── summarized_news.json             # Deduplicated, summarized & ranked news cards
├── feeds.yaml                       # Configurable RSS feed registry
├── bot/                             # Modular Telegram bot package
├── newsbot/                         # Scrapy spider package
├── tests/                           # Unit test suite
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment variables template
├── start_crawler.bat                # 1-click crawler launch
├── process_news.bat                 # 1-click summarizer & ranking launch
└── start_crawler_and_processor.bat  # 1-click launch for crawler + summarizer in sync
```

---

## Quickstart

### 1. Installation

Install dependencies using pip:

```bash
pip install -r requirements.txt
```

### 2. Configuration (Optional)

Copy `.env.example` to `.env`:

```bash
copy .env.example .env
```

You can optionally add API keys for AI summarization (e.g. `GROQ_API_KEY`, `GEMINI_API_KEY`, or `OPENAI_API_KEY`) and a `TELEGRAM_BOT_TOKEN`.
*(If no API keys are provided, the system runs with deterministic high-density factual synthesis automatically).*

### 3. Running

- **Option A: Run Crawler & Processing Engine together in sync**:
  ```bash
  start_crawler_and_processor.bat
  ```

- **Option B: Run Crawler alone (every 10 minutes)**:
  ```bash
  python auto_news_crawler.py
  ```

- **Option C: Run Deduplication & Summarization Engine**:
  ```bash
  # Summarize top 20 stories once
  python process_news.py --limit 20

  # Or run continuously every 10 minutes
  python process_news.py --watch
  ```

- **Option D: Run Telegram Bot**:
  ```bash
  python main.py
  ```

---

## Running Tests

Run the test suite with pytest:

```bash
pytest
```
