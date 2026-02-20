"""
Fetcher module for Worktree A - RECAP PDF streaming download
"""
import os
import asyncio
from typing import Dict, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Add the shared directory to the path
import sys
sys.path.insert(0, '../bankruptcy-retrieval')

from shared.config import MAX_PDF_BYTES
from config import DOWNLOAD_DIR

# HTTP client for fetching PDFs (no auth needed for RECAP PDFs)
http_client = httpx.AsyncClient(timeout=30.0)

# Retry configuration
retry_config = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=2, max=10),
    "retry": retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException))
}

@retry(**retry_config)
async def download_recap_pdf(pdf_url: str, deal_id: str, download_dir: str = DOWNLOAD_DIR) -> Dict[str, Optional[str|int]]:
    """
    Download a RECAP PDF with streaming and size checking.

    Args:
        pdf_url: URL of the PDF to download
        deal_id: Deal ID for organizing downloads
        download_dir: Directory to save downloads

    Returns:
        Dict with success status and details
    """
    # Ensure download directory exists
    deal_download_dir = os.path.join(download_dir, deal_id)
    os.makedirs(deal_download_dir, exist_ok=True)

    # Construct the full URL for RECAP PDFs
    if pdf_url.startswith("/recap/"):
        full_url = f"https://storage.courtlistener.com{pdf_url}"
    else:
        full_url = pdf_url

    try:
        # First, check the content length
        head_response = await http_client.head(full_url)
        content_length = head_response.headers.get("content-length")

        if content_length:
            file_size = int(content_length)
            if file_size > MAX_PDF_BYTES:
                return {
                    "success": False,
                    "local_file_path": None,
                    "size_bytes": file_size,
                    "failure_reason": f"File too large ({file_size} bytes > {MAX_PDF_BYTES} bytes)"
                }

        # Stream the download
        async with http_client.stream("GET", full_url) as response:
            response.raise_for_status()

            # Double-check content length from response headers
            content_length = response.headers.get("content-length")
            if content_length:
                file_size = int(content_length)
                if file_size > MAX_PDF_BYTES:
                    return {
                        "success": False,
                        "local_file_path": None,
                        "size_bytes": file_size,
                        "failure_reason": f"File too large ({file_size} bytes > {MAX_PDF_BYTES} bytes)"
                    }

            # Generate filename from URL
            filename = pdf_url.split("/")[-1]
            if not filename.endswith(".pdf"):
                filename += ".pdf"

            file_path = os.path.join(deal_download_dir, filename)

            # Stream download to file
            downloaded_bytes = 0
            with open(file_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    downloaded_bytes += len(chunk)

                    # Check size during download as well
                    if downloaded_bytes > MAX_PDF_BYTES:
                        f.close()
                        os.remove(file_path)
                        return {
                            "success": False,
                            "local_file_path": None,
                            "size_bytes": downloaded_bytes,
                            "failure_reason": f"File too large ({downloaded_bytes} bytes > {MAX_PDF_BYTES} bytes)"
                        }

                    f.write(chunk)

            return {
                "success": True,
                "local_file_path": file_path,
                "size_bytes": downloaded_bytes,
                "failure_reason": None
            }

    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "local_file_path": None,
            "size_bytes": None,
            "failure_reason": f"HTTP error {e.response.status_code}: {e.response.text}"
        }
    except Exception as e:
        return {
            "success": False,
            "local_file_path": None,
            "size_bytes": None,
            "failure_reason": str(e)
        }

async def close_http_client():
    """Close the HTTP client"""
    await http_client.aclose()