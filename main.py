import json
import os
import re
import xml.etree.ElementTree as ET  # Added for XML parsing
from datetime import datetime, timedelta

import pandas as pd
import yaml

from src.ingest import downloader, pubmed
from src.llm import client as llm_client
from src.parse import grobid_client, pubmed_parser, tei_parser
from src.report import generator
from src.rob import assessor
from src.screen import screener
from src.utils import data_manager

# Define file paths
DATA_DIR = "data"
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
TABLES_DIR = os.path.join(DATA_DIR, "tables")
TEI_DIR = os.path.join(DATA_DIR, "tei")  # For GROBID output
CONFIG_PATH = "picos_config.yaml"
ASREVIEW_PROJECT_PATH = os.path.join(DATA_DIR, "asreview_project.asreview")  # Define ASReview project path


def check_and_clear_previous_run():
    """Checks for specific data files from a previous run and asks the user if they want to clear them."""
    previous_run_indicator = os.path.join(RAW_DATA_DIR, "articles.xml")

    if os.path.exists(previous_run_indicator):
        print("\n--- 경고: 이전 작업 데이터가 'data' 폴더에 남아있습니다. ---")
        choice = input(
            "새로운 검색을 시작하면 이전 데이터(raw, tables, pdf의 내용)가 삭제됩니다. 계속하시겠습니까? [y/n]: "
        ).lower()
        if choice == "y":
            data_manager.clear_generated_data_files()
            # Also remove the ASReview project file if it exists
            if os.path.exists(ASREVIEW_PROJECT_PATH):
                os.remove(ASREVIEW_PROJECT_PATH)
                print(f"Removed previous ASReview project file: {ASREVIEW_PROJECT_PATH}")
            return True
        else:
            print("작업을 중단합니다.")
            return False
    return True


def load_or_create_picos_config():
    """Loads PICOS configuration from picos_config.yaml or creates it interactively."""
    picos_data = None
    use_existing_file = False

    if os.path.exists(CONFIG_PATH):
        print(f"--- Found existing configuration file: {CONFIG_PATH} ---")
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            existing_config = yaml.safe_load(f)

        print("--- Existing PICOS Configuration ---")
        for key, value in existing_config.get("picos", {}).items():
            if value:
                print(f"- {key.capitalize()}: {value}")

        choice = input("\n이 설정 파일을 사용하시겠습니까? [Y/n]: ").lower()
        if choice == "" or choice == "y":
            use_existing_file = True
            picos_data = existing_config["picos"]

    if not use_existing_file:
        if os.path.exists(CONFIG_PATH):
            print("\n--- Creating new PICOS configuration. ---")
        else:
            print("--- PICOS configuration file not found. Starting interactive setup. ---")

        picos = {}
        picos["population"] = input("> Population을 입력하세요: ")
        picos["intervention"] = input("> Intervention을 입력하세요: ")
        picos["comparison"] = input("> Comparison을 입력하세요: ")
        picos["outcome"] = input("> Outcome을 입력하세요: ")
        picos["study_design"] = input("> (선택) Study Design을 입력하세요 (없으면 Enter): ")

        save_choice = input(f"\n입력하신 내용으로 {CONFIG_PATH} 파일을 생성/덮어쓰시겠습니까? (y/n): ").lower()
        if save_choice == "y":
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.dump({"picos": picos}, f, allow_unicode=True, sort_keys=False)
            print(f"--- Configuration saved to {CONFIG_PATH} ---")

        picos_data = picos

    return picos_data


def construct_search_query(picos):
    """Constructs a PubMed search query from the PICOS elements."""
    query_parts = []

    def format_part(term, field_tag="[tiab]"):
        if not term:
            return None
        if " " in term:
            return f'"{term}"{field_tag}'
        return f"{term}{field_tag}"

    query_parts.append(format_part(picos.get("population")))
    query_parts.append(format_part(picos.get("intervention")))
    query_parts.append(format_part(picos.get("comparison")))
    query_parts.append(format_part(picos.get("outcome")))
    query_parts.append(format_part(picos.get("study_design"), "[pt]"))

    return " AND ".join(filter(None, query_parts))


def setup_directories():
    """Ensures that the necessary data directories exist."""
    os.makedirs(RAW_DATA_DIR, exist_ok=True)
    os.makedirs(TABLES_DIR, exist_ok=True)
    os.makedirs(TEI_DIR, exist_ok=True)


def main():
    """
    Main function to orchestrate the systematic review pipeline.
    """
    print("--- Starting Systematic Review AI Pipeline ---")

    if not check_and_clear_previous_run():
        return

    setup_directories()

    stats = {
        "total_found": 0,
        "screened": 0,
        "excluded": 0,
        "included": 0,
        "retrieved": 0,
    }

    # --- 1. Scoping & Search --- #
    print("\nStep 1: Scoping and Searching")
    picos_config = load_or_create_picos_config()

    print("\n--- Using the following PICOS Configuration for the search ---")
    for key, value in picos_config.items():
        if value:
            print(f"- {key.capitalize()}: {value}")

    search_query = construct_search_query(picos_config)
    print(f"\nConstructed PubMed Query: {search_query}")

    # --- 2. Data Ingestion --- #
    print("\nStep 2: Ingesting data from PubMed")
    proceed = input("Proceed with this query? (y/n): ").lower()
    if proceed != "y":
        print("Pipeline stopped by user.")
        return

    today = datetime.now()
    end_date = today.strftime("%Y/%m/%d")
    start_date = (today - timedelta(days=20 * 365)).strftime("%Y/%m/%d")

    print(f"Searching for articles published between {start_date} and {end_date}.")

    # First call to get total count
    # Use a small max_ret to avoid fetching all PMIDs if not needed
    initial_pmids, total_count = pubmed.fetch_pmids(
        search_query,
        max_ret=1,  # Fetch only 1 to get the total count efficiently
        mindate=start_date,
        maxdate=end_date,
        sort="relevance",  # Sort by relevance instead of date
    )
    stats["total_found"] = total_count

    if total_count == 0:
        print("No articles found. Exiting pipeline.")
        return

    print(f"PubMed에서 총 {total_count}개의 논문이 검색되었습니다.")

    max_ret_user = 0
    while True:
        try:
            user_input = input(f"이 중 몇 개의 논문을 가져오시겠습니까? (최대 {total_count}개, 기본값: 20): ")
            if not user_input:  # Default to 20 if user just presses Enter
                max_ret_user = 20
            else:
                max_ret_user = int(user_input)

            if max_ret_user <= 0:
                print("0보다 큰 숫자를 입력해주세요.")
            elif max_ret_user > total_count:
                print(f"최대 {total_count}개까지 가져올 수 있습니다. 다시 입력해주세요.")
            else:
                break
        except ValueError:
            print("유효한 숫자를 입력해주세요.")

    # Second call to fetch the actual PMIDs based on user's choice
    pmids, _ = pubmed.fetch_pmids(
        search_query,
        max_ret=max_ret_user,
        mindate=start_date,
        maxdate=end_date,
        sort="relevance",  # Sort by relevance instead of date
    )

    if not pmids:  # Should not happen if total_count > 0 and max_ret_user > 0
        print("No articles found after user selection. Exiting pipeline.")
        return

    pmids_df = pd.DataFrame(pmids, columns=["pmid"])

    articles_xml = pubmed.fetch_abstracts(pmids)
    if articles_xml:
        # --- Filter articles by pub_year to exclude future-dated ones --- #
        print("\nFiltering articles by publication year...")
        root = ET.fromstring(articles_xml)
        filtered_articles_elements = []
        current_year = datetime.now().year

        for article in root.findall(".//PubmedArticle"):
            pub_year_node = article.find(".//PubDate/Year")
            pub_year = (
                int(pub_year_node.text) if pub_year_node is not None and pub_year_node.text.isdigit() else current_year + 1
            )  # Default to future if year is missing or invalid

            if pub_year <= current_year:  # Only include articles published up to the current year
                filtered_articles_elements.append(article)

        if not filtered_articles_elements:
            print("No articles found after filtering by publication year. Exiting pipeline.")
            return

        # Reconstruct XML string from filtered elements
        filtered_root = ET.Element("PubmedArticleSet")
        for article_elem in filtered_articles_elements:
            filtered_root.append(article_elem)
        filtered_articles_xml = ET.tostring(filtered_root, encoding="unicode")

        print(f"Filtered to {len(filtered_articles_elements)} articles with pub_year < {current_year}.")
        # --- End Filtering ---

        # Save the raw XML (now filtered)
        xml_path = os.path.join(RAW_DATA_DIR, "articles.xml")
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(filtered_articles_xml)  # Use filtered XML
        print(f"Saved filtered article XML to {xml_path}")

        # Parse XML and save to DB
        print("\nParsing XML and importing to database...")
        parsed_df = pubmed_parser.parse_articles_xml(filtered_articles_xml)
        data_manager.db_manager.import_pubmed_results(parsed_df)

        # --- 2.5 Automated Screening (Title/Abstract) --- #
        print("\nStep 2.5: Automated Screening")
        articles_df = data_manager.db_manager.get_articles_df()
        if not articles_df.empty:
            # Run screening
            screened_df = screener.screen_abstracts(articles_df, picos_config)
            
            # Save screening results to DB
            for idx, row in screened_df.iterrows():
                data_manager.db_manager.update_article(
                    row["pmid"],
                    screening_decision=row.get("screening_decision", ""),
                    screening_reason=row.get("screening_reason", "")
                )
            print(f"Saved screening results to database.")

            # Update stats
            stats["screened"] = len(screened_df)

            # Filter for included articles
            included_df = screened_df[screened_df["screening_decision"] == "Included"]
            included_pmids = included_df["pmid"].astype(str).tolist()

            stats["included"] = len(included_df)
            stats["excluded"] = stats["screened"] - stats["included"]

            print(f"Screening Result: {len(included_df)} included out of {len(screened_df)} total.")

            if not included_pmids:
                print("No articles met the inclusion criteria. Exiting pipeline.")
                # Generate report even if no included articles to show the exclusion flow
                report_path = os.path.join(DATA_DIR, "report.md")
                generator.generate_report(stats, picos_config, report_path)
                return


        # --- 3. PDF Downloading --- #
        print("\nStep 3: Downloading PDFs for Included Articles")
        pdf_dir = os.path.join(DATA_DIR, "pdf")

        # Pass included_pmids to filter downloads
        pdf_download_status = downloader.download_pdfs_from_xml(xml_path, pdf_dir, allowed_pmids=included_pmids)

        # Update database with PDF download status
        print("\nUpdating database with PDF download status...")
        try:
            for pmid, status in pdf_download_status.items():
                data_manager.db_manager.update_article(pmid, pdf_download_status=status)
            print("Updated database with PDF download status.")
        except Exception as e:
            print(f"Error updating database with PDF download status: {e}")

        # --- 3.5. Parse PDFs with GROBID --- #
        print("\nStep 3.5: Parsing PDFs with GROBID")
        # Find successfully downloaded PDFs
        downloaded_pdfs = [
            k
            for k, v in pdf_download_status.items()
            if v == "Downloaded" or v == "Already Downloaded" or v == "Downloaded (Unpaywall)" or v == "Downloaded (PMC)"
        ]
        stats["retrieved"] = len(downloaded_pdfs)

        if not downloaded_pdfs:
            print("No downloaded PDFs to process with GROBID.")
        else:
            print(f"Found {len(downloaded_pdfs)} PDFs to process.")
            for pmid in downloaded_pdfs:
                pdf_path = os.path.join(pdf_dir, f"{pmid}.pdf")
                if os.path.exists(pdf_path):
                    tei_xml = grobid_client.process_pdf(pdf_path)
                    if tei_xml:
                        tei_path = os.path.join(TEI_DIR, f"{pmid}.xml")
                        try:
                            with open(tei_path, "w", encoding="utf-8") as f:
                                f.write(tei_xml)
                            print(f"  - Saved TEI XML to {tei_path}")
                        except Exception as e:
                            print(f"  - Error saving TEI XML for {pmid}: {e}")

        # --- 3.6. Risk of Bias Assessment --- #
        print("\nStep 3.6: Automated Risk of Bias Assessment")
        # Check if we have TEI files
        if os.path.exists(TEI_DIR) and os.listdir(TEI_DIR):
            for _ in assessor.batch_assess_rob(TEI_DIR):
                pass # The generator yields progress, we need to consume it
        else:
            print("No TEI files found. Skipping RoB assessment.")

    # --- 5. Data Extraction & LLM Summarization ---
    print("\nStep 5: Data Extraction and Summarization")

    llm = llm_client.LLMClient()
    if not llm.get_completion(
        [
            {"role": "system", "content": "Respond with OK if you are ready."},
            {"role": "user", "content": "Are you ready?"},
        ]
    ):
        print("LLM client is not connected. Skipping data extraction.")
        print("\n--- Pipeline Scaffolding Complete ---")
        return

    print("LLM client is connected. Starting data extraction...")

    tei_files = []
    if os.path.exists(TEI_DIR):
        tei_files = [os.path.join(TEI_DIR, f) for f in os.listdir(TEI_DIR) if f.endswith(".xml")]

    if not tei_files:
        print("No TEI XML files found to extract data from.")
    else:
        extracted_data = []

        for tei_path in tei_files:
            pmid = os.path.basename(tei_path).replace(".xml", "")
            print(f"\n--- Processing article PMID: {pmid} ---")

            full_text = tei_parser.extract_text_from_tei(tei_path)

            if not full_text:
                print("  - Could not extract text from TEI file. Skipping.")
                continue

            # Prepare the prompt for the LLM
            # Using a simplified text snippet for brevity in the prompt
            text_snippet = (full_text[:8000] + "...") if len(full_text) > 8000 else full_text

            print("  - Sending text to LLM for multi-agent PICO extraction...")
            from src.extract import pico_extractor
            
            extracted = pico_extractor.extract_pico_multi_agent(text_snippet)
            if extracted:
                print("  - Received response from LLM.")
                extracted["pmid"] = pmid  # Add pmid for reference
                extracted_data.append(extracted)
                print(f"  - Successfully extracted: {extracted}")
            else:
                print(f"  - No response from LLM for {pmid}.")

        if extracted_data:
            # Save the extracted data to the database
            for pico_data in extracted_data:
                pmid = pico_data["pmid"]
                pico_json = json.dumps(pico_data, ensure_ascii=False)
                data_manager.db_manager.update_article(pmid, pico_data=pico_json)
            print(f"\nSaved all extracted PICO data to database.")

    # --- 7. Reporting ---
    print("\nStep 7: Generating Final Report")
    report_path = os.path.join(DATA_DIR, "report.md")
    generator.generate_report(stats, picos_config, report_path)

    print("\n--- Project Enhancements Complete---")
    print(f"See {report_path} for the systematic review summary.")


if __name__ == "__main__":
    main()
