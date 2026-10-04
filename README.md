# Automated Web Data Acquisition and Preprocessing System

This project is a moderate-scale web data acquisition and preprocessing system for LLM training, built with FastAPI, PostgreSQL, HTTPX, BeautifulSoup, Playwright, and PyMuPDF.

## Architecture Decisions

*   **Database Driver:** The system utilizes an **asynchronous database driver (`asyncpg` with SQLAlchemy)** to fully leverage the asynchronous capabilities of FastAPI, HTTPX, and Playwright. This ensures non-blocking I/O operations and higher concurrency when interacting with PostgreSQL.
*   **Layered Modular Design:** The codebase is split into presentation, application, processing, and data layers to maintain a clear separation of concerns.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure your environment variables (see `project/config/settings.py`).
3. Run the application:
   ```bash
   uvicorn project.app:app --reload
   ```
