import asyncio
from typing import Any, Dict, Optional, cast

import aiohttp

# Rate limiting semaphores for external APIs
CROSSREF_SEMAPHORE = asyncio.Semaphore(5)
OPENALEX_SEMAPHORE = asyncio.Semaphore(5)


def get_fallback_email(email=None):
    if email and email.strip():
        return email.strip()
    return "systematic-reviewer-ai@example.com"


async def fetch_crossref_metadata(session: aiohttp.ClientSession, doi: str, email: Optional[str] = None) -> Dict[str, Any]:
    """Fetch metadata from Crossref API."""
    if not doi:
        return {}

    url = f"https://api.crossref.org/works/{doi}"
    contact = get_fallback_email(email)
    headers = {"User-Agent": f"SystematicReviewerAI/1.0 (mailto:{contact})"}

    async with CROSSREF_SEMAPHORE:
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as response:
                if response.status == 200:
                    data = await response.json()
                    return cast(Dict[str, Any], data.get("message", {}))
        except Exception as e:
            print(f"  - Crossref API Error for {doi}: {e}")
    return {}


async def fetch_openalex_metadata(session: aiohttp.ClientSession, doi: str, email: Optional[str] = None) -> Dict[str, Any]:
    """Fetch metadata from OpenAlex API."""
    if not doi:
        return {}

    contact = get_fallback_email(email)
    # OpenAlex expects the DOI as doi:10.xxx
    url = f"https://api.openalex.org/works/doi:{doi}?mailto={contact}"

    async with OPENALEX_SEMAPHORE:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:
                if response.status == 200:
                    return cast(Dict[str, Any], await response.json())
        except Exception as e:
            print(f"  - OpenAlex API Error for {doi}: {e}")
    return {}


async def resolve_publisher_url(session: aiohttp.ClientSession, doi: str, email: Optional[str] = None) -> Optional[str]:
    """
    Attempts to resolve the actual publisher URL for a given DOI.
    First tries Crossref 'link' or 'resource.primary.URL'.
    Then tries OpenAlex 'primary_location'.
    Finally falls back to standard doi.org resolution.
    """
    if not doi:
        return None

    # 1. Try Crossref
    crossref_data = await fetch_crossref_metadata(session, doi, email)
    if crossref_data:
        # Check for direct links
        links = crossref_data.get("link", [])
        for link in links:
            if link.get("URL") and "pdf" in link.get("content-type", "").lower():
                return str(link["URL"])

        # Check primary resource URL
        resource = crossref_data.get("resource", {})
        primary = resource.get("primary", {})
        if primary.get("URL"):
            return str(primary["URL"])

    # 2. Try OpenAlex
    openalex_data = await fetch_openalex_metadata(session, doi, email)
    if openalex_data:
        primary_location = openalex_data.get("primary_location", {})
        if primary_location:
            pdf_url = primary_location.get("pdf_url")
            if pdf_url:
                return str(pdf_url)
            landing_page_url = primary_location.get("landing_page_url")
            if landing_page_url:
                return str(landing_page_url)

    # 3. Fallback to doi.org
    return f"https://doi.org/{doi}"
