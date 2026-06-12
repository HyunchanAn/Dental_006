import glob
import json
import os
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from src.ingest import downloader


@pytest.mark.asyncio
async def test_write_debug_log_on_download_failure(tmpdir):
    # Mock the aiohttp response context manager
    mock_response = AsyncMock()
    mock_response.status = 403
    mock_response.text.return_value = "<html><body>Access Denied from cloudflare</body></html>"
    # To mock response.raise_for_status() raising an aiohttp.ClientResponseError
    mock_response.raise_for_status.side_effect = aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=403,
        message="Forbidden",
    )

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
