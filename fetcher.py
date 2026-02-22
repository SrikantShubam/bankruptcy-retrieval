import os
import httpx
import asyncio
from pathlib import Path
from playwright.async_api import Page
from shared.telemetry import TelemetryLogger
from config import STRETTO_ERROR_SIGNATURES

logger = TelemetryLogger(
    worktree="B",
    ground_truth_path="../bankruptcy-retrieval/data/ground_truth.json",
    log_dir="./logs",
)

DOWNLOAD_DIR = os.environ.get('DOWNLOAD_DIR', './downloads')

async def download_via_browser(page: Page, pdf_url: str, deal_id: str) -> dict:
    """
    Use page.expect_download() context manager.
    Click the PDF link — do not navigate directly via URL.
    Save to DOWNLOAD_DIR/{deal_id}/{filename}.pdf
    Timeout: 60 seconds.
    """
    target_dir = Path(DOWNLOAD_DIR) / deal_id
    os.makedirs(target_dir, exist_ok=True)
    
    # Check for Stretto's "document no longer available" error
    try:
        await page.goto(pdf_url, wait_until="domcontentloaded", timeout=15000)
        error_el = await page.query_selector("h1, h2, strong")
        if error_el:
            error_text = (await error_el.inner_text()).lower()
            if any(sig in error_text for sig in STRETTO_ERROR_SIGNATURES) or ("no longer available" in error_text or "document" in error_text):
                return {
                    "success": False,
                    "local_file_path": None,
                    "failure_reason": "STRETTO_DOCUMENT_REMOVED",
                    "file_size_bytes": 0,
                    "fetch_method": "browser_download"
                }
    except Exception as e:
        print(f"Fetcher pre-check navigation failed: {e}")
        pass
    
    # We must click the link, so we need to find it in the DOM
    # If we only have the URL, we might need to inject an anchor and click it to trigger download
    # A robust way is to evaluate JS to click a synthetic link if the actual link is lost from context.
    
    try:
        async with page.expect_download(timeout=60000) as download_info:
            await page.evaluate(f'''() => {{
                const link = document.createElement("a");
                link.href = "{pdf_url}";
                link.download = "";
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }}''')
            
        download = await download_info.value
        filename = download.suggested_filename
        if not filename.endswith('.pdf'):
            filename += '.pdf'
            
        file_path = target_dir / filename
        await download.save_as(str(file_path))
        
        # Check size if possible
        size_bytes = os.path.getsize(file_path) if file_path.exists() else 0
        
        return {
            "success": True,
            "local_file_path": str(file_path),
            "file_size_bytes": size_bytes,
            "fetch_method": "browser_download",
            "failure_reason": None
        }
        
    except Exception as e:
        print(f"Browser download failed: {e}")
        return {
            "success": False,
            "local_file_path": None,
            "file_size_bytes": 0,
            "fetch_method": "browser_download",
            "failure_reason": str(e)
        }

async def download_via_httpx_fallback(pdf_url: str, deal_id: str, cookies: dict) -> dict:
    """
    Only used if browser download fails.
    Extract cookies from browser session, inject into httpx request.
    Streaming download, 50MB size guard.
    """
    target_dir = Path(DOWNLOAD_DIR) / deal_id
    os.makedirs(target_dir, exist_ok=True)
    
    filename = pdf_url.split("/")[-1]
    if not filename.endswith(".pdf"):
        filename = "downloaded.pdf"
        
    file_path = target_dir / filename
    
    # Convert Playwright cookie format to httpx format
    httpx_cookies = {cookie['name']: cookie['value'] for cookie in cookies}
    
    try:
        async with httpx.AsyncClient(cookies=httpx_cookies, verify=False) as client:
            async with client.stream('GET', pdf_url) as response:
                response.raise_for_status()
                
                size_bytes = 0
                with open(file_path, 'wb') as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        size_bytes += len(chunk)
                        if size_bytes > 50 * 1024 * 1024:  # 50MB
                            raise Exception("Download exceeded 50MB limit")
                            
        return {
            "success": True,
            "local_file_path": str(file_path),
            "file_size_bytes": size_bytes,
            "fetch_method": "httpx_stream",
            "failure_reason": None
        }
        
    except Exception as e:
        print(f"HTTPX download failed: {e}")
        return {
            "success": False,
            "local_file_path": None,
            "file_size_bytes": 0,
            "fetch_method": "httpx_stream",
            "failure_reason": str(e)
        }
