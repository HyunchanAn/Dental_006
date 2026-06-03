import asyncio
import datetime
import json
import os
import time
import xml.etree.ElementTree as ET

import requests

from .scihub_fallback import SciHubDownloader


def get_request_headers(email=None):
    """
    Constructs HTTP headers with a randomized modern User-Agent to bypass simple WAF rules,
    and includes modern browser hints.
    """
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


def get_unpaywall_pdf_url(doi, email=None):
    """
    Queries the Unpaywall API to find a direct PDF link for a given DOI.
    """
    if not doi:
        return None
    try:
        # Using a more compliant email address as recommended by Unpaywall
        contact_email = email if email else "systematic-reviewer-ai@example.com"
        url = f"https://api.unpaywall.org/v2/{doi}?email={contact_email}"

        # We don't strictly need custom headers for Unpaywall based on their docs (just email param),
        # but good practice to identify anyway.
        response = requests.get(url, headers=get_request_headers(email), timeout=20)
        response.raise_for_status()
        data = response.json()

        if data.get("best_oa_location") and data["best_oa_location"].get("url_for_pdf"):
            return data["best_oa_location"]["url_for_pdf"]
    except requests.exceptions.RequestException:
        # This is expected for non-existent DOIs, so we don't need to be too loud.
        pass
    except Exception as e:
        print(f"  - An unexpected error occurred while processing DOI {doi} with Unpaywall: {e}")
    return None


def get_semantic_scholar_pdf_url(paper_id, email=None):
    """
    Queries the Semantic Scholar API to find a direct PDF link.
    paper_id can be DOI (e.g., 'DOI:10.1038/nature12345') or PMID (e.g., 'PMID:12345').
    """
    if not paper_id:
        return None
    try:
        # Semantic Scholar API endpoint for paper details
        url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}?fields=openAccessPdf"

        response = requests.get(url, headers=get_request_headers(email), timeout=20)
        if response.status_code == 200:
            data = response.json()
            oa_pdf = data.get("openAccessPdf")
            if oa_pdf and oa_pdf.get("url"):
                return oa_pdf["url"]
    except Exception as e:
        print(f"  - Error querying Semantic Scholar for {paper_id}: {e}")
    return None


def write_debug_log(pmid, doi, url, response, exception=None):
    """
    Writes a debug log in JSON format for a failed PDF download attempt.
    """
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "logs")
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    pmid_str = str(pmid) if pmid else "unknown"
    log_filename = os.path.join(log_dir, f"download_fail_{pmid_str}_{timestamp}.json")

    headers = {}
    status_code = None
    body_snippet = ""
    anti_bot_signs = []

    if response is not None:
        headers = dict(response.request.headers) if hasattr(response, "request") and response.request else {}
        status_code = response.status_code
        try:
            body_snippet = response.text[:1000]
            lower_body = response.text.lower()
            if "access denied" in lower_body:
                anti_bot_signs.append("Access Denied")
            if "cloudflare" in lower_body:
                anti_bot_signs.append("Cloudflare")
            if "captcha" in lower_body:
                anti_bot_signs.append("Captcha")
            if "just a moment" in lower_body:
                anti_bot_signs.append("Just a moment")
        except Exception:
            body_snippet = "Could not decode body"

    proxy_used = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or "None"

    log_data = {
        "target_identifiers": {"pmid": pmid, "doi": doi, "url": url},
        "network_context": {
            "request_headers": headers,
            "user_agent": headers.get("User-Agent", "Unknown"),
            "proxy_vpn_used": proxy_used,
        },
        "http_status": {"status_code": status_code, "body_snippet": body_snippet},
        "anti_bot_sign": {"detected_signs": anti_bot_signs, "has_anti_bot": len(anti_bot_signs) > 0},
        "exception": str(exception) if exception else None,
    }

    try:
        with open(log_filename, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=4)
        print(f"  - Debug log written to {log_filename}")
    except Exception as e:
        print(f"  - Failed to write debug log: {e}")


def download_pdf_with_playwright(pdf_url, output_path):
    """
    Fallback downloader using Playwright Headless Browser to bypass WAF, Cloudflare and Meta redirects.
    """
    try:
        from playwright.sync_api import sync_playwright
        from playwright_stealth import stealth_sync
    except ImportError:
        print("  - Playwright or stealth not installed, skipping advanced fallback.")
        return False

    print(f"  - Using Playwright Headless Browser for {pdf_url}...")
    try:
        with sync_playwright() as p:
            # We use chromium
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            )
            page = context.new_page()

            # Apply stealth to bypass bot detection
            stealth_sync(page)

            # Setup route to intercept the PDF download if it triggers automatically
            # Or just goto the URL and wait for PDF
            try:
                # Wait until network is mostly idle to let JS redirects happen
                page.goto(pdf_url, wait_until="networkidle", timeout=30000)
            except Exception:
                # Might throw if it navigates to a PDF directly in some versions
                pass

            # If the current URL is a PDF or if there is a PDF viewer, we can just fetch the current page url
            # But the best way to get a PDF from a page is to use the request context to fetch the final URL.
            final_url = page.url

            # Some publishers render the PDF using pdf.js, so we grab the content if it's application/pdf
            # Actually, `page.goto` response might be the PDF
            # A more robust way to download the PDF using the browser context:
            cookies = context.cookies()
            cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Cookie": cookie_str,
            }

            browser.close()

        # Re-try the final URL with requests using the cookies obtained by playwright
        res = requests.get(final_url, headers=headers, stream=True, timeout=60)
        res.raise_for_status()

        if "application/pdf" not in res.headers.get("Content-Type", "").lower():
            return False

        with open(output_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=8192):
                f.write(chunk)
        print("  - SUCCESS: Downloaded PDF via Playwright session.")
        return True
    except Exception as e:
        print(f"  - Playwright fallback failed: {e}")
        return False


def download_pdf_from_url(pdf_url, output_path, email=None, pmid=None, doi=None):
    """
    Downloads a PDF from a URL and saves it to the specified path.
    """
    # 1. URL Parsing Rule Update (Angle Orthodontist)
    if "angle.org/doi/pdf" in pdf_url:
        pdf_url = pdf_url.replace("www.angle.org/doi/pdf", "meridian.allenpress.com/angle-orthodontist/article-pdf")

    response = None
    try:
        response = requests.get(pdf_url, headers=get_request_headers(email), stream=True, timeout=60)
        response.raise_for_status()

        # Sometimes it returns HTML instead of PDF
        if "application/pdf" not in response.headers.get("Content-Type", "").lower():
            # If standard request returns HTML (possibly WAF or redirect), try playwright fallback
            print(f"  - Target URL returned {response.headers.get('Content-Type')}, trying Playwright fallback...")
            if download_pdf_with_playwright(pdf_url, output_path):
                return True

            write_debug_log(pmid, doi, pdf_url, response, Exception("Content-Type is not application/pdf"))
            return False

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except requests.exceptions.RequestException as e:
        print(f"  - Failed to download PDF from {pdf_url}: {e}")
        # If it failed due to 403 or other WAF rules, attempt Playwright fallback
        if response and response.status_code in [403, 404, 429, 503]:
            print("  - Received HTTP Error. Attempting Playwright fallback...")
            if download_pdf_with_playwright(pdf_url, output_path):
                return True
        write_debug_log(pmid, doi, pdf_url, response, e)
    return False


def download_pdfs_from_xml(xml_path, output_dir, allowed_pmids=None, email=None, enable_scihub_fallback=False):
    """
    Parses a PubMed XML file, extracts DOIs and PMCIDs, and attempts to download open-access PDFs
    using a fallback strategy (Unpaywall -> PMC).

    Args:
        xml_path (str): Path to the PubMed XML file.
        output_dir (str): Directory to save downloaded PDFs.
        allowed_pmids (list, optional): List of PMIDs to download. If provided, only articles
                                        with PMIDs in this list will be processed.
        email (str, optional): User email for API headers.

    Returns:
        dict: A dictionary of PMID to download status.
    """
    os.makedirs(output_dir, exist_ok=True)

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"Error: Failed to parse XML file at {xml_path}. {e}")
        return {}

    articles = root.findall(".//PubmedArticle")
    total_found_xml = len(articles)

    # Filter articles if allowed_pmids is provided
    if allowed_pmids is not None:
        allowed_pmids_set = set(str(p) for p in allowed_pmids)
        articles_to_process = []
        for article in articles:
            pmid_node = article.find(".//PMID")
            pmid = pmid_node.text if pmid_node is not None else None
            if pmid and pmid in allowed_pmids_set:
                articles_to_process.append(article)
        articles = articles_to_process
        print(f"Filtered XML from {total_found_xml} to {len(articles)} articles based on screening results.")

    total_articles = len(articles)
    if total_articles == 0:
        return {}

    print(
        f"Attempting to download PDFs for {total_articles} articles using fallback strategy (Unpaywall -> SemanticScholar -> SciHub)..."
    )
    download_status = {}
    download_count = 0

    scihub_downloader = SciHubDownloader() if enable_scihub_fallback else None

    for i, article in enumerate(articles):
        pmid_node = article.find(".//PMID")
        pmid = pmid_node.text if pmid_node is not None else f"unknown_{i + 1}"
        print(f"\n[{i + 1}/{total_articles}] Processing PMID: {pmid}")

        output_filename = os.path.join(output_dir, f"{pmid}.pdf")
        if os.path.exists(output_filename):
            print("  - PDF already exists.")
            download_status[pmid] = "Already Downloaded"
            download_count += 1
            continue

        downloaded = False

        # --- Strategy 1: Try Unpaywall ---
        doi_node = article.find(".//ArticleId[@IdType='doi']")
        doi = doi_node.text if doi_node is not None else None
        if doi:
            pdf_url = get_unpaywall_pdf_url(doi, email=email)
            if pdf_url:
                print(f"  - Found Unpaywall OA link for DOI {doi}. Attempting download...")
                if download_pdf_from_url(pdf_url, output_filename, email=email, pmid=pmid, doi=doi):
                    download_status[pmid] = "Downloaded (Unpaywall)"
                    downloaded = True
                else:
                    download_status[pmid] = "Download Failed (Unpaywall)"

        # --- Strategy 2: Try Semantic Scholar (if Unpaywall failed) ---
        if not downloaded:
            # Try by DOI first, then by PMID
            paper_id = f"DOI:{doi}" if doi else (f"PMID:{pmid}" if pmid else None)
            if paper_id:
                pdf_url = get_semantic_scholar_pdf_url(paper_id, email=email)
                if pdf_url:
                    print(f"  - Found Semantic Scholar OA link for {paper_id}. Attempting download...")
                    if download_pdf_from_url(pdf_url, output_filename, email=email, pmid=pmid, doi=doi):
                        download_status[pmid] = "Downloaded (SemanticScholar)"
                        downloaded = True

        # --- Strategy 3: Try Sci-Hub Direct Fallback (if enabled and others failed) ---
        if not downloaded and enable_scihub_fallback and doi:
            downloaded = asyncio.run(scihub_downloader.download_by_doi(doi, output_filename))
            if downloaded:
                download_status[pmid] = "Downloaded (Sci-Hub)"

        if not downloaded:
            print("  - No open access source found via Unpaywall, Semantic Scholar, or Sci-Hub.")
            download_status[pmid] = "No OA Source Found"
            write_debug_log(pmid, doi, None, None, Exception("No OA Source Found via Unpaywall, Semantic Scholar, or Sci-Hub"))

        if downloaded:
            download_count += 1

        time.sleep(1)  # Be polite to APIs

    print(f"\nPDF 다운로드 시도 완료: 총 {total_articles}개 중 {download_count}개 성공 또는 이미 존재.")
    return download_status


if __name__ == "__main__":
    # This allows the script to be run directly for testing purposes.
    current_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    xml_file_path = os.path.join(project_root, "data", "raw", "articles.xml")
    pdf_output_dir = os.path.join(project_root, "data", "pdf")

    if not os.path.exists(xml_file_path):
        print(f"Error: XML file not found at {xml_file_path}")
        print("Please run main.py first to generate the articles.xml file.")
    else:
        download_pdfs_from_xml(xml_file_path, pdf_output_dir)
