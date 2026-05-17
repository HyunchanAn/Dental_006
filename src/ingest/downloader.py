import os
import time
import xml.etree.ElementTree as ET

import requests


def get_request_headers(email=None):
    """
    Constructs HTTP headers with User-Agent and Email contact info.
    """
    contact = email if email else "systematic-reviewer-ai@example.com"
    return {"User-Agent": f"SystematicReviewerAI/1.0 (mailto:{contact})", "Email": contact}


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


def download_pdf_from_url(pdf_url, output_path, email=None):
    """
    Downloads a PDF from a URL and saves it to the specified path.
    """
    try:
        response = requests.get(pdf_url, headers=get_request_headers(email), stream=True, timeout=60)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except requests.exceptions.RequestException as e:
        print(f"  - Failed to download PDF from {pdf_url}: {e}")
    return False


def try_pmc_download(pmcid, output_path, email=None, timeout=60):
    """
    Attempts to download a PDF directly from PubMed Central using its PMCID.
    """
    if not pmcid:
        return False

    print(f"  - Trying PubMed Central with PMCID: {pmcid}")
    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {"db": "pmc", "id": pmcid, "rettype": "pdf", "retmode": "binary"}
    try:
        response = requests.post(fetch_url, data=params, headers=get_request_headers(email), stream=True, timeout=timeout)

        if "application/pdf" not in response.headers.get("Content-Type", ""):
            print(f"  - PMC did not return a PDF. Content-Type: {response.headers.get('Content-Type')}")
            return False

        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("  - SUCCESS: Downloaded PDF from PMC.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  - Failed to download from PMC: {e}")
        return False


def download_pdfs_from_xml(xml_path, output_dir, allowed_pmids=None, email=None):
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

    print(f"Attempting to download PDFs for {total_articles} articles using fallback strategy (Unpaywall -> PMC)...")
    download_status = {}
    download_count = 0

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
                if download_pdf_from_url(pdf_url, output_filename, email=email):
                    download_status[pmid] = "Downloaded (Unpaywall)"
                    downloaded = True
                else:
                    download_status[pmid] = "Download Failed (Unpaywall)"

        # --- Strategy 2: Try PubMed Central (if Unpaywall failed) ---
        if not downloaded:
            pmc_node = article.find(".//ArticleId[@IdType='pmc']")
            pmcid = pmc_node.text if pmc_node is not None else None
            if pmcid:
                if try_pmc_download(pmcid, output_filename, email=email):
                    download_status[pmid] = "Downloaded (PMC)"
                    downloaded = True

        # --- Strategy 3: Try Semantic Scholar (if others failed) ---
        if not downloaded:
            # Try by DOI first, then by PMID
            paper_id = f"DOI:{doi}" if doi else (f"PMID:{pmid}" if pmid else None)
            if paper_id:
                pdf_url = get_semantic_scholar_pdf_url(paper_id, email=email)
                if pdf_url:
                    print(f"  - Found Semantic Scholar OA link for {paper_id}. Attempting download...")
                    if download_pdf_from_url(pdf_url, output_filename, email=email):
                        download_status[pmid] = "Downloaded (SemanticScholar)"
                        downloaded = True

        if not downloaded:
            print("  - No open access source found via Unpaywall, PMC, or Semantic Scholar.")
            download_status[pmid] = "No OA Source Found"

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
