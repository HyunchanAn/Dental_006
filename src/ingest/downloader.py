import asyncio
import datetime
import json
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET

import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from . import metadata_resolver

# External download connection limit
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(10)


def get_request_headers(email=None):
    contact = email if email else "systematic-reviewer-ai@example.com"
    return {
        "User-Agent": f"SystematicReviewerAI/1.0 (mailto:{contact})",
        "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Email": contact,
    }


async def get_unpaywall_pdf_url(session, doi, email=None):
    """Query Unpaywall API for a legal Open Access PDF URL."""
    if not doi:
        return None
    try:
        contact_email = email if email else "systematic-reviewer-ai@example.com"
        url = f"https://api.unpaywall.org/v2/{doi}?email={contact_email}"
        async with session.get(url, headers=get_request_headers(email), timeout=20) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("is_oa") and data.get("best_oa_location"):
                    pdf_url = data["best_oa_location"].get("url_for_pdf")
                    if pdf_url:
                        return pdf_url
    except Exception as e:
        print(f"  - An unexpected error occurred while processing DOI {doi} with Unpaywall: {e}")
    return None


async def get_pmc_oa_pdf_url(session, pmcid=None, email=None):
    """Query NCBI PubMed Central Open Access Web Service for a legal OA PDF link."""
    if not pmcid:
        return None
    try:
        clean_pmcid = pmcid if str(pmcid).upper().startswith("PMC") else f"PMC{pmcid}"
        url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={clean_pmcid}"
        async with session.get(url, headers=get_request_headers(email), timeout=20) as response:
            if response.status == 200:
                xml_text = await response.text()
                root = ET.fromstring(xml_text)
                for link in root.findall(".//link"):
                    if link.attrib.get("format") == "pdf" and link.attrib.get("href"):
                        href = link.attrib["href"]
                        if href.startswith("ftp://ftp.ncbi.nlm.nih.gov/"):
                            href = href.replace("ftp://ftp.ncbi.nlm.nih.gov/", "https://ftp.ncbi.nlm.nih.gov/", 1)
                        return href
    except Exception as e:
        print(f"  - Error querying PMC OA service for {pmcid}: {e}")
    return None


async def get_europe_pmc_pdf_url(session, pmid=None, doi=None, email=None):
    """Query Europe PMC REST API for Open Access PDF links."""
    query = None
    if pmid and str(pmid) != "unknown":
        query = f"EXT_ID:{pmid} AND SRC:MED"
    elif doi:
        query = f'DOI:"{doi}"'
    if not query:
        return None

    try:
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={query}&resultType=core&format=json"
        async with session.get(url, headers=get_request_headers(email), timeout=20) as response:
            if response.status == 200:
                data = await response.json()
                results = data.get("resultList", {}).get("result", [])
                for item in results:
                    if item.get("isOpenAccess") != "Y":
                        continue
                    url_list = item.get("fullTextUrlList", {}).get("fullTextUrl", [])
                    for entry in url_list:
                        if entry.get("documentStyle") == "pdf" and entry.get("availabilityCode") in ("OA", "F"):
                            if entry.get("url"):
                                return entry["url"]
                    pmcid = item.get("pmcid")
                    if pmcid:
                        return f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf"
    except Exception as e:
        print(f"  - Error querying Europe PMC for PMID={pmid} DOI={doi}: {e}")
    return None


async def get_semantic_scholar_pdf_url(session, paper_id, email=None):
    """Query Semantic Scholar Graph API for an Open Access PDF link."""
    if not paper_id:
        return None
    try:
        url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}?fields=isOpenAccess,openAccessPdf"
        async with session.get(url, headers=get_request_headers(email), timeout=20) as response:
            if response.status == 200:
                data = await response.json()
                oa_pdf = data.get("openAccessPdf")
                if oa_pdf and oa_pdf.get("url"):
                    return oa_pdf["url"]
    except Exception as e:
        print(f"  - Error querying Semantic Scholar for {paper_id}: {e}")
    return None


async def get_crossref_tdm_pdf_url(session, doi, email=None):
    """Resolve Open Access or licensed Crossref TDM / OpenAlex OA PDF links."""
    if not doi:
        return None
    try:
        crossref_data = await metadata_resolver.fetch_crossref_metadata(session, doi, email)
        if crossref_data:
            licenses = crossref_data.get("license", [])
            has_open_license = any(
                "creativecommons.org" in str(lic.get("URL", "")).lower()
                or lic.get("content-version") in ("vor", "am", "tdm")
                for lic in licenses
            )
            if has_open_license:
                for link in crossref_data.get("link", []):
                    content_type = str(link.get("content-type", "")).lower()
                    if link.get("URL") and "pdf" in content_type:
                        return str(link["URL"])

        openalex_data = await metadata_resolver.fetch_openalex_metadata(session, doi, email)
        if openalex_data:
            oa_info = openalex_data.get("open_access", {})
            if oa_info.get("is_oa") and oa_info.get("oa_url"):
                return str(oa_info["oa_url"])
    except Exception as e:
        print(f"  - Error checking Crossref TDM / OpenAlex OA for {doi}: {e}")
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


def is_valid_pdf(file_path):
    if not os.path.exists(file_path):
        return False
    if os.path.getsize(file_path) < 5120:  # 5KB limit
        return False
    try:
        with open(file_path, "rb") as f:
            header = f.read(4)
            if header != b"%PDF":
                return False
            f.seek(0)
            content = f.read(4096)
            text_content = content.decode("utf-8", errors="ignore").lower()
            invalid_keywords = ["redirecting", "login", "cloudflare", "403 forbidden", "just a moment", "<html"]
            for kw in invalid_keywords:
                if kw in text_content:
                    return False
    except Exception:
        return False
    return True


def is_valid_html_text(text):
    if len(text) < 500:
        return False
    lower_text = text.lower()
    invalid_keywords = ["redirecting", "login", "cloudflare", "403 forbidden", "just a moment", "please enable javascript"]
    for kw in invalid_keywords:
        if kw in lower_text:
            return False
    return True


async def download_pdf_with_playwright(pdf_url, output_path, tei_path=None):
    """
    Use an isolated temporary Playwright browser profile (never the user's real Chrome profile)
    to resolve standard Open Access redirects.
    """
    print(f"  - Using isolated headless browser session for OA URL {pdf_url}...")
    temp_profile_dir = tempfile.mkdtemp(prefix="sr_oa_browser_")
    try:
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=temp_profile_dir,
                headless=True,
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            try:
                await page.goto(pdf_url, wait_until="networkidle", timeout=30000)
            except Exception:
                pass

            final_url = page.url
            cookies = await context.cookies()
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            headers = {
                "User-Agent": "SystematicReviewerAI/1.0",
                "Cookie": cookie_str,
            }

            await context.close()

        async with aiohttp.ClientSession() as session:
            async with session.get(final_url, headers=headers, timeout=60) as res:
                content_type = res.headers.get("Content-Type", "").lower()
                if "application/pdf" not in content_type:
                    if tei_path:
                        print("  - OA URL returned HTML. Extracting full text via BeautifulSoup...")
                        html_content = await res.text()
                        soup = BeautifulSoup(html_content, "html.parser")
                        text = soup.get_text(separator=" ", strip=True)
                        if not is_valid_html_text(text):
                            print("  - HTML fallback rejected due to invalid stub or paywall.")
                            return False
                        xml_content = f'<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/><text><body><div><p>{text}</p></div></body></text></TEI>'
                        with open(tei_path, "w", encoding="utf-8") as f:
                            f.write(xml_content)
                        return "html"
                    return False

                with open(output_path, "wb") as f:
                    async for chunk in res.content.iter_chunked(8192):
                        f.write(chunk)

                if not is_valid_pdf(output_path):
                    print("  - Downloaded file is an invalid PDF or paywall stub. Moving to failed folder.")
                    os.rename(output_path, output_path + ".failed")
                    return False

                print("  - SUCCESS: Downloaded OA PDF.")
                return "pdf"
    except Exception as e:
        print(f"  - Playwright OA download fallback failed: {e}")
        return False
    finally:
        shutil.rmtree(temp_profile_dir, ignore_errors=True)


async def download_pdf_from_url(
    session, pdf_url, output_path, email=None, pmid=None, doi=None, tei_path=None
):
    try:
        async with session.get(pdf_url, headers=get_request_headers(email), timeout=60) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            if "application/pdf" not in content_type:
                print(f"  - Target URL returned {content_type}, trying isolated browser fallback...")
                pw_res = await download_pdf_with_playwright(pdf_url, output_path, tei_path)
                if pw_res:
                    return pw_res

                body = await response.text()
                write_debug_log(pmid, doi, pdf_url, response.status, dict(response.headers), body, Exception("Not PDF"))
                return False

            with open(output_path, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)

            if not is_valid_pdf(output_path):
                print("  - Downloaded file is an invalid PDF or paywall stub. Moving to failed folder.")
                os.rename(output_path, output_path + ".failed")
                return False

            return "pdf"
    except aiohttp.ClientError as e:
        print(f"  - Failed to download PDF from {pdf_url}: {e}")
        pw_res = await download_pdf_with_playwright(pdf_url, output_path, tei_path)
        if pw_res:
            return pw_res
        write_debug_log(pmid, doi, pdf_url, None, None, None, e)
    except Exception as e:
        print(f"  - Unknown Error {pdf_url}: {e}")
    return False


async def process_single_article(session, article, output_dir, email, tei_dir):
    pmid_node = article.find(".//PMID")
    pmid = pmid_node.text if pmid_node is not None else "unknown"
    output_filename = os.path.join(output_dir, f"{pmid}.pdf")

    if os.path.exists(output_filename):
        print(f"  - PDF already exists for {pmid}.")
        return pmid, "Already Downloaded"

    doi_node = article.find(".//ArticleId[@IdType='doi']")
    doi = doi_node.text if doi_node is not None else None
    pmc_node = article.find(".//ArticleId[@IdType='pmc']")
    pmcid = pmc_node.text if pmc_node is not None else None
    tei_path = os.path.join(tei_dir, f"{pmid}.xml") if tei_dir else None

    async with DOWNLOAD_SEMAPHORE:
        # 1. Unpaywall Open Access API
        if doi:
            pdf_url = await get_unpaywall_pdf_url(session, doi, email=email)
            if pdf_url:
                print(f"  - Found Unpaywall OA link for {doi}.")
                res = await download_pdf_from_url(session, pdf_url, output_filename, email, pmid, doi, tei_path)
                if res == "pdf":
                    return pmid, "Downloaded (Unpaywall)"
                elif res == "html":
                    return pmid, "Downloaded (HTML Fallback)"

        # 2. PubMed Central OA Web Service
        if pmcid:
            pdf_url = await get_pmc_oa_pdf_url(session, pmcid=pmcid, email=email)
            if pdf_url:
                print(f"  - Found PMC OA link for {pmcid}.")
                res = await download_pdf_from_url(session, pdf_url, output_filename, email, pmid, doi, tei_path)
                if res == "pdf":
                    return pmid, "Downloaded (PMC)"
                elif res == "html":
                    return pmid, "Downloaded (HTML Fallback)"

        # 3. Europe PMC Open Access REST API
        pdf_url = await get_europe_pmc_pdf_url(session, pmid=pmid, doi=doi, email=email)
        if pdf_url:
            print(f"  - Found Europe PMC OA link for {pmid}.")
            res = await download_pdf_from_url(session, pdf_url, output_filename, email, pmid, doi, tei_path)
            if res == "pdf":
                return pmid, "Downloaded (EuropePMC)"
            elif res == "html":
                return pmid, "Downloaded (HTML Fallback)"

        # 4. Semantic Scholar Open Access link
        paper_id = f"DOI:{doi}" if doi else (f"PMID:{pmid}" if pmid else None)
        if paper_id:
            pdf_url = await get_semantic_scholar_pdf_url(session, paper_id, email=email)
            if pdf_url:
                print(f"  - Found Semantic Scholar OA link for {paper_id}.")
                res = await download_pdf_from_url(session, pdf_url, output_filename, email, pmid, doi, tei_path)
                if res == "pdf":
                    return pmid, "Downloaded (SemanticScholar)"
                elif res == "html":
                    return pmid, "Downloaded (HTML Fallback)"

        # 5. Crossref TDM / OpenAlex Open Access link
        if doi:
            pdf_url = await get_crossref_tdm_pdf_url(session, doi, email=email)
            if pdf_url:
                print(f"  - Found Crossref TDM / OpenAlex OA link for {doi}.")
                res = await download_pdf_from_url(session, pdf_url, output_filename, email, pmid, doi, tei_path)
                if res == "pdf":
                    return pmid, "Downloaded (Crossref TDM)"
                elif res == "html":
                    return pmid, "Downloaded (HTML Fallback)"

        print(f"  - No OA source found for {pmid}. Please use Manual PDF Upload Helper.")
        write_debug_log(pmid, doi, None, None, None, None, Exception("No OA Source Found"))
        return pmid, "No OA Source Found"


async def download_pdfs_async(articles, output_dir, email, tei_dir):
    async with aiohttp.ClientSession() as session:
        tasks = [
            process_single_article(
                session,
                article,
                output_dir,
                email,
                tei_dir,
            )
            for article in articles
        ]
        results = await asyncio.gather(*tasks)
        return dict(results)


def download_pdfs_from_xml(
    xml_path,
    output_dir,
    allowed_pmids=None,
    email=None,
    tei_dir=None,
):
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

    print(f"Attempting to download Open Access PDFs concurrently for {len(articles)} articles...")

    return asyncio.run(
        download_pdfs_async(articles, output_dir, email, tei_dir)
    )
