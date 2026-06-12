import glob
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.ingest import downloader
from src.ingest.downloader import _apply_institutional_proxy


@pytest.mark.asyncio
@patch("src.ingest.downloader.download_pdf_with_playwright", new_callable=AsyncMock)
async def test_write_debug_log_on_download_failure(mock_pw, tmpdir):
    mock_pw.return_value = False

    # Mock the aiohttp response context manager
    mock_response = AsyncMock()
    mock_response.status = 403
    mock_response.text.return_value = "<html><body>Access Denied from cloudflare</body></html>"
    mock_response.headers = {"Content-Type": "text/html"}

    # Mock the get context manager
    mock_get_ctx = AsyncMock()
    mock_get_ctx.__aenter__.return_value = mock_response

    # Mock the session
    mock_session = MagicMock()
    mock_session.get.return_value = mock_get_ctx

    pmid = "99999999"
    doi = "10.1234/test"
    url = "https://example.com/test.pdf"

    # Ensure log dir doesn't have old files for this test
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "logs")
    if os.path.exists(log_dir):
        for f in glob.glob(os.path.join(log_dir, f"download_fail_{pmid}_*.json")):
            os.remove(f)

    result = await downloader.download_pdf_from_url(mock_session, url, "dummy.pdf", pmid=pmid, doi=doi)

    assert result is False

    # Verify log file was created
    log_files = glob.glob(os.path.join(log_dir, f"download_fail_{pmid}_*.json"))
    assert len(log_files) > 0

    with open(log_files[0], "r", encoding="utf-8") as f:
        log_data = json.load(f)

    assert log_data["target_identifiers"]["pmid"] == pmid
    assert log_data["target_identifiers"]["doi"] == doi
    assert log_data["http_status"]["status_code"] == 403
    assert "Access Denied" in log_data["anti_bot_sign"]["detected_signs"]
    assert "Cloudflare" in log_data["anti_bot_sign"]["detected_signs"]
    assert log_data["anti_bot_sign"]["has_anti_bot"] is True


def test_apply_institutional_proxy():
    url = "https://link.springer.com/article/10.1007/s00221-020-05833-2"
    prefix = "https://ezproxy.snu.ac.kr"
    expected = "https://link-springer-com.ezproxy.snu.ac.kr/article/10.1007/s00221-020-05833-2"
    result = _apply_institutional_proxy(url, prefix)
    assert result == expected

    # Test empty values
    assert _apply_institutional_proxy("", prefix) == ""
    assert _apply_institutional_proxy(url, "") == url

    # Test already proxied or no dot domain
    url_no_dot = "https://localhost/test"
    assert _apply_institutional_proxy(url_no_dot, prefix) == "https://localhost.ezproxy.snu.ac.kr/test"
