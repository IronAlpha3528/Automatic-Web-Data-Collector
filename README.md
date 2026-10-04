# Automated Web Data Acquisition and Preprocessing System for LLM Training

An enterprise-grade, high-throughput, fault-tolerant web data crawler and dataset preprocessor designed to acquire, clean, normalize, and serialize structured multimodal web content (HTML pages, tables, images, and PDF documents) for Large Language Model (LLM) training.

---

## 📖 Table of Contents

- [Overview & Objectives](#overview--objectives)
- [Key Features](#key-features)
- [Architecture & Design Principles](#architecture--design-principles)
- [End-to-End Processing Pipeline](#end-to-end-processing-pipeline)
- [Project Directory Structure](#project-directory-structure)
- [Setup & Installation](#setup--installation)
  - [Prerequisites](#prerequisites)
  - [Installation Steps](#installation-steps)
  - [Environment Configuration](#environment-configuration)
  - [Playwright Browser Setup](#playwright-browser-setup)
- [How It Works (System Operation)](#how-it-works-system-operation)
  - [1. Web UI Dashboard](#1-web-ui-dashboard)
  - [2. REST API Workflows](#2-rest-api-workflows)
- [Configuration Reference](#configuration-reference)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Output Dataset Format (Appendix B)](#output-dataset-format-appendix-b)

---

## Overview & Objectives

High-quality LLM pre-training and fine-tuning require clean, diverse, and well-structured text datasets. Raw web scraping often suffers from network fragility, JavaScript rendering overhead, malformed markup, boilerplate noise, duplicate URLs, and catastrophic failure cascades.

This system addresses these challenges with:
- **Resilient BFS link traversal** with depth restrictions and deterministic URL deduplication.
- **Dual-mode retrieval:** High-speed asynchronous HTTPX requests for static content with automatic fallback to headless Chromium (Playwright) for JavaScript-rendered Single Page Applications (SPAs).
- **Multi-format structural parsing:** Extracts hierarchical headings (`h1`–`h6`), paragraphs, tabular matrices, links, images, and embedded PDF documents (via PyMuPDF).
- **Conservative text normalization:** Strips boilerplate and normalizes whitespace/Unicode without aggressive destructive stemming or semantic corruption.
- **SHA-256 metadata hashing:** Deterministic content fingerprinting for lineage tracking.
- **Asynchronous PostgreSQL persistence:** Non-blocking database operations with atomic transaction boundaries and operational counter tracking.
- **Atomic JSON dataset exports:** Clean JSON output conforming strictly to the LLM ingestion schema.

---

## Key Features

- **Decoupled Layered Architecture:** Strict Clean Architecture (Presentation $\rightarrow$ Application $\rightarrow$ Processing $\rightarrow$ Infrastructure) using typed Pydantic contracts and Python `typing.Protocol` interfaces.
- **Golden Failure Rule (URL-Level Fault Isolation):** Failures on individual URLs (timeouts, 404s, malformed HTML, failed downloads) are categorized and logged without terminating the crawl job.
- **Intelligent SPA Detection:** Dynamically detects empty DOM containers, `<noscript>` tags, or minimal body text to trigger headless browser rendering only when necessary.
- **Adaptive Rate Limiting & Retry Engine:** Configurable per-domain pacing and exponential backoff retry policies for transient network errors (HTTP 429, 5xx, timeouts).
- **Direct Media Streaming:** Downloads images and PDFs to organized disk directories (`output/jobs/{job_id}/images/` and `pdfs/`) while saving lightweight metadata and SHA-256 checksums in PostgreSQL.
- **Interactive Presentation Dashboard:** Responsive Jinja2 web interface featuring live polling progress bars, job creation forms, categorized error tables, and dataset download buttons.

---

## Architecture & Design Principles

```text
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                       │
│  FastAPI REST API (/api/jobs)  +  HTML Web Dashboard (/)    │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    APPLICATION LAYER                        │
│  JobManager  │  CrawlConfig  │  State Machine Coordination  │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                     PROCESSING LAYER                        │
│  URLManager    │  Crawler (BFS) │  HTTPXRetriever           │
│  Playwright    │  DocumentParser│  ContentExtractor         │
│  Preprocessor  │  MediaDownloader│  JSONExporter            │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                   INFRASTRUCTURE LAYER                      │
│  PostgreSQL (asyncpg)  │  Filesystem Media  │  Async Engine │
└─────────────────────────────────────────────────────────────┘
```

### Architectural Principles:
1. **Low Coupling & Dependency Inversion:** Service consumers depend on abstract protocols defined in `project/interfaces/` (`Storage`, `Retriever`, `Renderer`, `Parser`, `Extractor`, `MediaDownloader`), not concrete implementations.
2. **PostgreSQL as Source of Truth:** Crawl frontiers, URL lineage, operational counters, and error taxonomies are tracked in PostgreSQL.
3. **Filesystem for Binary Media:** Binary blobs never inflate the database; they are streamed directly to disk, keeping the database fast and lean.

---

## End-to-End Processing Pipeline

Each URL enqueued in the BFS frontier traverses a deterministic 16-step processing pipeline:

```text
1. Seed URL Validation & Normalization
        ↓
2. In-Memory BFS Frontier Queue (URLManager)
        ↓
3. Domain Rate Limiter & Concurrency Semaphore Check
        ↓
4. Primary Static HTTP Retrieval (HTTPX async)
        ↓
5. Content Sufficiency Check (needs_javascript_rendering)
        ├── If insufficient → Fallback to Playwright Headless Browser
        └── If sufficient   → Proceed with HTTP response
        ↓
6. Structural Document Parsing (BeautifulSoup4 + lxml / PyMuPDF)
        ↓
7. Content & Boilerplate Extraction (Headings, Paragraphs, Tables, Media Links)
        ↓
8. Conservative Text Normalization (NFKC Unicode, Whitespace & Line Standardisation)
        ↓
9. SHA-256 Content Hash Calculation (Page Metadata)
        ↓
10. Media Streaming (Images & PDF documents downloaded to disk)
        ↓
11. Safe PostgreSQL Persistence (Page, Media metadata, URL status = SUCCESS)
        ↓
12. Child Link Discovery, Normalization & Depth Check
        ↓
13. URL Checkpointing & Operational Counter Increments
        ↓
14. Atomic Appendix B JSON Dataset Export
```

---

## Project Directory Structure

```text
SE_PROJECT/
├── output/                        # Root output directory for media and JSON exports
│   └── jobs/{job_id}/             # Per-job directories (images, pdfs, json)
├── project/
│   ├── config/
│   │   ├── database.py            # Async engine, sessionmaker & init_db
│   │   └── settings.py            # Pydantic BaseSettings & CrawlConfig
│   ├── interfaces/                # Abstract Protocol contracts
│   │   ├── retriever.py
│   │   ├── renderer.py
│   │   ├── parser.py
│   │   ├── extractor.py
│   │   ├── storage.py
│   │   └── media.py
│   ├── models/                    # SQLAlchemy ORM database models
│   │   ├── job.py                 # ScrapingJob & JobStatus enum
│   │   ├── url_record.py          # URLRecord & URLStatus enum
│   │   ├── page.py                # Page entity (content, hash, extractions)
│   │   ├── media.py               # Media entity (type, size, path)
│   │   └── error_log.py           # ErrorLog entity (category, attempt, trace)
│   ├── routes/                    # FastAPI endpoints & UI controllers
│   │   ├── dashboard.py           # HTML Presentation views & form handlers
│   │   ├── jobs.py                # REST API for job management & execution
│   │   ├── results.py             # Results inspection & export downloads
│   │   └── errors.py              # Error drilldown API
│   ├── schemas/                   # Pydantic validation models / DTOs
│   │   ├── job_schema.py
│   │   ├── url_schema.py
│   │   ├── page_schema.py         # Appendix B compliant document schema
│   │   └── result_schema.py
│   ├── services/                  # Core domain and processing services
│   │   ├── crawler.py             # BFS traversal engine & pipeline coordinator
│   │   ├── job_manager.py         # Job orchestrator & task lifecycle coordinator
│   │   ├── url_manager.py         # Frontier queue & URL deduplication
│   │   ├── retriever.py           # HTTPX client with retry integration
│   │   ├── renderer.py            # Playwright headless browser fallback
│   │   ├── parser.py              # HTML & PDF document parser
│   │   ├── extractor.py           # Content & structural table/link extractor
│   │   ├── preprocessor.py        # Normalizer & SHA-256 hash generator
│   │   ├── storage.py             # PostgresStorage implementing Storage protocol
│   │   ├── media_downloader.py    # Binary media streaming service
│   │   ├── error_manager.py       # Error classification & fault isolation
│   │   └── json_exporter.py       # Atomic Appendix B JSON serializer
│   ├── static/                    # Dashboard static assets
│   │   ├── css/styles.css         # Modern responsive dark-mode styling
│   │   └── js/monitor.js          # Polling status & live progress bar script
│   ├── templates/                 # Jinja2 HTML templates
│   │   ├── base.html              # Shell layout with top navbar
│   │   ├── dashboard.html         # Job listing & status overview
│   │   ├── create_job.html        # Form to configure and submit new crawls
│   │   ├── job_monitor.html       # Real-time progress monitor
│   │   ├── results.html           # Parsed documents & content preview table
│   │   └── errors.html            # Classified error logs table
│   ├── tests/                     # 72 automated tests (Unit, Integration, E2E)
│   │   ├── unit/                  # Unit tests for all phases
│   │   ├── integration/           # Multi-service pipeline and system E2E tests
│   │   ├── negative/              # Negative matrix & resilience test suite
│   │   └── performance/           # 50-URL benchmark & throughput suite
│   ├── utils/                     # Cross-cutting utilities
│   │   ├── content_detection.py   # SPA & sufficiency evaluation
│   │   ├── exceptions.py          # Domain exception hierarchy
│   │   ├── hashing.py             # Deterministic SHA-256 hashing
│   │   ├── logging.py             # Centralized structured logger
│   │   ├── rate_limiter.py        # Per-domain async rate limiter
│   │   ├── retry.py               # Exponential backoff retry handler
│   │   └── url_normalizer.py      # Deterministic URL normalizer
│   └── app.py                     # FastAPI application factory & lifespan
├── .env.example                   # Environment configuration template
├── implementation_plan.md         # Authoritative technical implementation blueprint
├── requirements.txt               # Python package dependencies
└── README.md                      # Project documentation
```

---

## Setup & Installation

### Prerequisites

- **Python:** Python 3.11, 3.12, 3.13, or 3.14
- **Database:** PostgreSQL 14+ with an active database (or a cloud-hosted Postgres instance)
- **OS:** Linux, macOS, or Windows

### Installation Steps

1. **Clone the repository and enter the directory:**
   ```bash
   cd SE_PROJECT
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # On Windows (PowerShell):
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # On Linux/macOS:
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Python package dependencies:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Install Playwright browser binaries (for JavaScript fallback rendering):**
   ```bash
   playwright install chromium
   ```

### Environment Configuration

Copy the sample environment file to create your active configuration:

```bash
# On Windows (PowerShell):
Copy-Item .env.example .env

# On Linux/macOS:
cp .env.example .env
```

Edit `.env` to configure your PostgreSQL credentials and settings:

```dotenv
# Application Environment
APP_ENV=development

# Database Connection (AsyncPG format)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/web_data_acq

# Output Directory for downloaded images, PDFs, and exported JSON datasets
OUTPUT_DIR=./output

# Logging Level
LOG_LEVEL=INFO

# Default Crawl Parameters
DEFAULT_CRAWL_DEPTH=2
DEFAULT_RECURSIVE=true
DEFAULT_JAVASCRIPT_FALLBACK=true
DEFAULT_ROBOTS_MODE=respect
DEFAULT_TIMEOUT_SECONDS=15
DEFAULT_MAX_RETRIES=3
DEFAULT_DOMAIN_RATE_LIMIT=2.0
DEFAULT_MAX_CONCURRENCY=3
```

> **Note:** The application automatically converts standard `postgresql://` and `postgres://` URLs to `postgresql+asyncpg://` so standard database connection strings work out of the box.

---

## How It Works (System Operation)

### Starting the Server

Run the development server using Uvicorn:

```bash
uvicorn project.app:app --host 127.0.0.1 --port 8000 --reload
```

When the application boots:
- It connects to PostgreSQL and automatically verifies/creates all required tables (`scraping_jobs`, `url_records`, `pages`, `media`, `error_logs`).
- The Web Dashboard is available at: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- The interactive OpenAPI/Swagger documentation is available at: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

### 1. Web UI Dashboard

The built-in web interface provides an intuitive control center for managing scraping workflows:

1. **Dashboard Overview (`/`):**
   - Displays all recent scraping jobs, operational counters, status badges (`CREATED`, `RUNNING`, `COMPLETED`, `COMPLETED_WITH_ERRORS`, `FAILED`), and quick-action buttons.
2. **Create Scraping Job (`/jobs/new`):**
   - Enter seed URLs (one per line).
   - Configure traversal depth, recursiveness, Playwright JS fallback, per-request timeouts, domain rate pacing, and maximum concurrency.
   - Click **"Validate & Start Job"** to create and immediately launch the background crawl.
3. **Live Job Monitor (`/jobs/{job_id}/monitor`):**
   - Real-time animated progress bar polling the operational counters.
   - Shows live tallies for Total, Processed, Successful, and Failed URLs.
4. **Results Viewer (`/jobs/{job_id}/results-view`):**
   - Inspects extracted page titles, structural counts (headings, paragraphs, tables, links), SHA-256 hashes, and text previews.
   - Direct button to **"Download JSON Dataset"**.
5. **Categorized Error Logs (`/jobs/{job_id}/errors-view`):**
   - Inspects failed URLs, taxonomy classifications (`NETWORK_ERROR`, `HTTP_ERROR`, `TIMEOUT_ERROR`), retry attempts, and detailed error messages.

---

### 2. REST API Workflows

All operational capabilities are exposed via clean REST endpoints under `/api/jobs`:

#### Create a Scraping Job
```bash
curl -X POST "http://127.0.0.1:8000/api/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "seed_urls": ["https://en.wikipedia.org/wiki/Artificial_intelligence"],
    "crawl_depth": 1,
    "recursive": true,
    "javascript_fallback": true,
    "timeout_seconds": 15,
    "max_retries": 3,
    "domain_rate_limit": 2.0,
    "max_concurrency": 3
  }'
```
*Response (HTTP 201 Created):*
```json
{
  "job_id": "f8a7e029-6725-4c01-bf5c-d2c6cf15e219",
  "status": "CREATED",
  "crawl_depth": 1,
  "recursive": true,
  "total_urls": 1,
  "processed_urls": 0,
  "successful_urls": 0,
  "failed_urls": 0,
  "skipped_urls": 0
}
```

#### Start Job Execution
```bash
curl -X POST "http://127.0.0.1:8000/api/jobs/f8a7e029-6725-4c01-bf5c-d2c6cf15e219/start"
```

#### Poll Job Status & Counters
```bash
curl -X GET "http://127.0.0.1:8000/api/jobs/f8a7e029-6725-4c01-bf5c-d2c6cf15e219"
```

#### Cancel an In-Flight Job
```bash
curl -X POST "http://127.0.0.1:8000/api/jobs/f8a7e029-6725-4c01-bf5c-d2c6cf15e219/cancel"
```

#### Inspect Extracted Results
```bash
curl -X GET "http://127.0.0.1:8000/api/jobs/f8a7e029-6725-4c01-bf5c-d2c6cf15e219/results"
```

#### Download JSON Dataset File
```bash
curl -X GET "http://127.0.0.1:8000/api/jobs/f8a7e029-6725-4c01-bf5c-d2c6cf15e219/export" -o dataset.json
```

#### Inspect Classified Errors
```bash
curl -X GET "http://127.0.0.1:8000/api/jobs/f8a7e029-6725-4c01-bf5c-d2c6cf15e219/errors"
```

---

## Configuration Reference

| Parameter | Type | Default | Description |
|:---|:---:|:---:|:---|
| `crawl_depth` | `int` | `2` | Maximum BFS link traversal depth (`0` = seed URLs only). |
| `recursive` | `bool` | `true` | When `true`, links discovered on crawled pages are enqueued. |
| `javascript_fallback` | `bool` | `true` | Enables Playwright headless browser fallback for dynamic SPAs. |
| `robots_mode` | `string` | `"respect"` | Robots compliance mode (`"respect"` or `"ignore"`). |
| `timeout_seconds` | `int` | `15` | Per-request HTTP timeout in seconds (bounded 1–120s). |
| `max_retries` | `int` | `3` | Maximum retry attempts with exponential backoff for transient errors. |
| `domain_rate_limit` | `float` | `2.0` | Maximum requests per second per domain (prevents DDoS/rate bans). |
| `max_concurrency` | `int` | `3` | Maximum concurrent requests allowed across the crawl. |
| `output_dir` | `string` | `"./output"` | Filesystem directory for media files and exported JSON datasets. |

---

## Testing & Quality Assurance

The codebase includes an automated test suite comprising **72 tests** covering every phase of the implementation plan:

```bash
# Run the entire test suite:
pytest -v

# Run with concise traceback:
pytest -v --tb=short

# Run specific test suites:
pytest project/tests/unit/test_foundation.py -v
pytest project/tests/unit/test_url_system.py -v
pytest project/tests/unit/test_retrieval_and_services.py -v
pytest project/tests/unit/test_persistence.py -v
pytest project/tests/unit/test_orchestration.py -v
pytest project/tests/unit/test_api_and_ui.py -v
pytest project/tests/negative/test_negative_matrix.py -v
pytest project/tests/performance/test_benchmark_suite.py -v
pytest project/tests/integration/test_pipeline_integration.py -v
pytest project/tests/integration/test_system_e2e.py -v
```

### Test Coverage Breakdown:
- **Foundation Suite (14 tests):** Settings normalization, ORM schema compilation, DDL constraints, Pydantic contracts, and Protocol definitions.
- **URL System Suite (12 tests):** Deterministic normalization, port stripping, query sorting, path cleanup, and BFS queue behavior.
- **Retrieval & Services Suite (18 tests):** Retry logic, rate limiter pacing, status classification, content sufficiency detection, BS4/PyMuPDF parsing, and SHA-256 hashing.
- **Persistence Suite (6 tests):** Error taxonomy classification, Golden Failure Rule verification, media extension resolution, and storage protocol adherence.
- **Orchestration Suite (4 tests):** Crawler 16-step execution flow, URL failure isolation, and JobManager state transitions.
- **API & UI Suite (7 tests):** FastAPI route validation, dashboard template rendering, job creation, monitor endpoints, and job cancellation.
- **Negative Test Matrix (8 tests):** Invalid URL schemes, bounded timeout exhaustions, HTTP 404/500 resilience, malformed HTML recovery, empty HTML responses, corrupted PDF handling, and invalid filesystem paths.
- **Performance Benchmark (1 test, 50 URLs):** Automated stress testing across 50 simulated URLs validating fault isolation, memory stability, and throughput.
- **Pipeline Integration (1 test):** Full-cycle integration from raw HTTP response through BS4 parser $\rightarrow$ extractor $\rightarrow$ preprocessor $\rightarrow$ atomic JSON exporter.
- **System Acceptance (1 test):** End-to-end multi-tier test executing job creation $\rightarrow$ multi-page recursive BFS crawl $\rightarrow$ DB persistence $\rightarrow$ JSON export $\rightarrow$ REST API verification $\rightarrow$ Web dashboard presentation.

---

## Output Dataset Format (Appendix B)

Exported JSON files conform strictly to the approved LLM training dataset schema:

```json
[
  {
    "job_id": "f8a7e029-6725-4c01-bf5c-d2c6cf15e219",
    "url": "https://example.com/article/deep-learning",
    "title": "Deep Learning Fundamentals",
    "headings": [
      "Introduction",
      "Neural Network Architecture",
      "Backpropagation"
    ],
    "paragraphs": [
      "Deep learning is a subset of machine learning based on artificial neural networks...",
      "Training involves forward propagation, loss calculation, and gradient descent..."
    ],
    "content": "Deep learning is a subset of machine learning based on artificial neural networks...\n\nTraining involves forward propagation, loss calculation, and gradient descent...",
    "tables": [
      [
        ["Layer", "Activation", "Parameters"],
        ["Dense_1", "ReLU", "128"],
        ["Output", "Softmax", "10"]
      ]
    ],
    "links": [
      {
        "url": "https://example.com/article/backpropagation",
        "text": "Learn more about backpropagation"
      }
    ],
    "images": [
      {
        "url": "https://example.com/images/nn_diagram.png",
        "media_type": "image",
        "local_path": "jobs/f8a7e029-6725-4c01-bf5c-d2c6cf15e219/images/a1b2c3d4e5f6.png",
        "status": "downloaded",
        "file_size": 245890
      }
    ],
    "documents": [
      {
        "url": "https://example.com/docs/paper.pdf",
        "media_type": "pdf",
        "local_path": "jobs/f8a7e029-6725-4c01-bf5c-d2c6cf15e219/pdfs/7a8b9c0d1e2f.pdf",
        "status": "downloaded",
        "file_size": 1542300
      }
    ],
    "metadata": {
      "timestamp": "2026-10-05T00:15:30.123456+00:00",
      "crawl_depth": 1,
      "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "status": "success"
    }
  }
]
```

---

## License

This project is developed as part of the Software Engineering Data Acquisition Curriculum for LLM Training and is distributed under the MIT License.
