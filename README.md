<a id="readme-top"></a>

# Art Competition Finder

An automated tool that searches for art competitions, filters out expired or irrelevant pages, and uses a local LLM to extract useful details such as deadlines, eligibility, entry fees, and accepted mediums.

## Table of Contents

- [About The Project](#about-the-project)
- [Built With](#built-with)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

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

## Getting Started

### Prerequisites

- Python 3.10+
- Ollama
- A Serper API key

Pull the model used by the project:

```bash
ollama pull qwen2.5:3b