# Project A --- Technical Implementation Plan

**Version:** 1.0\
**Status:** Implementation Baseline\
**Architecture:** Modular Monolith / Layered Architecture\
**Primary Goal:** Reliable, modular, fault-tolerant web/content crawling
and structured JSON generation.

------------------------------------------------------------------------

## 1. Purpose

This document converts the approved SRS/SDD design into an
implementation-level blueprint.

The implementation MUST prioritize:

-   High cohesion
-   Low coupling
-   Explicit module boundaries
-   Typed data contracts
-   URL-level failure isolation
-   Retry and fallback mechanisms
-   Controlled resource usage
-   Deterministic processing where possible
-   Safe persistence
-   Structured logging
-   Testability
-   Extensibility without rewriting the crawler

The core processing flow is:

``` text
Seed URL
   ↓
URL Validation
   ↓
URL Normalization
   ↓
BFS Queue
   ↓
HTTP Retrieval
   ↓
JavaScript Rendering Fallback (when required)
   ↓
Parsing
   ↓
Content Extraction
   ↓
Preprocessing
   ↓
Content Hashing / Deduplication Metadata
   ↓
Persistence
   ↓
Media Download
   ↓
JSON Export
```

A failure on one webpage MUST NOT terminate the complete job unless the
failure is job-level, such as an unrecoverable persistence/system
failure.

------------------------------------------------------------------------

# 2. Architecture

Use a **layered modular monolith**.

``` text
┌───────────────────────────────────────────────┐
│                PRESENTATION                   │
│ FastAPI Routes + Web UI                       │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                APPLICATION                    │
│ JobManager / Config / Status / Results        │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│                 PROCESSING                    │
│ URL Manager / Crawler / Retriever / Parser    │
│ Extractor / Preprocessor / Media / Exporter   │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│              INFRASTRUCTURE                   │
│ PostgreSQL / Filesystem / HTTPX / Playwright  │
└───────────────────────────────────────────────┘
```

### Dependency rule

Dependencies MUST flow downward.

``` text
Routes
  ↓
Application Services
  ↓
Processing Services
  ↓
Interfaces
  ↓
Infrastructure
```

Processing modules MUST NOT directly depend on FastAPI request objects.

Processing modules SHOULD NOT directly execute arbitrary SQL.

The crawler MUST NOT know whether retrieval uses HTTPX or Playwright.

------------------------------------------------------------------------

# 3. Technology Stack

## Backend

  Component         Technology             Responsibility
  ----------------- ---------------------- -------------------------------------------
  Language          Python 3.x             Core implementation
  API               FastAPI                REST API
  Server            Uvicorn                Application server
  Validation        Pydantic               Request/config/data validation
  ORM/Data Access   SQLAlchemy             Database access
  Database          PostgreSQL             Jobs, URLs, pages, media metadata, errors
  HTTP              HTTPX                  Primary static retrieval
  Browser           Playwright             JavaScript-rendered fallback
  HTML Parsing      BeautifulSoup + lxml   HTML parsing
  PDF Processing    PyMuPDF                PDF text extraction
  Hashing           Python `hashlib`       SHA-256 content hash
  Async             `asyncio`              Bounded concurrency
  Logging           Python `logging`       Structured operational logs
  Testing           pytest                 Unit/integration/system tests

## Frontend

Use the project's selected web UI technology around the FastAPI backend.
The UI MUST remain a presentation layer and MUST NOT contain crawling
logic.

Required screens:

1.  Dashboard
2.  Create Job
3.  Job Monitor
4.  Results
5.  Errors

## Storage

``` text
PostgreSQL
    ├── Job metadata
    ├── URL records
    ├── Page metadata/content
    ├── Media metadata
    └── Error records

Filesystem
    └── output/jobs/<job_id>/
        ├── images/
        ├── pdfs/
        ├── json/
        └── logs/
```

------------------------------------------------------------------------

# 4. Project Structure

``` text
project/
│
├── app.py
│
├── config/
│   ├── settings.py
│   └── database.py
│
├── routes/
│   ├── dashboard.py
│   ├── jobs.py
│   ├── results.py
│   └── errors.py
│
├── models/
│   ├── job.py
│   ├── url_record.py
│   ├── page.py
│   ├── media.py
│   └── error_log.py
│
├── schemas/
│   ├── job_schema.py
│   ├── url_schema.py
│   ├── page_schema.py
│   └── result_schema.py
│
├── interfaces/
│   ├── retriever.py
│   ├── renderer.py
│   ├── parser.py
│   ├── extractor.py
│   ├── storage.py
│   └── media.py
│
├── services/
│   ├── job_manager.py
│   ├── config_manager.py
│   ├── status_manager.py
│   ├── result_manager.py
│   ├── url_manager.py
│   ├── crawler.py
│   ├── retriever.py
│   ├── renderer.py
│   ├── parser.py
│   ├── extractor.py
│   ├── preprocessor.py
│   ├── deduplicator.py
│   ├── media_downloader.py
│   ├── json_exporter.py
│   └── error_manager.py
│
├── utils/
│   ├── url_normalizer.py
│   ├── retry.py
│   ├── rate_limiter.py
│   ├── hashing.py
│   ├── logging.py
│   └── content_detection.py
│
├── templates/
├── static/
├── output/
└── tests/
    ├── unit/
    ├── integration/
    ├── system/
    ├── negative/
    └── performance/
```

------------------------------------------------------------------------

# 5. Core Engineering Rules

## Rule 1 --- Single Responsibility

Each module MUST have one primary reason to change.

Examples:

``` text
URLNormalizer       → URL normalization
URLManager          → URL lifecycle/queue state
Crawler             → traversal
Retriever           → retrieval
Renderer            → browser rendering
Parser              → structural parsing
Extractor           → meaningful content extraction
Preprocessor        → content cleanup
Deduplicator        → duplicate/hash logic
MediaDownloader     → media retrieval
Storage              → persistence
JSONExporter        → JSON generation
ErrorManager        → error classification/recording
```

Do not create a "God class".

------------------------------------------------------------------------

## Rule 2 --- Low Coupling

Bad:

``` python
crawler.py
    ↓
SQLAlchemy Session
    ↓
specific database tables
```

Better:

``` text
Crawler
   ↓
URLManager interface
   ↓
Storage implementation
```

The crawler MUST NOT know the database schema.

------------------------------------------------------------------------

## Rule 3 --- High Cohesion

A module MUST contain functionality that belongs together.

Bad:

``` text
retriever.py
    ├── HTTP request
    ├── HTML parsing
    ├── text cleaning
    ├── database writes
    └── JSON export
```

Good:

``` text
retriever.py → retrieval only
parser.py    → parsing only
preprocessor.py → preprocessing only
```

------------------------------------------------------------------------

## Rule 4 --- Dependency Inversion

Depend on interfaces/contracts rather than concrete infrastructure.

Example:

``` python
class Retriever(Protocol):
    async def retrieve(self, url: str) -> RetrievalResult:
        ...
```

Implementations:

``` text
HTTPXRetriever
PlaywrightRenderer
```

The crawler depends on `Retriever`, not HTTPX.

------------------------------------------------------------------------

## Rule 5 --- No Hidden Side Effects

A function SHOULD NOT unexpectedly:

-   modify unrelated database records
-   write files outside its responsibility
-   change global configuration
-   modify global state
-   start browser processes
-   silently swallow errors

------------------------------------------------------------------------

## Rule 6 --- Explicit Data Contracts

Use Pydantic models/dataclasses for pipeline boundaries.

Example:

``` python
@dataclass
class RetrievalResult:
    url: str
    status_code: int | None
    content: bytes | str | None
    content_type: str | None
    success: bool
    error: "ProcessingError | None"
```

Avoid passing uncontrolled dictionaries between modules.

------------------------------------------------------------------------

# 6. Configuration

Centralize configuration.

``` python
class CrawlConfig:
    crawl_depth: int
    recursive: bool
    javascript_fallback: bool
    robots_mode: str
    timeout_seconds: int
    max_retries: int
    domain_rate_limit: float
    max_concurrency: int
```

Default baseline:

``` text
crawl_depth          = 2
recursive            = true
javascript_fallback = true
robots_mode          = respect
timeout_seconds      = 15
max_retries          = 3
domain_rate_limit    = configurable
max_concurrency      = configurable
```

Configuration MUST be validated before the job enters RUNNING state.

Invalid configuration MUST produce a controlled validation response.

------------------------------------------------------------------------

# 7. URL Validation and Normalization

Only `http://` and `https://` are supported.

Reject:

``` text
file://
ftp://
javascript:
data:
unknown schemes
```

Normalization should:

-   lowercase scheme
-   lowercase hostname
-   remove URL fragments
-   handle default ports
-   conservatively normalize paths
-   preserve meaningful query parameters

Example:

``` text
HTTPS://Example.COM/page#section
```

becomes:

``` text
https://example.com/page
```

Do NOT blindly remove query parameters.

------------------------------------------------------------------------

# 8. URL Lifecycle

Every URL should have a controlled state.

``` text
QUEUED
  ↓
PROCESSING
  ↓
SUCCESS

or

PROCESSING
  ↓
FAILED

or

QUEUED
  ↓
SKIPPED
```

Only valid state transitions should be permitted.

Use the database as an additional source of truth.

------------------------------------------------------------------------

# 9. BFS Crawler

The crawler owns traversal only.

It MUST NOT:

-   parse HTML
-   clean text
-   download images
-   execute SQL directly
-   generate JSON

Algorithm:

``` text
Seed URLs
    ↓
Queue
    ↓
Pop URL
    ↓
Check duplicate
    ↓
Process URL
    ↓
Receive discovered links
    ↓
Normalize links
    ↓
Depth check
    ↓
Queue valid links
```

Depth rule:

``` text
if discovered_depth <= configured_max_depth:
    queue
else:
    do not queue
```

When recursion is disabled:

``` text
seed URLs → process only
```

No newly discovered links should be queued.

------------------------------------------------------------------------

# 10. Retrieval Architecture

Primary:

``` text
HTTPX
```

Fallback:

``` text
Playwright
```

Decision flow:

``` text
HTTPX
  ↓
HTTP success?
  ↓
Content sufficient?
 ├── YES → Parser
 └── NO
      ↓
JS fallback enabled?
 ├── NO → controlled failure/partial result
 └── YES → Playwright
```

Playwright MUST NOT be used for every URL by default.

This reduces resource consumption and improves throughput.

------------------------------------------------------------------------

# 11. Retry Rules

Retries are only for transient failures.

Retry candidates:

``` text
timeouts
connection reset
transient network errors
selected 5xx responses
```

Do not normally retry:

``` text
invalid URL
unsupported scheme
most 4xx responses
parsing errors
extraction errors
unsupported document type
```

Default:

``` text
Attempt 1
   ↓ 1 sec
Attempt 2
   ↓ 2 sec
Attempt 3
   ↓
Final failure
```

Retries MUST be bounded.

Never use infinite retry loops.

------------------------------------------------------------------------

# 12. Fallback Rules

The fallback hierarchy is:

``` text
PRIMARY
   ↓
RETRY
   ↓
FALLBACK
   ↓
PARTIAL RESULT
   ↓
CONTROLLED FAILURE
```

Examples:

### HTML

``` text
HTTPX
 ↓
insufficient content
 ↓
Playwright
 ↓
parse rendered HTML
```

### PDF

``` text
PDF download
 ↓
PyMuPDF extraction
 ↓
usable text?
 ├── YES → process
 └── NO
      ↓
retain original PDF
      ↓
record PDF_EXTRACTION_ERROR
      ↓
continue job
```

### Media

``` text
download
 ↓
retry
 ↓
failed
 ↓
record media error
 ↓
page/job continues
```

------------------------------------------------------------------------

# 13. Failure Isolation

The fundamental rule is:

> A URL failure is not a job failure.

Example:

``` text
URL A → SUCCESS
URL B → TIMEOUT → FAILED
URL C → SUCCESS
URL D → JS fallback → SUCCESS
```

The job continues.

Job-level failure should be reserved for failures that make safe
continuation impossible, especially critical persistence/system
failures.

------------------------------------------------------------------------

# 14. Error Taxonomy

Use a controlled error enum.

``` python
class ErrorType(str, Enum):
    URL_VALIDATION_ERROR = "URL_VALIDATION_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    HTTP_ERROR = "HTTP_ERROR"
    PARSING_ERROR = "PARSING_ERROR"
    EXTRACTION_ERROR = "EXTRACTION_ERROR"
    JS_RENDERING_ERROR = "JS_RENDERING_ERROR"
    PDF_EXTRACTION_ERROR = "PDF_EXTRACTION_ERROR"
    MEDIA_DOWNLOAD_ERROR = "MEDIA_DOWNLOAD_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXPORT_ERROR = "EXPORT_ERROR"
```

Never use arbitrary error strings as the primary classification.

------------------------------------------------------------------------

# 15. Error Handling Pattern

Every processing operation should conceptually follow:

``` text
Validate
   ↓
Execute
   ↓
Detect failure
   ↓
Classify
   ↓
Retry?
   ├── YES → retry
   └── NO
        ↓
Fallback?
   ├── YES → fallback
   └── NO
        ↓
Record error
        ↓
Return controlled result
```

Avoid:

``` python
except Exception:
    pass
```

This hides failures.

Also avoid blindly allowing every exception to terminate the complete
job.

------------------------------------------------------------------------

# 16. Exception Hierarchy

Use explicit internal exception classes.

``` text
ProjectError
│
├── ValidationError
├── RetrievalError
│   ├── NetworkError
│   ├── TimeoutError
│   └── HTTPError
├── ParsingError
├── ExtractionError
├── RenderingError
├── MediaError
├── PersistenceError
└── ExportError
```

Expected webpage failures should normally be converted into controlled
processing results and error records.

Unexpected infrastructure failures should propagate to the appropriate
higher-level boundary.

------------------------------------------------------------------------

# 17. Error Manager

All modules SHOULD report errors through an ErrorManager interface.

Example:

``` python
error_manager.record(
    job_id=job_id,
    url_id=url_id,
    error_type="TIMEOUT_ERROR",
    attempt=2,
    message="Request timed out"
)
```

The ErrorManager is responsible for:

-   classification
-   structured recording
-   attempt number
-   URL status updates
-   job statistics
-   safe user-facing messages
-   operational logging

Do not duplicate error persistence logic across every service.

------------------------------------------------------------------------

# 18. HTTP Status Handling

Suggested classification:

``` text
2xx → success
3xx → follow/handle according to redirect policy
4xx → normally non-retryable failure
5xx → potentially retryable
```

All final failures MUST be recorded.

Do not retry all HTTP errors indiscriminately.

------------------------------------------------------------------------

# 19. Rate Limiting

Rate limiting MUST be centralized.

Do not write random:

``` python
await asyncio.sleep(...)
```

throughout the codebase.

Use:

``` text
RateLimiter
   ↓
domain-specific scheduling
```

and:

``` text
Semaphore
   ↓
global concurrency ceiling
```

The system should maintain separate pacing state per domain.

------------------------------------------------------------------------

# 20. Concurrency

Use bounded async concurrency.

Example:

``` python
semaphore = asyncio.Semaphore(max_concurrency)
```

Every network operation must acquire the appropriate concurrency permit.

Concurrency MUST NOT be unbounded.

Browser rendering should be especially conservative because browser
contexts are more resource-intensive than normal HTTP requests.

------------------------------------------------------------------------

# 21. Resource Cleanup

Every external resource MUST have deterministic cleanup.

Examples:

``` text
HTTP response → close/release
Playwright page → close
Browser context → close
Browser → close
Database session → close
Temporary file → remove/commit
```

Use `async with`, context managers, or `try/finally`.

Never rely solely on garbage collection.

------------------------------------------------------------------------

# 22. HTML Parsing

Parser responsibility:

``` text
HTML
 ↓
title
headings
paragraphs
links
tables
images
document references
```

Parser MUST NOT:

-   decide job state
-   write database records directly
-   perform aggressive NLP
-   download media

------------------------------------------------------------------------

# 23. Content Extraction

Extraction determines which parts of the parsed document represent
meaningful content.

Expected output:

``` json
{
  "title": "...",
  "headings": [],
  "paragraphs": [],
  "content": "...",
  "tables": [],
  "links": [],
  "images": [],
  "documents": []
}
```

Extraction and preprocessing MUST remain separate.

------------------------------------------------------------------------

# 24. Preprocessing Rules

Perform conservative normalization:

-   Unicode normalization
-   whitespace normalization
-   line-break normalization
-   encoding cleanup
-   obvious boilerplate removal
-   navigation/noise removal where confidently identifiable

Do NOT perform aggressive transformations such as:

-   stopword removal
-   stemming
-   lemmatization
-   semantic rewriting
-   LLM summarization

The output should remain faithful to source content.

------------------------------------------------------------------------

# 25. Content Hashing

Generate a SHA-256 hash after preprocessing.

``` python
hashlib.sha256(
    processed_content.encode("utf-8")
).hexdigest()
```

The hash is metadata in Version 1.

Do not automatically discard records solely because two pages have the
same content hash unless the specification explicitly requires
content-level duplicate removal.

URL deduplication and content hashing are separate concepts.

------------------------------------------------------------------------

# 26. Media Processing

Media types:

``` text
images
PDFs/documents
```

Flow:

``` text
Extractor
   ↓
Media references
   ↓
Media queue
   ↓
MediaDownloader
   ↓
Retry
   ↓
Download
   ↓
Validate
   ↓
Save
   ↓
Persist metadata
```

Store files under:

``` text
output/jobs/<job_id>/
```

Never allow arbitrary filesystem paths from crawled content.

Use temporary files followed by atomic rename where practical.

------------------------------------------------------------------------

# 27. PDF Processing

PDF flow:

``` text
Download
 ↓
Validate file
 ↓
PyMuPDF
 ↓
Extract text
 ↓
Text usable?
 ├── YES → preprocess
 └── NO
      ↓
retain PDF
      ↓
PDF_EXTRACTION_ERROR
      ↓
continue
```

An image-only or extraction-resistant PDF should not cause the complete
job to fail.

------------------------------------------------------------------------

# 28. Database Design

Core tables:

## scraping_jobs

``` text
job_id
status
crawl_depth
recursive
javascript_fallback
robots_mode
timeout_seconds
max_retries
domain_rate_limit
max_concurrency
total_urls
processed_urls
successful_urls
failed_urls
skipped_urls
created_at
started_at
completed_at
```

## url_records

``` text
url_id
job_id
url
normalized_url
depth
status
parent_url_id
discovered_at
processing_started_at
processing_completed_at
```

## pages

``` text
page_id
url_id
title
content
content_hash
created_at
processed_at
```

## media

``` text
media_id
page_id
media_type
source_url
local_path
status
file_size
created_at
```

## error_logs

``` text
error_id
job_id
url_id
error_type
message
attempt
timestamp
```

------------------------------------------------------------------------

# 29. Database Rules

Use:

-   primary keys
-   foreign keys
-   unique constraints
-   indexes
-   transactions
-   parameterized/ORM queries

Recommended unique constraint:

``` text
(job_id, normalized_url)
```

Useful indexes:

``` text
url_records(job_id, status)
pages(content_hash)
```

Database constraints are a second line of defense against
application-level race conditions.

------------------------------------------------------------------------

# 30. Transaction Rules

Use transactions around logically atomic operations.

Example:

``` text
URL processing result
   ↓
save page
save URL status
save media metadata
   ↓
commit
```

If a transaction fails:

``` text
rollback
 ↓
retry if safe
 ↓
otherwise classify persistence failure
```

Do not leave records in ambiguous intermediate states.

------------------------------------------------------------------------

# 31. Job State Machine

Use controlled states:

``` text
CREATED
   ↓
RUNNING
   ↓
COMPLETED

RUNNING
   ↓
COMPLETED_WITH_ERRORS

RUNNING
   ↓
FAILED
```

`FAILED` means job-level failure.

A single failed URL should normally be represented by:

``` text
URL = FAILED
JOB = COMPLETED_WITH_ERRORS
```

when the rest of the job completes successfully.

------------------------------------------------------------------------

# 32. Checkpointing

Do not retain the entire job only in memory.

Persist:

-   URL state
-   page result
-   error records
-   media metadata
-   job counters
-   job state

at meaningful checkpoints.

This makes the system more resilient to process termination and provides
accurate monitoring.

------------------------------------------------------------------------

# 33. JSON Export

JSON generation should read from persisted records rather than transient
crawler memory.

Architecture:

``` text
Crawler
   ↓
PostgreSQL
   ↓
JSONExporter
   ↓
JSON file
```

Representative record:

``` json
{
  "job_id": "...",
  "url": "...",
  "title": "...",
  "headings": [],
  "paragraphs": [],
  "content": "...",
  "tables": [],
  "links": [],
  "images": [],
  "documents": [],
  "metadata": {
    "timestamp": "...",
    "crawl_depth": 1,
    "content_hash": "...",
    "status": "success"
  }
}
```

Validate the generated JSON before exposing it as a completed export.

------------------------------------------------------------------------

# 34. API Design

Required endpoints:

``` text
POST /api/jobs
GET  /api/jobs
GET  /api/jobs/{job_id}
POST /api/jobs/{job_id}/start
GET  /api/jobs/{job_id}/results
GET  /api/jobs/{job_id}/errors
GET  /api/jobs/{job_id}/export
```

Routes MUST:

-   validate input
-   invoke application services
-   return appropriate HTTP status codes
-   avoid crawler implementation
-   avoid direct business logic
-   avoid direct infrastructure manipulation

------------------------------------------------------------------------

# 35. HTTP API Error Mapping

Suggested mapping:

``` text
400 → validation error
404 → job/resource not found
409 → invalid job state/conflict
422 → invalid structured request
500 → unexpected internal error
503 → unavailable critical infrastructure
```

Do not expose stack traces or internal database information to users.

------------------------------------------------------------------------

# 36. API Boundary

Bad:

``` python
@app.post("/jobs")
def create_job():
    crawl()
    parse()
    extract()
    save()
```

Correct:

``` python
@app.post("/jobs")
def create_job(request):
    return job_manager.create_job(request)
```

The route delegates.

The application service orchestrates.

The processing services perform the actual work.

------------------------------------------------------------------------

# 37. Security Rules

## URL Security

Only permit supported schemes.

Validate redirects before following them where applicable.

Do not allow arbitrary local-file access.

## Filesystem Security

All downloaded files MUST remain inside the job output directory.

Never construct paths directly from untrusted URLs without sanitization.

## UI Security

Crawled content is untrusted.

Escape HTML output.

Never inject crawled HTML directly into the dashboard.

## Database Security

Use SQLAlchemy/parameterized queries.

Never concatenate untrusted input into SQL.

## Error Security

Never expose:

-   database credentials
-   environment variables
-   internal filesystem paths
-   stack traces
-   connection strings
-   secrets

in API responses.

------------------------------------------------------------------------

# 38. Logging Rules

Structured logs should contain:

``` text
timestamp
level
component
job_id
url
event_type
attempt
message
```

Example:

``` text
WARNING
component=Retriever
job_id=JOB-102
url=https://example.com
event=TIMEOUT
attempt=2
message=Request timed out
```

Recommended levels:

``` text
DEBUG    internal diagnostics
INFO     normal lifecycle events
WARNING  retry/fallback/partial failure
ERROR    URL/component failure
CRITICAL job/infrastructure failure
```

Do not log sensitive information.

------------------------------------------------------------------------

# 39. Observability

At minimum track:

``` text
total URLs
processed URLs
successful URLs
failed URLs
skipped URLs
retry count
fallback count
average retrieval time
media failures
PDF extraction failures
job duration
```

This allows the dashboard to show meaningful progress.

------------------------------------------------------------------------

# 40. Service Interfaces

Example:

``` python
class Retriever(Protocol):
    async def retrieve(
        self,
        url: str,
        config: CrawlConfig
    ) -> RetrievalResult:
        ...
```

``` python
class Parser(Protocol):
    def parse(
        self,
        document: RetrievalResult
    ) -> ParsedDocument:
        ...
```

``` python
class Storage(Protocol):
    async def save_page(
        self,
        page: ProcessedDocument
    ) -> None:
        ...
```

Interfaces should describe behavior, not implementation.

------------------------------------------------------------------------

# 41. Dependency Injection

Prefer constructor injection.

Good:

``` python
class JobManager:
    def __init__(
        self,
        crawler,
        storage,
        error_manager
    ):
        self.crawler = crawler
        self.storage = storage
        self.error_manager = error_manager
```

Avoid:

``` python
class JobManager:
    def __init__(self):
        self.db = PostgreSQL(...)
        self.crawler = Crawler(...)
        self.browser = Playwright(...)
```

Constructor injection makes unit testing much easier.

------------------------------------------------------------------------

# 42. No Circular Dependencies

Never allow:

``` text
Crawler → JobManager → Crawler
```

or:

``` text
Parser → Extractor → Parser
```

The dependency graph must remain directed.

------------------------------------------------------------------------

# 43. No Shared Mutable Global State

Avoid:

``` python
GLOBAL_QUEUE = []
GLOBAL_CURRENT_JOB = ...
GLOBAL_BROWSER = ...
```

Use explicit objects and dependency injection.

A shared resource such as a rate limiter may exist at application scope,
but ownership and lifecycle must be explicit.

------------------------------------------------------------------------

# 44. Crawler Processing Contract

For each URL:

``` text
Input:
    CrawlURL

Output:
    URLProcessingResult
```

Possible result:

``` python
@dataclass
class URLProcessingResult:
    url: str
    status: str
    page: ProcessedDocument | None
    discovered_links: list[str]
    media: list[MediaReference]
    error: ProcessingError | None
```

The crawler consumes the result and decides what links to queue.

It should not inspect parser internals.

------------------------------------------------------------------------

# 45. Complete URL Processing Algorithm

``` text
1. Normalize URL
2. Validate URL
3. Check duplicate
4. Mark URL PROCESSING
5. Acquire concurrency permit
6. Apply domain rate limiter
7. HTTPX retrieval
8. Retry transient failures
9. Evaluate content sufficiency
10. Invoke Playwright if required
11. Detect document type
12. Parse
13. Extract
14. Preprocess
15. Generate SHA-256
16. Persist page
17. Extract discovered links
18. Normalize links
19. Apply depth rule
20. Queue new URLs
21. Queue media
22. Download media
23. Persist media metadata
24. Mark URL SUCCESS
25. Release resources
```

Failure at a URL level:

``` text
Record error
   ↓
Mark URL FAILED / partial
   ↓
Release resources
   ↓
Continue next URL
```

------------------------------------------------------------------------

# 46. Complete Job Algorithm

``` text
Create job
   ↓
Validate configuration
   ↓
Normalize seed URLs
   ↓
Deduplicate seeds
   ↓
Create URL records
   ↓
RUNNING
   ↓
BFS processing
   ↓
Persist checkpoints
   ↓
Queue empty
   ↓
Generate final statistics
   ↓
Generate JSON export
   ↓
Finalize job
```

Final state:

``` text
No URL failures
    → COMPLETED

Some URL failures
    → COMPLETED_WITH_ERRORS

Critical infrastructure/persistence failure
    → FAILED
```

------------------------------------------------------------------------

# 47. Testing Strategy

Testing MUST be layered.

``` text
Unit
  ↓
Integration
  ↓
System
  ↓
Negative
  ↓
Performance
```

Do not use only end-to-end testing.

------------------------------------------------------------------------

# 48. Unit Test Requirements

## URL Normalizer

Test:

-   scheme normalization
-   hostname case
-   fragments
-   ports
-   paths
-   query parameters
-   malformed URLs

## Retry

Test:

-   zero failures
-   one transient failure
-   two transient failures
-   final failure
-   non-retryable failure

## Hashing

Test:

``` text
same input → same hash
different input → different hash
```

## Preprocessor

Test:

-   whitespace
-   Unicode
-   encoding
-   boilerplate
-   empty content

------------------------------------------------------------------------

# 49. Integration Tests

At minimum:

``` text
Retriever → Parser
Parser → Extractor
Extractor → Preprocessor
URLManager → Database
Storage → JSONExporter
JobManager → Crawler
```

Use controlled fixtures rather than depending entirely on external
websites.

------------------------------------------------------------------------

# 50. Negative Test Matrix

Mandatory cases:

``` text
Invalid URL
Unsupported protocol
Timeout
DNS failure
Connection reset
404
403
500
Malformed HTML
Empty HTML
JavaScript rendering failure
Corrupted PDF
Image-only PDF
Media download failure
Duplicate URL
Database unavailable
Database transaction failure
JSON write failure
```

Every test must verify both:

1.  Correct error classification
2.  Correct continuation/termination behavior

------------------------------------------------------------------------

# 51. System Test Cases

### TC-01 --- Valid Seed

``` text
Valid URL
→ job created
→ URL queued
```

### TC-02 --- Invalid URL

``` text
Invalid URL
→ validation error
→ URL not queued
```

### TC-03 --- Duplicate

``` text
Same normalized URL
→ one record
→ duplicate skipped
```

### TC-04 --- Crawl Depth

``` text
Depth reached
→ deeper links not queued
```

### TC-05 --- Timeout

``` text
Timeout
→ retry
→ final failure
→ next URL processed
```

### TC-06 --- JavaScript

``` text
Static retrieval insufficient
→ Playwright
→ rendered content processed
```

### TC-07 --- PDF

``` text
PDF
→ download
→ PyMuPDF extraction
→ preprocessing
```

### TC-08 --- PDF Failure

``` text
Extraction failure
→ retain PDF
→ log error
→ continue
```

### TC-09 --- Parser Failure

``` text
Parser failure
→ URL failed
→ remaining URLs continue
```

### TC-10 --- Content Hash

``` text
Same processed content
→ same SHA-256
→ records remain unless explicit content deduplication is enabled
```

------------------------------------------------------------------------

# 52. Performance Testing

Use a representative dataset of approximately 50--100 URLs.

Include:

``` text
static HTML
linked pages
tables
images
PDFs
JavaScript pages
failure cases
```

Measure:

``` text
total job duration
URLs/second
average retrieval time
retry count
fallback count
success rate
failure rate
memory usage
browser resource usage
```

Do not invent a throughput target before benchmarking.

Record the measured baseline and compare later implementations against
it.

------------------------------------------------------------------------

# 53. Resource Safety Rules

The implementation MUST enforce:

``` text
bounded concurrency
bounded retries
bounded crawl depth
timeouts
rate limiting
controlled browser creation
maximum reasonable download size
temporary-file cleanup
database connection management
```

No operation should be able to consume unlimited resources.

------------------------------------------------------------------------

# 54. Code Quality Rules

Use:

-   type hints
-   docstrings for public interfaces
-   descriptive names
-   small functions
-   explicit return types
-   constants/enums instead of magic strings
-   dependency injection
-   centralized configuration
-   centralized logging
-   centralized retry policy

Avoid:

-   giant functions
-   duplicated retry logic
-   duplicated error handling
-   hidden global state
-   magic numbers
-   broad `except Exception` without handling
-   direct SQL throughout services
-   business logic inside routes

------------------------------------------------------------------------

# 55. Function Size Rule

Functions should generally represent one logical operation.

Prefer:

``` text
process_url()
    → retrieve()
    → parse()
    → extract()
    → preprocess()
    → persist()
```

rather than one 500-line `process_url()` function.

If a function requires many unrelated comments to explain what it is
doing, it likely contains multiple responsibilities.

------------------------------------------------------------------------

# 56. Configuration Rule

No hard-coded operational values inside business logic.

Bad:

``` python
timeout = 15
retries = 3
depth = 2
```

inside different modules.

Good:

``` python
config.timeout_seconds
config.max_retries
config.crawl_depth
```

Configuration must have one authoritative source.

------------------------------------------------------------------------

# 57. Constants and Enums

Use enums for:

``` text
JobStatus
URLStatus
ErrorType
MediaStatus
DocumentType
RobotsMode
```

Avoid:

``` python
if status == "completed_with_errors":
```

throughout the project.

Prefer:

``` python
if status == JobStatus.COMPLETED_WITH_ERRORS:
```

------------------------------------------------------------------------

# 58. External Service Boundary

All external systems should be behind adapters.

``` text
HTTPXAdapter
PlaywrightAdapter
PostgresStorage
FilesystemStorage
```

This means tests can replace them with:

``` text
MockRetriever
MockStorage
MockRenderer
```

without modifying business logic.

------------------------------------------------------------------------

# 59. Testing With Mocks

Unit tests MUST NOT require:

-   real PostgreSQL
-   real browser
-   external websites

unless the test is explicitly an integration/system test.

Example:

``` text
JobManager
   ↓
MockCrawler
MockStorage
MockErrorManager
```

This makes tests fast and deterministic.

------------------------------------------------------------------------

# 60. Determinism

Where possible:

-   use fixed fixtures
-   normalize URLs deterministically
-   generate deterministic hashes
-   avoid timing-dependent assertions
-   isolate external network tests
-   use explicit test configuration

Do not make tests depend on current website content.

------------------------------------------------------------------------

# 61. Git Rules

Recommended branch model:

``` text
main
  │
  ├── feature/url-manager
  ├── feature/retriever
  ├── feature/parser
  ├── feature/extractor
  ├── feature/storage
  └── feature/api
```

Rules:

-   One logical feature per branch
-   Small commits
-   No unrelated changes
-   Run tests before merge
-   Do not commit secrets
-   Do not commit downloaded crawl output
-   Do not commit database credentials
-   Do not commit `.env`

------------------------------------------------------------------------

# 62. Environment Configuration

Use environment variables for deployment-specific settings.

Example:

``` text
DATABASE_URL
LOG_LEVEL
OUTPUT_DIR
DEFAULT_TIMEOUT
DEFAULT_MAX_RETRIES
DEFAULT_MAX_CONCURRENCY
DEFAULT_RATE_LIMIT
PLAYWRIGHT_ENABLED
```

Provide `.env.example`.

Never commit real credentials.

------------------------------------------------------------------------

# 63. Documentation Rules

Every major module should document:

``` text
Purpose
Inputs
Outputs
Dependencies
Failure modes
Retry behavior
Fallback behavior
Resource ownership
Tests
```

Every public interface should have a short contract.

------------------------------------------------------------------------

# 64. Implementation Sequence

Implement in this order:

## Phase 1 --- Foundation

``` text
settings
database
models
schemas
interfaces
logging
```

## Phase 2 --- URL System

``` text
normalizer
URLManager
BFS queue
deduplication
```

## Phase 3 --- Retrieval

``` text
HTTPX
timeouts
retry
rate limiter
status classification
```

## Phase 4 --- Rendering

``` text
content detector
renderer interface
Playwright
resource cleanup
```

## Phase 5 --- Parsing

``` text
HTML parser
PDF parser
```

## Phase 6 --- Extraction

``` text
content extraction
links
tables
images
documents
```

## Phase 7 --- Preprocessing

``` text
normalization
boilerplate cleanup
content assembly
hashing
```

## Phase 8 --- Persistence

``` text
storage
transactions
job state
URL state
errors
media metadata
```

## Phase 9 --- Orchestration

``` text
JobManager
complete pipeline
checkpointing
```

## Phase 10 --- Export

``` text
JSON exporter
schema validation
```

## Phase 11 --- API

``` text
FastAPI routes
request validation
error mapping
```

## Phase 12 --- UI

``` text
Dashboard
Create Job
Monitor
Results
Errors
```

## Phase 13 --- Hardening

``` text
negative tests
performance tests
security tests
resource tests
failure injection
```

------------------------------------------------------------------------

# 65. Team Development Strategy

For a two-person team, split by subsystem boundaries.

## Developer A

``` text
Configuration
Database
Models
URLManager
Crawler
JobManager
FastAPI
Dashboard
```

## Developer B

``` text
Retriever
RetryPolicy
RateLimiter
Playwright
Parser
Extractor
Preprocessor
MediaDownloader
```

## Shared

``` text
Interfaces
ErrorManager
JSONExporter
Integration tests
System tests
Performance testing
```

The interface contracts MUST be agreed before parallel implementation.

------------------------------------------------------------------------

# 66. Definition of Done --- Module

A module is complete only when:

``` text
[ ] Interface defined
[ ] Input model defined
[ ] Output model defined
[ ] Error behavior defined
[ ] Retry behavior defined if applicable
[ ] Fallback behavior defined if applicable
[ ] Resource cleanup implemented
[ ] Logging implemented
[ ] Unit tests written
[ ] Negative tests written
[ ] No unrelated responsibilities
[ ] No forbidden direct dependencies
```

------------------------------------------------------------------------

# 67. Definition of Done --- Project

The project is complete only when:

``` text
[ ] URL validation works
[ ] URL normalization works
[ ] BFS works
[ ] Depth restriction works
[ ] Recursive mode works
[ ] Deduplication works
[ ] HTTPX retrieval works
[ ] Timeout handling works
[ ] Retry works
[ ] Rate limiting works
[ ] Concurrency is bounded
[ ] Playwright fallback works
[ ] HTML parsing works
[ ] PDF parsing works
[ ] Content extraction works
[ ] Preprocessing works
[ ] SHA-256 generation works
[ ] Image downloading works
[ ] PDF downloading works
[ ] Media failures are isolated
[ ] URL state is persisted
[ ] Job state is persisted
[ ] Errors are classified
[ ] Failed URLs do not kill the job
[ ] JSON export works
[ ] API works
[ ] UI works
[ ] Security checks pass
[ ] Negative tests pass
[ ] Integration tests pass
[ ] System tests pass
[ ] Performance benchmark is recorded
```

------------------------------------------------------------------------

# 68. Critical Design Decisions

## Decision 1 --- HTTPX is the default

Reason:

-   lightweight
-   fast
-   efficient
-   suitable for static pages
-   lower resource usage than browser rendering

Playwright is an exception/fallback path.

## Decision 2 --- PostgreSQL is the source of truth

The crawler should not rely only on in-memory state.

## Decision 3 --- Filesystem for binary media

Store binary images/PDFs on the filesystem and metadata in PostgreSQL.

## Decision 4 --- JSON is an export representation

Do not make JSON the primary operational storage layer.

## Decision 5 --- URL failure is isolated

A failed URL does not terminate the job.

## Decision 6 --- Browser rendering is conditional

Do not launch browsers unnecessarily.

## Decision 7 --- Content hash is metadata

Do not silently implement content-level deduplication if it is not part
of the approved Version 1 scope.

------------------------------------------------------------------------

# 69. Requirement Conflict to Resolve

There is one important specification-level conflict that MUST be
explicitly resolved before implementation.

The original SRS states that `robots.txt` is not used as a crawling
restriction.

The final SDD specifies:

``` text
robots_mode = configurable
default = respect
```

Because the SDD is the final design baseline, the implementation plan
should use:

``` text
robots_mode = respect
```

unless the project owner formally decides otherwise.

This decision should be recorded in the requirements/design decision log
rather than silently changing behavior.

------------------------------------------------------------------------

# 70. Golden Failure-Handling Rule

The complete project should follow this rule:

``` text
                 FAILURE
                    │
          ┌─────────┴─────────┐
          │                   │
    Recoverable          Unrecoverable
          │                   │
      Retry/Fallback      Record failure
          │                   │
       succeeds?              │
       │      │               │
      YES     NO              │
       │      │               │
       │      └───────────────┘
       │              │
       ▼              ▼
 Continue        URL FAILED
 pipeline            │
                     ▼
              Continue job
```

Only when the failure compromises a job-wide invariant:

``` text
critical database failure
critical application failure
unrecoverable persistence failure
```

should the complete job enter:

``` text
FAILED
```

------------------------------------------------------------------------

# 71. Final Architectural Principle

The most important implementation principle is:

> **Every component should either perform one responsibility, coordinate
> responsibilities, or persist information --- never all three.**

Therefore:

``` text
Route
    → receives request

Application Service
    → coordinates

Crawler
    → traverses

Retriever
    → retrieves

Renderer
    → renders

Parser
    → parses

Extractor
    → extracts

Preprocessor
    → cleans

Deduplicator
    → hashes/deduplicates

Media Downloader
    → downloads media

Storage
    → persists

Error Manager
    → records/classifies failures

Exporter
    → generates JSON

UI
    → displays state
```

This structure preserves high cohesion, minimizes coupling, supports
independent testing, allows replacement of individual technologies, and
ensures that failure of one URL or one processing technique does not
unnecessarily bring down the complete scraping job.
