from unittest.mock import AsyncMock, MagicMock

import pytest

from src.ingest import downloader


def test_dummy():
    pass


def test_removed_noncompliant_helpers():
    assert not hasattr(downloader, "SciHubDownloader")
    assert not hasattr(downloader, "get_default_chrome_user_data_dir")
    assert not hasattr(downloader, "_apply_institutional_proxy")


@pytest.mark.asyncio
async def test_get_unpaywall_pdf_url():
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "is_oa": True,
        "best_oa_location": {"url_for_pdf": "https://example.org/oa_article.pdf"},
    }
    mock_get_ctx = AsyncMock()
    mock_get_ctx.__aenter__.return_value = mock_response
    mock_session = MagicMock()
    mock_session.get.return_value = mock_get_ctx

    url = await downloader.get_unpaywall_pdf_url(mock_session, "10.1000/oa1", email="researcher@example.com")
    assert url == "https://example.org/oa_article.pdf"


@pytest.mark.asyncio
async def test_get_europe_pmc_pdf_url():
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "resultList": {
            "result": [
                {
                    "isOpenAccess": "Y",
                    "pmcid": "PMC1234567",
                    "fullTextUrlList": {
                        "fullTextUrl": [
                            {
                                "documentStyle": "pdf",
                                "availabilityCode": "OA",
                                "url": "https://europepmc.org/articles/PMC1234567?pdf=render",
                            }
                        ]
                    },
                }
            ]
        }
    }
    mock_get_ctx = AsyncMock()
    mock_get_ctx.__aenter__.return_value = mock_response
    mock_session = MagicMock()
    mock_session.get.return_value = mock_get_ctx

    url = await downloader.get_europe_pmc_pdf_url(mock_session, pmid="12345678")
    assert url == "https://europepmc.org/articles/PMC1234567?pdf=render"
