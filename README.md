<a id="readme-top"></a>

# Art Competition Finder

An automated tool that searches for art competitions, filters out expired or irrelevant pages, and uses a local LLM to extract useful details such as deadlines, eligibility, entry fees, and accepted mediums.

## Table of Contents

- [About The Project](#about-the-project)
- [Built With](#built-with)
- [Getting Started](#getting-started)
- [Usage](#usage)

## About The Project

Searching for art competitions manually is repetitive and time-consuming. This project automates the process:

**Search → Filter → Scrape → Extract → Deduplicate**

The system first finds potential competitions through Google Search, removes pages that do not have relevant future deadlines, and then uses a locally hosted LLM to extract structured information.

### Built With

- Python
- asyncio
- Serper API
- crawl4ai / Playwright
- Ollama / Qwen 2.5 3B
- Instructor
- Pydantic
- dateparser

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Getting Started

### Prerequisites

- Python 3.10+
- Ollama
- A Serper API key

Pull the model used by the project:

```bash
ollama pull qwen2.5:3b
```

### Installation

1. Clone the repo
   ```bash
   git clone https://github.com/yourusername/your-repo-name.git
   cd your-repo-name
   ```
2. Install the Python dependencies
   ```bash
   pip install -r requirements.txt
   ```
3. Install the browser crawl4ai needs
   ```bash
   playwright install chromium
   ```
4. Set up your environment file
   ```bash
   cp .env.example .env
   ```
   Then open `.env` and add your own key:
   ```
   SERPER_API_KEY=your_actual_key_here
   ```

**Note:** `OLLAMA_BASE_URL` in `scraper.py` is set to a gateway IP from this project's original dev setup (a Docker container on WSL2, talking to Ollama on Windows). If you're running everything on one machine, change it to `http://localhost:11434/v1`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Usage

Run the whole pipeline with:

```bash
python main.py
```

This searches, filters, scrapes, and extracts, then saves everything to `results.json` in the project root.

Want to see what it produces without running it yourself? Check [`results.json`](./results.json) for a real output from a past run.

<p align="right">(<a href="#readme-top">back to top</a>)</p>
