import glob
import json
import os
from unittest.mock import MagicMock, patch

import requests

from src.ingest import downloader


def test_write_debug_log_on_download_failure(tmpdir):
    with patch("src.ingest.downloader.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "<html><body>Access Denied from cloudflare</body></html>"
        mock_response.request.headers = {"User-Agent": "test-agent"}

        # raise_for_status will raise an exception
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("403 Forbidden")

        mock_get.return_value = mock_response

        pmid = "99999999"
        doi = "10.1234/test"
        url = "https://example.com/test.pdf"

        # Ensure log dir doesn't have old files for this test
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "logs")
        if os.path.exists(log_dir):
            for f in glob.glob(os.path.join(log_dir, f"download_fail_{pmid}_*.json")):
                os.remove(f)

        result = downloader.download_pdf_from_url(url, "dummy.pdf", pmid=pmid, doi=doi)

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
