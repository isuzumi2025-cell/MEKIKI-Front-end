# Sitemap Pro: Project Design Bundle

> **Note**: This document is a consolidation of the 5 design artifacts for easy import into Obsidian.

## 1. Requirements Specification (`sitemap_spec.md`)

# Sitemap Pro: Requirements Specification

## 1. Goal
Create a "Reproducible Crawl Report" for ad production.
The tool must automatically crawl a website, capture visual and structural data, and present it in an interactive, shareable "Visual Sitemap" UI.

## 2. Inputs & Configuration
- **Start URL** (Required): The entry point (e.g., `https://example.com`).
- **Allowed Domains** (List): Restrict crawling to specific domains (e.g., `['example.com']`).
- **Max Pages** (Int): Hard limit on pages to crawl (Default: 50).
- **Concurrency** (Int): Parallel tabs/workers (Default: 4).
- **Headless** (Bool): Run browser invisibly (Default: True).
- **Authentication**:
    - **None**: Public sites.
    - **Login**: Configured via `.env` or separate secure JSON (NOT in report).
    - **Basic Auth**: Username/Password.
    - **Cookies**: Pre-baked session cookies.

## 3. Crawler Behavior
- **Exploration**: BFS (Breadth-First Search) preferred for "shallow but wide" coverage of top pages.
- **Normalization**: Strip query params (optional settings), handle trailing slashes.
- **Exclusion**: Respect `robots.txt` (configurable).
- **Safety**:
    - Do NOT execute arbitrary code from pages.
    - Timeout per page (e.g., 30s).
    - Retry limit (3 times).

## 4. Data Extraction (Per Page)
- **Visual**:
    - Full-page Screenshot (PNG, max height cap optional).
    - Thumbnail (JPG/WebP, small).
- **Structural**:
    - Outgoing Links (Internal & External).
    - Depth level.
- **Metadata**:
    - HTTP Status Code (200, 404, etc.).
    - `<title>`, `<meta description>`.
    - `<h1>` text.
    - Canonical URL.

## 5. Outputs (Artifacts)
All outputs stored in `outputs/{run_id}/`:
- **`data.json`**: Complete structured data (Nodes, Edges, Metadata).
- **`images/`**: Directory containing full screenshots and thumbnails.
- **`report/`**: Static Website (HTML/JS/CSS) visualizing the data.
    - **Index**: Network Graph (Cytoscape.js) of the site.
    - **Detail View**: Sidebar/Modal showing selected page's screenshot and metadata.
    - **Assets**: All necessary scripts bundled relative (for zip portability).

## 6. Security
- **Auth Isolation**: Credentials never saved to `data.json` or `report/`.
- **Sanitization**: All extracted text escaped in HTML report to prevent XSS.
- **Command Safety**: No shell execution from web content.

---

## 2. Architecture (`sitemap_architecture.md`)

# Sitemap Pro: Architecture & Data Model

## 1. System Overview

```mermaid
graph TD
    User[User] -->|Config| Main[Main Controller]
    Main -->|Init| Crawler[Playwright Crawler]
    Crawler -->|Fetch| Web[Target Website]
    Crawler -->|Extract| Parser[HTML/Metadata Parser]
    Crawler -->|Capture| Shot[Screenshot Engine]
    
    Crawler -->|Save| Storage[File System (run_id)]
    Storage -->|Write| JSON[data.json]
    Storage -->|Write| Img[images/*.png]
    
    Main -->|Build| Reporter[Report Generator]
    Reporter -->|Read| JSON
    Reporter -->|Bundle| UI[Static HTML Report]
```

## 2. Directory Structure (`sitemap_pro/`)
```
sitemap_pro/
├── app/
│   ├── core/
│   │   ├── crawler.py       # Async Playwright Logic
│   │   ├── parser.py        # BeautifulSoup/Extraction
│   │   └── config.py        # Settings management
│   ├── report/
│   │   ├── generator.py     # Static site builder
│   │   └── template/        # Vite/React Source for Report UI
│   └── main.py              # CLI Entry Point
├── outputs/                 # Artifact storage
│   └── {run_id}/
│       ├── data.json
│       ├── images/
│       └── report/          # Final viewable site
├── .env                     # Secrets (Auth)
└── requirements.txt
```

## 3. Data Model (`data.json`)
The core data structure exchanged between Python Crawler and JS Report.

```json
{
  "meta": {
    "run_id": "20240101_120000",
    "start_url": "https://example.com",
    "timestamp": "ISO8601",
    "total_pages": 50
  },
  "nodes": [
    {
      "id": "hash(url)",
      "url": "https://example.com/about",
      "title": "About Us",
      "h1": "Who We Are",
      "status": 200,
      "depth": 1,
      "screenshot": "images/hash.png",
      "thumbnail": "images/hash_thumb.jpg",
      "timestamp": "...",
      "errors": []
    }
  ],
  "edges": [
    {
      "source": "hash(url_A)",
      "target": "hash(url_B)",
      "type": "internal"
    }
  ]
}
```

## 4. Component Details
- **Crawler**: `asyncio` + `playwright`. Uses a `Set` for visited URLs (`seen_urls`). Uses a `Queue` for exploration.
- **Report UI**:
    - **Framework**: React (Vite Build) or Vanilla JS (if requirements simple). Recommended React for complex interactive Graph.
    - **Graph Lib**: `cytoscape.js` or `react-force-graph`.
    - **State**: Loads `data.json` at runtime (fetch) or embedded in `<script>` tag for single-file portability.

---

## 3. Task Plan (`sitemap_task_plan.md`)

# Sitemap Pro: Task Plan

## Phase 1: MVP Core (Priority: High)
1.  **Project Skeleton**
    -   [ ] Initialize directory structure (if needed).
    -   [ ] Verify dependencies (`playwright`, `pytest`, `networkx`).
2.  **Basic Crawler**
    -   [ ] Implement `Crawler` class in `app/core/crawler.py`.
    -   [ ] Add `crawl(url)` method with single-page fetch.
    -   [ ] Add Metadata Extraction (Title, Links).
    -   [ ] Add Screenshot Capture.
    -   [ ] Implement BFS Loop for `max_pages`.
3.  **Data Persistence**
    -   [ ] Implement `Storage` class to save `data.json` and images.
    -   [ ] Ensure run-unique directories (`outputs/run_{timestamp}`).
4.  **Basic Report**
    -   [ ] Create a minimal HTML template (`report.html`) that loads `data.json`.
    -   [ ] Render a simple list of pages with thumbnails.
    -   [ ] (MVP+) Add basic Cytoscape graph visualization.

## Phase 2: Robustness & Authentication (Priority: Medium)
1.  **Configuration**
    -   [ ] Implement `Config` loader from `.env` and CLI args.
    -   [ ] Add `ALLOWED_DOMAINS` filtering.
2.  **Authentication Engine**
    -   [ ] Implement `AuthManager` class.
    -   [ ] Add `login_form(url, user, pass, selector)` handler.
    -   [ ] Add `basic_auth(user, pass)` handler.
3.  **Error Handling**
    -   [ ] Add retry logic for timeouts/network errors.
    -   [ ] Log errors to `data.json` nodes.

## Phase 3: Advanced Report (Priority: Low)
1.  **Interactive UI**
    -   [ ] Enhance Graph styling (node size by degree, edge colors).
    -   [ ] Add Search/Filter by Title/URL.
    -   [ ] Side-by-side Detail View.
2.  **Export**
    -   [ ] "Download ZIP" feature (bundle report + images).

## Phase 4: Quality & Tests
1.  **Unit Tests**
    -   [ ] Test URL normalization.
    -   [ ] Test Metadata extractor with mock HTML.
2.  **E2E Tests**
    -   [ ] Run crawler against a local mock server.

---

## 4. Threat Model (`sitemap_threat_model.md`)

# Sitemap Pro: Threat Model

## 1. Assets
-   **Credentials**: User/Password for target sites.
-   **Local System**: The machine running the crawler.
-   **Report Viewers**: Users viewing the generated HTML report.

## 2. Threats & Risks

### A. Malicious Web Content (Crawler Side)
-   **Risk**: Target site contains malicious JS (Cryptominers, Exploits) or infinite redirects.
-   **Mitigation**:
    -   Run Playwright in **Headless** mode (mostly).
    -   **Disable JS execution** where possible (though crawler needs it for rendering, so use **Timeout**).
    -   **No File System Access**: Browser context is sandboxed (standard Playwright behavior).
    -   **Strict Timeouts**: 30s per page global timeout.

### B. Cross-Site Scripting (Report Side)
-   **Risk**: Target site has `<script>alert(1)</script>` in Title or H1. When Report UI renders this, it executes.
-   **Mitigation**:
    -   **Sanitization**: All extracted text (Title, H1, Meta) MUST be escaped before insertion into Report DOM.
    -   **React**: React automatically escapes strings by default. Verify no `dangerouslySetInnerHTML`.

### C. Indirect Prompt Injection
-   **Risk**: Page text contains "Delete all files" instructions that might be read by an AI agent later processing this data.
-   **Mitigation**:
    -   The Crawler itself is deterministic code, not an AI agent.
    -   If AI processes the report later, ensure context separation. (Out of scope for this tool, but noted).

### D. Credential Leakage
-   **Risk**: `auth` config leaked into the generated `data.json` or logs.
-   **Mitigation**:
    -   **Strict Separation**: `config.py` loads auth, uses it in `context.add_cookies()`, but NEVER writes it to `outputs/`.
    -   **Log Redaction**: Filter out passwords from standard logs.

## 3. Allowed Operations (Allowlist)
-   **Network**: Outbound HTTP/S to `START_URL` and `ALLOWED_DOMAINS` only.
-   **File System**: Write only to `outputs/{run_id}/`. Read only from `app/` and `.env`.
-   **Shell**: None. The application should not shell out.

---

## 5. Test Plan (`sitemap_test_plan.md`)

# Sitemap Pro: Test Plan

## 1. Unit Tests (`tests/unit/`)
Focus on pure logic functions.
-   **URL Normalization**:
    -   Input: `https://example.com/foo/?utm_source=1` -> Output: `https://example.com/foo/`
    -   Input: `/relative/path` -> Output: `https://base/relative/path`
-   **Parser**:
    -   Input: HTML string with `<title>Test</title>`
    -   Output: Correct dict `{'title': 'Test', ...}`

## 2. Integration Tests (`tests/integration/`)
Focus on Playwright interactions (mocked or real minimal).
-   **Crawler Fetch**:
    -   Spin up local `http.server`.
    -   Run Crawler against `http://localhost:8000`.
    -   Verify strict connectivity and data extraction.
-   **Screenshot**:
    -   Verify PNG file is created and size > 0.

## 3. E2E / Verification (`verify/`)
-   **"Smoke Test"**:
    -   Run full pipeline on `https://example.com` (max 5 pages).
    -   Check `outputs/run_X/data.json` exists.
    -   Check `outputs/run_X/report/index.html` loads without JS errors.

## 4. Security Tests
-   **Auth Leak Check**:
    -   Grep `data.json` for known dummy password string. Should match 0.
-   **XSS Payload**:
    -   Crawl a local page with `<title><script>alert(1)</script></title>`.
    -   Open Report. Verify script does NOT execute.
