import asyncio
import datetime
import json
import os
import xml.etree.ElementTree as ET

import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

from .scihub_fallback import SciHubDownloader

# External download connection limit
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(10)


def get_request_headers(email=None):
    try:
        from fake_useragent import UserAgent
        ua = UserAgent(os="windows", browsers=["chrome", "edge"]).random
    except Exception:
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

    contact = email if email else "systematic-reviewer-ai@example.com"
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1",
        "Email": contact,
    }


async def get_unpaywall_pdf_url(session, doi, email=None):
    if not doi:
        return None
    try:
        contact_email = email if email else "systematic-reviewer-ai@example.com"
        url = f"https://api.unpaywall.org/v2/{doi}?email={contact_email}"
        async with session.get(url, headers=get_request_headers(email), timeout=20) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("best_oa_location") and data["best_oa_location"].get("url_for_pdf"):
                    return data["best_oa_location"]["url_for_pdf"]
    except Exception as e:
        print(f"  - An unexpected error occurred while processing DOI {doi} with Unpaywall: {e}")
    return None


async def get_semantic_scholar_pdf_url(session, paper_id, email=None):
    if not paper_id:
        return None
    try:
        url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}?fields=openAccessPdf"
        async with session.get(url, headers=get_request_headers(email), timeout=20) as response:
            if response.status == 200:
                data = await response.json()
                oa_pdf = data.get("openAccessPdf")
                if oa_pdf and oa_pdf.get("url"):
                    return oa_pdf["url"]
    except Exception as e:
        print(f"  - Error querying Semantic Scholar for {paper_id}: {e}")
    return None


def write_debug_log(pmid, doi, url, status_code, headers, body_snippet, exception=None):
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "logs")
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    pmid_str = str(pmid) if pmid else "unknown"
    log_filename = os.path.join(log_dir, f"download_fail_{pmid_str}_{timestamp}.json")

    anti_bot_signs = []
    if body_snippet:
        lower_body = body_snippet.lower()
        if "access denied" in lower_body:
            anti_bot_signs.append("Access Denied")
        if "cloudflare" in lower_body:
            anti_bot_signs.append("Cloudflare")
        if "captcha" in lower_body:
            anti_bot_signs.append("Captcha")
        if "just a moment" in lower_body:
            anti_bot_signs.append("Just a moment")

    log_data = {
        "target_identifiers": {"pmid": pmid, "doi": doi, "url": url},
        "network_context": {
            "request_headers": headers,
            "user_agent": headers.get("User-Agent", "Unknown") if headers else "Unknown",
        },
        "http_status": {"status_code": status_code, "body_snippet": body_snippet[:1000] if body_snippet else ""},
        "anti_bot_sign": {"detected_signs": anti_bot_signs, "has_anti_bot": len(anti_bot_signs) > 0},
        "exception": str(exception) if exception else None,
    }

    try:
        with open(log_filename, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=4)
        print(f"  - Debug log written to {log_filename}")
    except Exception:
        pass


async def download_pdf_with_playwright(pdf_url, output_path, tei_path=None):
    print(f"  - Using Async Playwright Headless Browser for {pdf_url}...")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            )
            page = await context.new_page()
            await stealth_async(page)

            try:
                await page.goto(pdf_url, wait_until="networkidle", timeout=30000)
            except Exception:
                pass

            final_url = page.url
            cookies = await context.cookies()
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Cookie": cookie_str,
            }
            await browser.close()

        # Re-try the final URL with aiohttp using the cookies obtained by playwright
        async with aiohttp.ClientSession() as session:
            async with session.get(final_url, headers=headers, timeout=60) as res:
                content_type = res.headers.get("Content-Type", "").lower()
                if "application/pdf" not in content_type:
                    if tei_path:
                        print("  - URL returned HTML. Extracting full text via BeautifulSoup...")
                        html_content = await res.text()
                        soup = BeautifulSoup(html_content, "html.parser")
                        text = soup.get_text(separator=" ", strip=True)
                        xml_content = f'<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/><text><body><div><p>{text}</p></div></body></text></TEI>'
                        with open(tei_path, "w", encoding="utf-8") as f:
                            f.write(xml_content)
                        return "html"
                    return False

                with open(output_path, "wb") as f:
                    async for chunk in res.content.iter_chunked(8192):
                        f.write(chunk)
                print("  - SUCCESS: Downloaded PDF via Playwright session.")
                return "pdf"
    except Exception as e:
        print(f"  - Playwright fallback failed: {e}")
        return False


async def download_pdf_from_url(session, pdf_url, output_path, email=None, pmid=None, doi=None, tei_path=None):
    if "angle.org/doi/pdf" in pdf_url:
        pdf_url = pdf_url.replace("www.angle.org/doi/pdf", "meridian.allenpress.com/angle-orthodontist/article-pdf")

    try:
        async with session.get(pdf_url, headers=get_request_headers(email), timeout=60) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            if "application/pdf" not in content_type:
                print(f"  - Target URL returned {content_type}, trying Playwright fallback...")
                pw_res = await download_pdf_with_playwright(pdf_url, output_path, tei_path)
                if pw_res:
                    return pw_res
                
                body = await response.text()
                write_debug_log(pmid, doi, pdf_url, response.status, dict(response.headers), body, Exception("Not PDF"))
                return False

            with open(output_path, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
            return "pdf"
    except aiohttp.ClientError as e:
        print(f"  - Failed to download PDF from {pdf_url}: {e}")
        # Try Playwright fallback on failure
        pw_res = await download_pdf_with_playwright(pdf_url, output_path, tei_path)
        if pw_res:
            return pw_res
        write_debug_log(pmid, doi, pdf_url, None, None, None, e)
    except Exception as e:
        print(f"  - Unknown Error {pdf_url}: {e}")
    return False


async def process_single_article(session, article, output_dir, email, enable_scihub_fallback, tei_dir, scihub_downloader):
    pmid_node = article.find(".//PMID")
    pmid = pmid_node.text if pmid_node is not None else "unknown"
    output_filename = os.path.join(output_dir, f"{pmid}.pdf")

    if os.path.exists(output_filename):
        print(f"  - PDF already exists for {pmid}.")
        return pmid, "Already Downloaded"

    doi_node = article.find(".//ArticleId[@IdType='doi']")
    doi = doi_node.text if doi_node is not None else None

    async with DOWNLOAD_SEMAPHORE:
        # Strategy 1: Unpaywall
        if doi:
            pdf_url = await get_unpaywall_pdf_url(session, doi, email=email)
            if pdf_url:
                print(f"  - Found Unpaywall OA link for {doi}.")
                tei_path = os.path.join(tei_dir, f"{pmid}.xml") if tei_dir else None
                res = await download_pdf_from_url(session, pdf_url, output_filename, email, pmid, doi, tei_path)
                if res == "pdf":
                    return pmid, "Downloaded (Unpaywall)"
                elif res == "html":
                    return pmid, "Downloaded (HTML Fallback)"

        # Strategy 2: Semantic Scholar
        paper_id = f"DOI:{doi}" if doi else (f"PMID:{pmid}" if pmid else None)
        if paper_id:
            pdf_url = await get_semantic_scholar_pdf_url(session, paper_id, email=email)
            if pdf_url:
                print(f"  - Found Semantic Scholar OA link for {paper_id}.")
                tei_path = os.path.join(tei_dir, f"{pmid}.xml") if tei_dir else None
                res = await download_pdf_from_url(session, pdf_url, output_filename, email, pmid, doi, tei_path)
                if res == "pdf":
                    return pmid, "Downloaded (SemanticScholar)"
                elif res == "html":
                    return pmid, "Downloaded (HTML Fallback)"

        # Strategy 3: Sci-Hub Fallback
        if enable_scihub_fallback and doi and scihub_downloader:
            downloaded = await scihub_downloader.download_by_doi(doi, output_filename)
            if downloaded:
                return pmid, "Downloaded (Sci-Hub)"

        print(f"  - No OA source found for {pmid}.")
        write_debug_log(pmid, doi, None, None, None, None, Exception("No OA Source Found"))
        return pmid, "No OA Source Found"


async def download_pdfs_async(articles, output_dir, email, enable_scihub_fallback, tei_dir):
    scihub_downloader = SciHubDownloader() if enable_scihub_fallback else None
    
    async with aiohttp.ClientSession() as session:
        tasks = [
            process_single_article(session, article, output_dir, email, enable_scihub_fallback, tei_dir, scihub_downloader)
            for article in articles
        ]
        results = await asyncio.gather(*tasks)
        return dict(results)


def download_pdfs_from_xml(xml_path, output_dir, allowed_pmids=None, email=None, enable_scihub_fallback=False, tei_dir=None):
    os.makedirs(output_dir, exist_ok=True)
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Error: Failed to parse XML file at {xml_path}. {e}")
        return {}

    articles = root.findall(".//PubmedArticle")
    
    if allowed_pmids is not None:
        allowed_pmids_set = set(str(p) for p in allowed_pmids)
        articles = [a for a in articles if a.find(".//PMID") is not None and a.find(".//PMID").text in allowed_pmids_set]

    if not articles:
        return {}

    print(f"Attempting to download PDFs concurrently for {len(articles)} articles...")
    
    # Run async logic synchronously for compatibility with Streamlit caller
    return asyncio.run(download_pdfs_async(articles, output_dir, email, enable_scihub_fallback, tei_dir))
