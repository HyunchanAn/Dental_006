from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from src.ingest import metadata_resolver


@pytest.mark.asyncio
async def test_get_fallback_email():
    assert metadata_resolver.get_fallback_email("test@example.com") == "test@example.com"
    assert metadata_resolver.get_fallback_email(None) == "systematic-reviewer-ai@example.com"
    assert metadata_resolver.get_fallback_email("") == "systematic-reviewer-ai@example.com"


@pytest.mark.asyncio
@patch("aiohttp.ClientSession.get")
async def test_fetch_crossref_metadata(mock_get):
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {"message": {"title": "Test Title", "URL": "http://test.url"}}
    mock_get.return_value.__aenter__.return_value = mock_response

    async with aiohttp.ClientSession() as session:
        result = await metadata_resolver.fetch_crossref_metadata(session, "10.1234/test")
        assert result.get("title") == "Test Title"


@pytest.mark.asyncio
@patch("aiohttp.ClientSession.get")
async def test_resolve_publisher_url_crossref_priority(mock_get):
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {
        "message": {"link": [{"URL": "http://publisher.com/pdf", "content-type": "application/pdf"}]}
    }
    mock_get.return_value.__aenter__.return_value = mock_response

    async with aiohttp.ClientSession() as session:
        url = await metadata_resolver.resolve_publisher_url(session, "10.1234/test")
        assert url == "http://publisher.com/pdf"
