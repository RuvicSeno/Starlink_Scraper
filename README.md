# 🛰️ Starlink Usage Scraper & Dashboard

A Python-based web application that scrapes your Starlink account usage data and presents it in a modern, interactive dashboard inspired by the Starlink interface design.

![Python](https://img.shields.io/badge/Python-3.10+-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green) ![Playwright](https://img.shields.io/badge/Playwright-1.48+-purple)

## Features

- **Automated Scraping** — Uses Playwright to scrape usage data from your Starlink account
- **Network Interception** — Captures internal API responses (more resilient than DOM scraping)
- **Interactive Dashboard** — Dark-themed UI with real-time charts and data tables
- **Daily & Monthly Analytics** — Line charts, bar charts, and summary statistics
- **Searchable Data Table** — Sort, search, and paginate through all usage records
- **CSV Export** — Download all scraped data as a formatted CSV file
- **Session Persistence** — Log in once, sessions are saved for subsequent runs
- **Multi-Month Scraping** — Automatically navigates through all available months

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python, FastAPI, Uvicorn |
| Scraping | Playwright (Chromium) |
| Database | SQLite (via aiosqlite) |
| Frontend | HTML5, CSS3, JavaScript |
| Charts | Chart.js |

## Project Structure

```
Starlink_Scraper/
├── backend/              # FastAPI application
│   ├── app.py            # App entry point & static serving
│   ├── config.py         # Environment settings
│   ├── database.py       # SQLite async operations
│   ├── models.py         # Pydantic data models
│   └── routes/           # API endpoints
│       ├── data.py       # Usage data & CSV export
│       └── scraper.py    # Scraper controls
├── scraper/              # Playwright scraping engine
│   ├── browser.py        # Browser lifecycle management
│   ├── auth.py           # Authentication & sessions
│   ├── extractor.py      # Data extraction & parsing
│   └── tasks.py          # Async scraping orchestrator
├── frontend/             # Web dashboard
│   ├── index.html        # Main page
│   ├── css/style.css     # Starlink-inspired dark theme
│   └── js/               # Application modules
├── data/                 # Database & sessions (gitignored)
├── .env.example          # Config template
├── requirements.txt      # Python dependencies
└── run.py                # Startup script
```

## Setup & Installation

### Prerequisites
- Python 3.10 or higher
- pip package manager

### 1. Clone & Navigate
```bash
cd Starlink_Scraper
```

### 2. Create Virtual Environment (Recommended)
```bash
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # macOS/Linux
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browser
```bash
playwright install chromium
```

### 5. Configure Environment
```bash
copy .env.example .env     # Windows
# cp .env.example .env     # macOS/Linux
```

Edit `.env` and update `STARLINK_URL` with your account's usage page URL.

### 6. Run the Application
```bash
python run.py
```

The dashboard will be available at **http://127.0.0.1:8000**

## First-Time Login

1. Click **"Start Scraping"** on the dashboard
2. A Chromium browser window will open automatically
3. Log in to your Starlink account in that window
4. Once logged in, the app will detect it and save your session
5. The browser will close and scraping begins in headless mode
6. Subsequent runs will reuse the saved session (no login needed)

> **Note:** If your session expires, the app will prompt you to log in again.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/usage/daily?month=YYYY-MM` | Daily usage (filterable) |
| `GET` | `/api/usage/monthly` | Monthly aggregated stats |
| `GET` | `/api/usage/all` | All usage records |
| `GET` | `/api/usage/summary` | Dashboard overview stats |
| `GET` | `/api/export/csv` | Download CSV file |
| `POST` | `/api/scrape/start` | Start scraping job |
| `GET` | `/api/scrape/status` | Current scrape status |
| `POST` | `/api/scrape/stop` | Cancel running scrape |
| `GET` | `/api/scrape/history` | Past scrape runs |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **"Authentication failed"** | Delete `data/session/` folder and restart scraping to re-login |
| **No data extracted** | The Starlink page structure may have changed; check logs for details |
| **Playwright not found** | Run `playwright install chromium` |
| **Port 8000 in use** | Change `PORT` in `.env` to another port |

## License

This project is for personal use only. Starlink is a trademark of SpaceX.
