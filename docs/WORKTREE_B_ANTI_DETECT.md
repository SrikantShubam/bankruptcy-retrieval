# WORKTREE_B_ANTI_DETECT.md
# Worktree B — Hardened Headless Browser Pipeline
**Architecture Type:** Anti-Detect Browser Targeting Claims Agents (Kroll, Stretto, Epiq)
**Worker LLM:** Implement this file as `worktree-b/`

---

## 1. Philosophy

Worktree B targets claims agents directly — Kroll, Stretto, and Epiq — because they host
the original filed documents before they're indexed in RECAP. This gives higher coverage
and earlier availability, but requires bypassing Cloudflare Turnstile and TLS fingerprinting.

**Target advantage:** Access to documents not yet in RECAP; higher recall.
**Expected weakness:** Slower; browser sessions can fail; more complex error handling.

---

## 2. Anti-Bot Threat Model

| Protection Layer | Used By | Bypass Strategy |
|---|---|---|
| Cloudflare Turnstile (JS challenge) | Kroll, Epiq | Camoufox (real Firefox binary + custom fingerprint) |
| TLS fingerprinting (JA3/JA4) | All three | Camoufox native TLS; nodriver Chromium CDP |
| Behavioral mouse-movement analysis | Kroll | Camoufox built-in human behavior simulation |
| IP reputation scoring | All three | Delay + session reuse (no proxy needed) |
| Cookie-based session tokens | All three | Persist cookies across deals in same session |

---

## 3. Required Python Libraries
```
camoufox>=0.4            # Primary: Firefox-based anti-detect browser
nodriver>=0.35           # Fallback: Chrome CDP-based anti-detect
playwright>=1.44         # DOM interaction API (Camoufox uses Playwright API)
asyncio                  # Standard library concurrency
aiofiles>=23.0           # Async file I/O for downloads
python-dotenv            # Environment management
```

**DO NOT USE:** `selenium`, `undetected-chromedriver`, `puppeteer-stealth`.
These are detectable in 2025/2026. Use only Camoufox or nodriver.

---

## 4. Browser Session Architecture

### Session Lifecycle
```
[Pipeline Start]
    │
    ▼
[Launch single Camoufox instance]
  - headless=True (use virtual display xvfb for CI environments)
  - humanize=True  ← enables realistic mouse/keyboard simulation
  - persistent_context_dir="./browser_session/"  ← reuse cookies
    │
    ▼
[For each active deal — sequential, not concurrent]
  - Reuse the same browser context (DO NOT relaunch per deal)
  - New tab per deal; close tab when done
    │
    ▼
[Pipeline End]
    └── browser.close()
```

**Critical rule:** Launch ONE browser instance for the entire pipeline run.
Relaunching per deal triggers Cloudflare's browser fingerprint change detection.

### Cookie Persistence Strategy
```
- Store cookies to `./browser_session/cookies.json` after first successful page load
- On subsequent deals: inject saved cookies before navigation
- If Cloudflare challenge appears: pause 8–15 seconds (random), allow JS execution
- Never click CAPTCHA manually — Camoufox's Turnstile bypass handles it via JS hooks
```

---

## 5. The Scout — Claims Agent Navigation Strategy

### 5a. Kroll Restructuring (kroll.com/restructuring)

**Case search URL pattern:**
```
https://www.kroll.com/en/services/restructuring/cases
```

**Search sequence:**
1. Navigate to case search page
2. Wait for selector: `input[placeholder*="Search"]` (Cloudflare may delay this 3–8s)
3. Type company name character-by-character with 80–150ms random delays (Camoufox humanize)
4. Wait for results list: `div.case-result-item` or equivalent
5. Click matching result
6. On case page: locate document table with XPath: `//table[contains(@class,'document')]//tr`
7. Filter rows where `td[2]` (document type column) contains target keywords
8. Extract document link: `td//a[contains(@href,'.pdf')]/@href`

**Fallback XPath if table structure changes:**
```xpath
//a[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'first day')]
```

### 5b. Stretto (cases.stretto.com)

**Case URL pattern:** `https://cases.stretto.com/{case-slug}/`

**Search strategy:**
1. Construct slug from company name: lowercase, hyphens, strip special chars
2. Try direct URL navigation first (faster than search UI)
3. If 404: fall back to `https://cases.stretto.com/?s={company_name}` search
4. On case page: target `#documents-section` or equivalent anchor
5. XPath for document rows: `//div[@class='document-list']//a[contains(@href,'pdf')]`

### 5c. Epiq (dm.epiq11.com)

**Case URL pattern:** `https://dm.epiq11.com/{CaseName}/docket`

**Search strategy:**
1. Navigate to `https://dm.epiq11.com`
2. Use search field: `input#global-search` (may be AJAX-loaded)
3. Filter results by document type using dropdown if available
4. Extract docket table rows matching keyword filters

**Epiq-specific Cloudflare note:** Epiq uses Cloudflare in aggressive mode.
If Camoufox fails after 2 attempts, switch to `nodriver` (Chromium) for Epiq URLs only.

---

## 6. Metadata Extraction Before Download (Context Window Rule)

**After locating the document link but BEFORE downloading:**

Extract these fields from the page DOM without fetching the PDF:
- Document title (from link text or adjacent `<td>`)
- Filing date (from date column)
- Document type label (from type column or badge)
- File size if displayed

Construct `CandidateDocument` and pass to `gatekeeper.py`.
Only proceed to download if verdict is `"DOWNLOAD"`.

---

## 7. The Fetcher — PDF Download Via Browser

Use Playwright's download API through Camoufox:
```
Method: page.expect_download()
  - Click the PDF link
  - Intercept the download event
  - Save to ./downloads/{deal_id}/{filename}.pdf
  - Timeout: 60 seconds
```

Do NOT navigate to the PDF URL directly with `httpx` after extracting it.
The download link may require the authenticated browser session cookies.

**Alternative if direct download fails:**
- Use `page.goto(pdf_url)` in the same browser context
- Use `page.pdf()` to capture rendered page (last resort)

---

## 8. Fallback Cascade
```
1. Try Camoufox → Kroll/Stretto/Epiq
2. If Cloudflare hard block after 3 attempts:
   a. Switch to nodriver (Chromium) for the specific URL
3. If still blocked:
   a. Log "CLAIMS_AGENT_BLOCKED"
   b. Fall back to CourtListener RECAP API for this deal (use Worktree A logic inline)
4. If RECAP also has no document:
   a. Log pipeline_status: "NOT_FOUND"
```

---

## 9. Session Health Checks

Implement a `session_health_check()` function called every 10 deals:
- Navigate to a benign known page (e.g., `https://www.kroll.com/`)
- Verify page title loads correctly
- If session appears broken: close and relaunch browser, reload cookies
- Log: `{"event": "session_health_check", "status": "ok|relaunched"}`

---

## 10. Logging Events Specific to Worktree B
```json
{"event": "browser_launch", "library": "camoufox", "headless": true, "timestamp_utc": "..."}
{"event": "cloudflare_challenge_detected", "url": "...", "wait_seconds": 11.3, "deal_id": "..."}
{"event": "cloudflare_bypass_success", "deal_id": "...", "attempt": 1}
{"event": "dom_element_found", "selector": "div.case-result-item", "deal_id": "..."}
{"event": "metadata_extracted", "title": "First Day Declaration of CEO...", "filing_date": "2023-11-06", "deal_id": "..."}
{"event": "gatekeeper_decision", "verdict": "DOWNLOAD", "score": 0.93, "deal_id": "..."}
{"event": "download_complete", "file_path": "...", "size_bytes": 3100000, "deal_id": "..."}
{"event": "fallback_triggered", "reason": "CLAIMS_AGENT_BLOCKED", "fallback": "courtlistener", "deal_id": "..."}
{"event": "session_health_check", "status": "ok", "deals_processed": 10}
```