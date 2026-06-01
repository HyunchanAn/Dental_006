import os

# Import existing modules
# We need to add the project root to sys.path if it's not already there for imports to work
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
import yaml

sys.path.append(os.getcwd())

from src.ingest import downloader, pubmed
from src.llm import synthesizer
from src.parse import grobid_client, pubmed_parser, tei_parser
from src.rob import assessor
from src.screen import screener
from src.utils import data_manager, db_manager, versioning

# --- Configuration & Setup ---
DATA_DIR = "data"
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
TABLES_DIR = os.path.join(DATA_DIR, "tables")
TEI_DIR = os.path.join(DATA_DIR, "tei")
PDF_DIR = os.path.join(DATA_DIR, "pdf")
CONFIG_PATH = "picos_config.yaml"

# Ensure directories exist
os.makedirs(RAW_DATA_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)
os.makedirs(TEI_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)

st.set_page_config(page_title="Systematic Reviewer AI", layout="wide")


# --- Helper Functions ---
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f).get("picos", {})
    return {}


def save_config(picos_data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump({"picos": picos_data}, f, allow_unicode=True, sort_keys=False)


def construct_search_query(picos):
    query_parts = []

    def format_part(term, field_tag="[tiab]"):
        if not term:
            return None
        term = term.strip()
        # If term already contains field tags or boolean operators, assume it's a raw query
        if "[" in term and "]" in term:
            return f"({term})"
        if " OR " in term or " AND " in term:
            return f"({term})"

        # Default behavior for simple terms
        if " " in term:
            return f'"{term}"{field_tag}'
        return f"{term}{field_tag}"

    query_parts.append(format_part(picos.get("population")))
    query_parts.append(format_part(picos.get("intervention")))
    query_parts.append(format_part(picos.get("comparison")))
    query_parts.append(format_part(picos.get("outcome")))
    query_parts.append(format_part(picos.get("study_design"), "[pt]"))
    return " AND ".join(filter(None, query_parts))


# --- Translations ---
TRANSLATIONS = {
    "EN": {
        "title": "🤖 Systematic Reviewer AI",
        "subtitle": "Automate your systematic review pipeline with local AI.",
        "project_data": "Project & Data",
        "reset_data": "🗑️ Reset All Data",
        "reset_success": "Data cleared!",
        "current_config": "Current Config",
        "language": "Language",
        "tabs": [
            "🔍 1. Search (PICO)",
            "👀 2. Screening",
            "⚙️ 3. Analysis Pipeline",
            "📊 4. Report",
        ],
        "step1_header": "Step 1: Scoping and Search Strategy",
        "save_config": "💾 Save Configuration & Generate Query",
        "config_saved": "Configuration saved!",
        "generated_query": "Generated PubMed Query",
        "max_articles": "Max Articles to Retrieve",
        "search_button": "🚀 Search PubMed",
        "searching": "Searching PubMed...",
        "total_found": "Total articles found: {count}. Retrieving top {max}...",
        "retrieval_success": "Successfully retrieved and parsed {count} articles!",
        "no_articles": "No articles found matching the criteria.",
        "search_first": "No articles found. Please run the search in Step 1 first.",
        "step2_header": "Step 2: Automated Screening",
        "start_screening": "🤖 Start Automated Screening",
        "screening_progress": "AI is screening titles and abstracts...",
        "screening_results": "Screening Results",
        "inclusion_rate": "Inclusion Rate",
        "step3_header": "Step 3: Processing Pipeline",
        "step3_desc": "This step will perform PDF Download, Parsing, RoB Assessment, and Data Extraction.",
        "screen_first_warning": "Please complete screening in Step 2 first.",
        "no_included": "No included articles to process.",
        "download_section": "1. PDF Download",
        "analysis_section": "2. Analysis Pipeline",
        "download_btn": "📥 Start PDF Download",
        "analysis_btn": "⚙️ Start Analysis (Parse, RoB, Extract)",
        "download_complete": "Download complete! Check for missing files.",
        "analysis_ready": "Ready for analysis: {count} PDF(s).",
        "analysis_complete": "Analysis complete.",
        "ai_proposal_warning": "⚠️ Note: All RoB assessments and data extractions are AI-generated 'suggestions'. Please verify them for academic rigour.",
        "step4_header": "Step 4: Final Report",
        "generate_report": "📄 Generate Report",
        "report_generated": "Report generated!",
        "download_report": "Download Report (MD)",
        "population": "Population",
        "intervention": "Intervention",
        "comparison": "Comparison",
        "outcome": "Outcome",
        "study_design": "Study Design",
        "manual_helper_title": "👇 Manual Download Helper (Batch of 5)",
        "download_failed_warning": "⚠️ {count} PDF(s) failed to download. Please download manually.",
        "resume_pipeline_btn": "🔄 Resume Pipeline (Process Manual/Fixed Files)",
        "prev_page": "<< Previous",
        "next_page": "Next >>",
        "check_file_btn": "Check File",
        "skip_file_btn": "Skip",
        "file_verified": "Verified {pmid}!",
        "file_skipped": "Skipped {pmid}.",
        "file_not_found": "File not found: {path}",
        "upload_pdf": "Upload PDF",
        "search_scholar": "Search Scholar",
        "search_doi": "Search DOI",
        "search_scihub": "Sci-Hub",
        "copy_filename": "Copy Filename",
        "status_failed": "❌ Download Failed",
        "status_manual": "📂 Manual Detected",
        "status_verified": "✅ Verified",
        "bulk_upload_title": "📤 Bulk PDF Upload (Auto-matching)",
        "bulk_upload_desc": "Upload multiple PDFs. PMID (8 digits) will be automatically detected from filenames.",
        "match_success": "✅ Matched {pmid} from {filename}",
        "match_failed": "⚠️ Could not find PMID in {filename}",
        "view_pubmed": "PubMed",
    },
    "KO": {
        "title": "🤖 체계적 문헌고찰 AI",
        "subtitle": "로컬 AI로 체계적 문헌고찰 파이프라인을 자동화하세요.",
        "project_data": "프로젝트 및 데이터",
        "reset_data": "🗑️ 모든 데이터 초기화",
        "reset_success": "데이터가 초기화되었습니다!",
        "current_config": "현재 설정",
        "language": "언어 / Language",
        "tabs": [
            "🔍 1. 검색 (PICO)",
            "👀 2. 스크리닝",
            "⚙️ 3. 분석 파이프라인",
            "📊 4. 보고서",
        ],
        "step1_header": "1단계: 범위 설정 및 검색 전략",
        "save_config": "💾 설정 저장 및 쿼리 생성",
        "config_saved": "설정이 저장되었습니다!",
        "generated_query": "생성된 PubMed 쿼리",
        "max_articles": "가져올 최대 논문 수",
        "search_button": "🚀 PubMed 검색",
        "searching": "PubMed 검색 중...",
        "total_found": "총 {count}개의 논문 발견. 상위 {max}개 가져오는 중...",
        "retrieval_success": "{count}개의 논문을 성공적으로 가져오고 파싱했습니다!",
        "no_articles": "조건에 맞는 논문을 찾을 수 없습니다.",
        "search_first": "논문이 없습니다. 1단계에서 검색을 먼저 실행해주세요.",
        "step2_header": "2단계: 자동 스크리닝",
        "start_screening": "🤖 자동 스크리닝 시작",
        "screening_progress": "AI가 제목과 초록을 스크리닝하고 있습니다...",
        "screening_results": "스크리닝 결과",
        "inclusion_rate": "포함 비율",
        "step3_header": "3단계: 처리 파이프라인",
        "step3_desc": "이 단계에서는 PDF 다운로드, 파싱, 비뚤림 위험(RoB) 평가, 데이터 추출을 수행합니다.",
        "screen_first_warning": "2단계에서 스크리닝을 먼저 완료해주세요.",
        "no_included": "처리를 진행할 포함된 논문이 없습니다.",
        "download_section": "1. PDF 다운로드 / Download",
        "analysis_section": "2. 분석 파이프라인 / Analysis",
        "download_btn": "📥 PDF 다운로드 시작",
        "analysis_btn": "⚙️ 분석 시작 (파싱, RoB, 추출)",
        "download_complete": "다운로드 완료! 누락된 파일을 확인하세요.",
        "analysis_ready": "분석 준비 완료: {count}개의 PDF 파일.",
        "analysis_complete": "분석이 완료되었습니다.",
        "ai_proposal_warning": "⚠️ 주의: 모든 비뚤림 위험(RoB) 평가 및 데이터 추출 결과는 AI가 생성한 '제안'입니다. 학술적 엄밀성을 위해 반드시 최종 검토를 거쳐주세요.",
        "step4_header": "4단계: 최종 보고서",
        "generate_report": "📄 보고서 생성",
        "report_generated": "보고서가 생성되었습니다!",
        "download_report": "보고서 다운로드 (MD)",
        "population": "연구 대상(Population)",
        "intervention": "중재(Intervention)",
        "comparison": "비교(Comparison)",
        "outcome": "결과(Outcome)",
        "study_design": "연구 설계(Study Design)",
        "manual_helper_title": "👇 수동 다운로드 도우미 (5개씩 보기)",
        "download_failed_warning": "⚠️ {count}개의 PDF 다운로드 실패. 수동 다운로드가 필요합니다.",
        "resume_pipeline_btn": "🔄 획득한 파일로 분석 재개",
        "prev_page": "<< 이전 페이지",
        "next_page": "다음 페이지 >>",
        "check_file_btn": "파일 확인",
        "skip_file_btn": "건너뛰기 (Skip)",
        "file_verified": "{pmid} 파일 확인 완료!",
        "file_skipped": "{pmid} 건너뜀.",
        "file_not_found": "파일을 찾을 수 없습니다: {path}",
        "upload_pdf": "PDF 업로드",
        "search_scholar": "Google Scholar",
        "search_doi": "DOI 검색",
        "search_scihub": "Sci-Hub",
        "copy_filename": "파일명 복사",
        "status_failed": "❌ 다운로드 실패",
        "status_manual": "📂 수동 파일 감지",
        "status_verified": "✅ 확인됨",
        "bulk_upload_title": "📤 일괄 PDF 업로드 (자동 매칭)",
        "bulk_upload_desc": "여러 PDF 파일을 한꺼번에 업로드하세요. 파일명에서 8자리 PMID를 자동 추출합니다.",
        "match_success": "✅ {filename} -> PMID {pmid} 매칭 완료",
        "match_failed": "⚠️ {filename}에서 PMID를 추출하지 못했습니다.",
        "view_pubmed": "PubMed",
    },
}


def t(key, **kwargs):
    lang = st.session_state.get("lang", "KO")  # Default to Korean as requested
    text = TRANSLATIONS[lang].get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text


def init_session_state():
    if "stats" not in st.session_state:
        st.session_state["stats"] = {
            "total_found": 0,
            "screened": 0,
            "excluded": 0,
            "included": 0,
            "retrieved": 0,
        }
    if "picos" not in st.session_state:
        st.session_state["picos"] = load_config()
    if "lang" not in st.session_state:
        # Default language logic could be improved, but sticking to KO default as requested
        st.session_state["lang"] = "KO"
    if "current_tab_index" not in st.session_state:
        st.session_state["current_tab_index"] = 0
    if "failed_pdfs_page" not in st.session_state:
        st.session_state["failed_pdfs_page"] = 0
    if "file_cache" not in st.session_state:
        st.session_state["file_cache"] = {}


def handle_bulk_upload(uploaded_files, df, csv_path):
    import re

    from pypdf import PdfReader

    success_count = 0
    results = []

    for uploaded_file in uploaded_files:
        filename = uploaded_file.name
        # Search for 8-digit PMID in filename
        match = re.search(r"(\d{8})", filename)
        if match:
            pmid = match.group(1)
            target_path = os.path.join(PDF_DIR, f"{pmid}.pdf")

            # Check if this PMID is in our database
            if pmid in df["pmid"].astype(str).values:
                # Pre-flight Check: Validate PDF structure
                try:
                    reader = PdfReader(uploaded_file)
                    num_pages = len(reader.pages)
                    if num_pages > 0:
                        # Validation passed, save the file
                        uploaded_file.seek(0)
                        with open(target_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())

                        df.loc[df["pmid"].astype(str) == pmid, "pdf_download_status"] = "Downloaded (Bulk Match)"
                        success_count += 1
                        results.append(t("match_success", filename=filename, pmid=pmid))
                        # Update session state cache immediately
                        st.session_state["file_cache"][f"exists_{pmid}"] = True
                    else:
                        results.append(f"⚠️ {filename}: 유효하지 않은 PDF입니다 (페이지 없음).")
                except Exception as e:
                    results.append(f"⚠️ {filename}: PDF 파싱 실패 (손상된 파일) - {e}")
            else:
                results.append(f"⚠️ {filename}: PMID {pmid} not found in project.")
        else:
            results.append(t("match_failed", filename=filename))

    if success_count > 0:
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    return results, success_count


def next_step():
    st.session_state["current_tab_index"] += 1
    st.rerun()


# --- Main App Interface ---
def main():
    init_session_state()
    vm = versioning.VersionManager(DATA_DIR)

    # Language Selector in Sidebar (First item)
    with st.sidebar:
        st.session_state["lang"] = st.radio(
            "언어 / Language",
            ["KO", "EN"],
            index=0 if st.session_state["lang"] == "KO" else 1,
            horizontal=True,
        )
        st.divider()

        # Email & API Key Input
        st.subheader("API Settings")
        email_input = st.text_input(
            "Email (Required for NCBI)",
            value=st.session_state["picos"].get("email", ""),
        )
        api_key_input = st.text_input(
            "NCBI API Key (Optional)",
            value=st.session_state["picos"].get("api_key", ""),
            type="password",
        )

        if email_input != st.session_state["picos"].get("email", "") or api_key_input != st.session_state["picos"].get(
            "api_key", ""
        ):
            st.session_state["picos"]["email"] = email_input
            st.session_state["picos"]["api_key"] = api_key_input
            save_config(st.session_state["picos"])
            st.toast("Settings saved!", icon="💾")
        st.divider()

    st.title(t("title"))
    st.markdown(t("subtitle"))

    # --- Sidebar Content ---
    with st.sidebar:
        # Mode Selector
        st.subheader("실행 모드 / Run Mode")
        mode_val = st.radio(
            "Mode",
            ["Human-in-the-Loop Mode", "Full AI-driven Scoping Mode"],
            index=0 if st.session_state.get("run_mode", "hitl") == "hitl" else 1,
            label_visibility="collapsed",
        )
        st.session_state["run_mode"] = "scoping" if "Scoping" in mode_val else "hitl"

        if st.session_state["run_mode"] == "scoping":
            st.warning(
                "⚠️ **예비 타당성 검토 모드**\n\n본 모드는 예비 연구 기획 및 문헌 탐색(Scoping) 목적으로만 제한됩니다. LLM 추론 특성상 누락이나 환각이 포함될 수 있으므로, 실제 정밀 임상 연구 및 학술지 출판물(Publication) 데이터로의 직접적인 인용 및 활용을 절대 금지합니다."
            )
            st.session_state["scoping_agreed"] = st.checkbox(
                "위 경고사항을 확인했으며, 동의합니다.", value=st.session_state.get("scoping_agreed", False)
            )
        st.divider()

        st.header(t("project_data"))
        if st.button(t("reset_data"), type="primary"):
            data_manager.clear_generated_data_files()
            st.session_state["stats"] = {
                "total_found": 0,
                "screened": 0,
                "excluded": 0,
                "included": 0,
                "retrieved": 0,
            }
            st.success(t("reset_success"))
            time.sleep(1)
            st.rerun()

        st.divider()
        st.subheader(t("current_config"))
        st.json(st.session_state["picos"])

    # --- Navigation ---
    tabs_labels = t("tabs")

    # helper for radio button
    def update_tab_index():
        # Find which label was selected
        selected_label = st.session_state["nav_radio"]
        # Update index mapping
        st.session_state["current_tab_index"] = tabs_labels.index(selected_label)

    # If index changed programmatically (e.g. Next button), sync radio
    if "nav_radio" not in st.session_state:
        st.session_state["nav_radio"] = tabs_labels[0]

    # Ensure radio state matches current_tab_index (if button changed it)
    if st.session_state["current_tab_index"] < len(tabs_labels):
        st.session_state["nav_radio"] = tabs_labels[st.session_state["current_tab_index"]]

    st.radio(
        "",
        tabs_labels,
        key="nav_radio",
        horizontal=True,
        on_change=update_tab_index,
        label_visibility="collapsed",
    )
    st.divider()

    current_tab = st.session_state["current_tab_index"]

    # --- Tab 1: PICO & Search ---
    if current_tab == 0:
        st.header(t("step1_header"))

        # --- AI PICO Extraction ---
        st.subheader("🤖 AI PICO Assistant")
        topic_description = st.text_area(
            "연구 주제를 자유롭게 서술하세요 / Research Topic Description",
            placeholder="예: 65세 이상 노인에게 치과 임플란트가 틀니보다 저작 효율이 좋은지 알고 싶어.",
            height=100,
        )

        if st.button("✨ PICO 자동 추출 (Auto-extract with AI)"):
            if topic_description:
                from src.llm import pico_extractor

                with st.spinner("AI가 PICO를 분석 중입니다..."):
                    extracted = pico_extractor.extract_pico_from_description(topic_description)
                    if extracted:
                        st.session_state["picos"].update(extracted)
                        # Sync individual fields to session state to update UI immediately
                        st.success("PICO 추출 완료! 아래 필드가 업데이트되었습니다.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("PICO 추출에 실패했습니다.")
            else:
                st.warning("먼저 연구 주제를 입력해주세요.")

        st.divider()
        st.subheader("PICO Details")

        col1, col2 = st.columns(2)
        with col1:
            population = st.text_input(t("population"), value=st.session_state["picos"].get("population", ""))
            intervention = st.text_input(
                t("intervention"),
                value=st.session_state["picos"].get("intervention", ""),
            )
            comparison = st.text_input(t("comparison"), value=st.session_state["picos"].get("comparison", ""))
        with col2:
            outcome = st.text_input(t("outcome"), value=st.session_state["picos"].get("outcome", ""))
            study_design = st.text_input(
                t("study_design"),
                value=st.session_state["picos"].get("study_design", ""),
            )

        if st.button(t("save_config")):
            new_picos = {
                "population": population,
                "intervention": intervention,
                "comparison": comparison,
                "outcome": outcome,
                "study_design": study_design,
            }
            save_config(new_picos)
            st.session_state["picos"] = new_picos
            st.success(t("config_saved"))

        query = construct_search_query(st.session_state["picos"])
        st.text_area(t("generated_query"), value=query, height=100)

        st.divider()
        col_s1, col_s2 = st.columns([1, 2])
        with col_s1:
            max_ret = st.number_input(t("max_articles"), min_value=1, max_value=1000, value=20)
        with col_s2:
            st.markdown("<br>", unsafe_allow_html=True)  # Spacer
            if st.button(t("search_button")):
                with st.spinner(t("searching")):
                    today = datetime.now()
                    end_date = today.strftime("%Y/%m/%d")
                    start_date = (today - timedelta(days=20 * 365)).strftime("%Y/%m/%d")

                    # 1. Get Count
                    _, total_count = pubmed.fetch_pmids(
                        query,
                        max_ret=1,
                        mindate=start_date,
                        maxdate=end_date,
                        sort="relevance",
                        email=st.session_state["picos"].get("email"),
                        api_key=st.session_state["picos"].get("api_key"),
                    )
                    st.session_state["stats"]["total_found"] = total_count

                    if total_count > 0:
                        st.info(t("total_found", count=total_count, max=max_ret))
                        # 2. Get Data
                        pmids, _ = pubmed.fetch_pmids(
                            query,
                            max_ret=max_ret,
                            mindate=start_date,
                            maxdate=end_date,
                            sort="relevance",
                            email=st.session_state["picos"].get("email"),
                            api_key=st.session_state["picos"].get("api_key"),
                        )

                        # Save PMIDs
                        pd.DataFrame(pmids, columns=["pmid"]).to_csv(
                            os.path.join(TABLES_DIR, "retrieved_pmids.csv"), index=False
                        )

                        # Fetch Abstracts
                        articles_xml = pubmed.fetch_abstracts(
                            pmids,
                            email=st.session_state["picos"].get("email"),
                            api_key=st.session_state["picos"].get("api_key"),
                        )

                        # Filter by Year
                        root = ET.fromstring(articles_xml)
                        filtered_articles_elements = []
                        current_year = datetime.now().year
                        for article in root.findall(".//PubmedArticle"):
                            pub_year_node = article.find(".//PubDate/Year")
                            pub_year = (
                                int(pub_year_node.text)
                                if pub_year_node is not None and pub_year_node.text.isdigit()
                                else current_year + 1
                            )
                            if pub_year <= current_year:
                                filtered_articles_elements.append(article)

                        # Reconstruct XML
                        filtered_root = ET.Element("PubmedArticleSet")
                        for article_elem in filtered_articles_elements:
                            filtered_root.append(article_elem)
                        filtered_articles_xml = ET.tostring(filtered_root, encoding="unicode")

                        # Save XML
                        with open(
                            os.path.join(RAW_DATA_DIR, "articles.xml"),
                            "w",
                            encoding="utf-8",
                        ) as f:
                            f.write(filtered_articles_xml)

                        # Parse to CSV and DB
                        df_parsed = pubmed_parser.parse_and_save_articles_csv(
                            filtered_articles_xml,
                            os.path.join(TABLES_DIR, "articles.csv"),
                        )
                        if df_parsed is not None and not df_parsed.empty:
                            db_manager.import_pubmed_results(df_parsed)

                        st.success(
                            t(
                                "retrieval_success",
                                count=len(filtered_articles_elements),
                            )
                        )

                        # Full AI-driven Scoping Mode: Automatically proceed
                        if st.session_state.get("run_mode") == "scoping" and st.session_state.get("scoping_agreed"):
                            st.info("🚀 Scoping 모드 작동 중: 다음 단계(스크리닝)로 자동 진입합니다...")
                            time.sleep(2)
                            st.session_state["current_tab_index"] = 1
                            st.rerun()

                    else:
                        st.warning(t("no_articles"))
        # Navigation Button (Step 1 -> Step 2)
        # Show only if articles have been retrieved
        csv_path = os.path.join(TABLES_DIR, "articles.csv")
        if os.path.exists(csv_path) or st.session_state["stats"]["total_found"] > 0:
            st.divider()
            col_next, _ = st.columns([1, 4])
            with col_next:
                if st.button(f"{t('tabs')[1]} >", type="primary", use_container_width=True):
                    next_step()

    # --- Tab 2: Screening ---
    if current_tab == 1:
        st.header(t("step2_header"))

        df = db_manager.get_articles_df()

        if not df.empty:
            st.dataframe(df[["pmid", "title", "journal", "pub_year"]], use_container_width=True)

            auto_start_screening = False
            if st.session_state.get("run_mode") == "scoping" and st.session_state.get("scoping_agreed"):
                if "screening_decision" not in df.columns or len(df[df["screening_decision"].notna()]) == 0:
                    auto_start_screening = True

            if st.button(t("start_screening")) or auto_start_screening:
                st.write("스크리닝을 시작합니다. 중단되어도 다시 시작하면 이어서 진행됩니다 (Resume).")
                progress_bar = st.progress(0)
                status_text = st.empty()

                checkpoint_csv = os.path.join(TABLES_DIR, "screening_results.csv")
                screen_gen = screener.screen_abstracts(df, st.session_state["picos"], checkpoint_csv)

                for current_idx, total_count, pmid, result in screen_gen:
                    progress_bar.progress(current_idx / total_count)
                    if result:
                        status_text.text(
                            f"[{current_idx}/{total_count}] Screening PMID {pmid}... Decision: {result['screening_decision']}"
                        )
                        # Write to DB immediately
                        db_manager.update_article(
                            pmid,
                            screening_decision=result["screening_decision"],
                            screening_reason=result["screening_reason"],
                            pipeline_status=1,
                        )
                    else:
                        status_text.text(f"[{current_idx}/{total_count}] Skipping PMID {pmid} (Already screened)")

                status_text.text(f"Screening completed! ({total_count}/{total_count})")

                # Reload df from DB to update stats
                df = db_manager.get_articles_df()

                # Update stats
                st.session_state["stats"]["screened"] = len(df[df["screening_decision"].notna()])
                st.session_state["stats"]["included"] = len(df[df["screening_decision"] == "Included"])
                st.session_state["stats"]["excluded"] = (
                    st.session_state["stats"]["screened"] - st.session_state["stats"]["included"]
                )

                if st.session_state.get("run_mode") == "scoping" and st.session_state.get("scoping_agreed"):
                    st.info("🚀 Scoping 모드 작동 중: 다음 단계(분석 파이프라인)로 자동 진입합니다...")
                    time.sleep(2)
                    st.session_state["current_tab_index"] = 2
                    st.rerun()
                else:
                    st.rerun()

            # Show Screening Results if available
            if "screening_decision" in df.columns:
                st.divider()
                st.subheader(t("screening_results"))
                st.metric(
                    t("inclusion_rate"),
                    f"{st.session_state['stats']['included']} / {st.session_state['stats']['screened']}",
                )

                # PRISMA Flow Diagram rendering
                st.subheader("PRISMA Flow Diagram")
                total_found = len(df)
                total_screened = st.session_state["stats"]["screened"]
                total_included = st.session_state["stats"]["included"]

                if "exclusion_category" in df.columns:
                    exclusion_counts = (
                        df[df["screening_decision"] == "Excluded"]["exclusion_category"].value_counts().to_dict()
                    )
                    exclusion_html = "".join([f"<li>{k}: {v}</li>" for k, v in exclusion_counts.items() if str(k).strip()])
                else:
                    exclusion_html = "<li>No category recorded</li>"

                prisma_html = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px; border: 1px solid #ddd;">
                    <h3 style="text-align: center; color: #333;">PRISMA Flow Diagram</h3>
                    <div style="text-align: center; padding: 10px; margin: 10px; background-color: #e3f2fd; border: 1px solid #90caf9; border-radius: 5px;">
                        <strong>Identification</strong><br>
                        Records identified through database searching<br>
                        (n = {total_found})
                    </div>
                    <div style="text-align: center; font-size: 24px;">&#8595;</div>
                    <div style="text-align: center; padding: 10px; margin: 10px; background-color: #fff3e0; border: 1px solid #ffcc80; border-radius: 5px; display: flex; justify-content: space-between;">
                        <div style="width: 45%;">
                            <strong>Screening</strong><br>
                            Records screened<br>
                            (n = {total_screened})
                        </div>
                        <div style="width: 45%; border-left: 2px solid #ffcc80; padding-left: 10px; text-align: left;">
                            <strong>Records excluded</strong> (n = {total_screened - total_included})<br>
                            <ul style="margin: 0; padding-left: 20px; font-size: 0.9em;">
                                {exclusion_html}
                            </ul>
                        </div>
                    </div>
                    <div style="text-align: center; font-size: 24px;">&#8595;</div>
                    <div style="text-align: center; padding: 10px; margin: 10px; background-color: #e8f5e9; border: 1px solid #a5d6a7; border-radius: 5px;">
                        <strong>Included</strong><br>
                        Studies included in qualitative synthesis<br>
                        (n = {total_included})
                    </div>
                </div>
                """
                st.components.v1.html(prisma_html, height=450)

                display_cols = ["pmid", "title", "screening_decision", "screening_reason"]
                if "exclusion_category" in df.columns:
                    display_cols.append("exclusion_category")

                st.markdown("### 📝 수동 검토 및 오버라이드 (Override)")
                st.markdown(
                    "아래 표에서 `screening_decision` 항목을 더블클릭하여 결과를 수동으로 변경(Included/Excluded)할 수 있습니다. 변경된 내용은 DB에 즉시 반영되며, 차트와 통계에 업데이트됩니다."
                )

                # Editor for User Override
                edited_df = st.data_editor(
                    df[display_cols],
                    use_container_width=True,
                    disabled=["pmid", "title", "screening_reason", "exclusion_category"],
                    column_config={
                        "screening_decision": st.column_config.SelectboxColumn(
                            "Decision",
                            help="판정 결과를 오버라이드합니다.",
                            options=["Included", "Excluded"],
                            required=True,
                        )
                    },
                    key="screening_editor",
                )

                # Check if any decision changed
                changed = False
                for idx, row in edited_df.iterrows():
                    orig_decision = df.loc[idx, "screening_decision"]
                    new_decision = row["screening_decision"]
                    if orig_decision != new_decision:
                        pmid = row["pmid"]
                        db_manager.update_article(pmid, screening_decision=new_decision)
                        changed = True

                if changed:
                    st.success("✅ 오버라이드 결과가 데이터베이스에 업데이트되었습니다!")
                    time.sleep(1)
                    st.rerun()
        else:
            st.info(t("search_first"))

        # Navigation Button (Step 2 -> Step 3)
        # Show only if screening has been performed
        screening_csv_path = os.path.join(TABLES_DIR, "screening_results.csv")
        if os.path.exists(screening_csv_path) or st.session_state["stats"]["screened"] > 0:
            st.divider()
            col_next, _ = st.columns([1, 4])
            with col_next:
                if st.button(f"{t('tabs')[2]} >", type="primary", use_container_width=True):
                    next_step()

    # --- Tab 3: Analysis Pipeline ---
    if current_tab == 2:
        st.header(t("step3_header"))
        st.markdown(t("step3_desc"))

        df = db_manager.get_articles_df()
        if not df.empty:
            if "screening_decision" not in df.columns:
                st.warning(t("screen_first_warning"))
            else:
                included_df = df[df["screening_decision"] == "Included"]
                included_pmids = included_df["pmid"].astype(str).tolist()

                if not included_pmids:
                    st.warning(t("no_included"))
                else:
                    if not included_pmids:
                        st.warning(t("no_included"))
                    else:
                        # --- Section 1: PDF Download ---
                        st.subheader(t("download_section"))

                        xml_path = os.path.join(RAW_DATA_DIR, "articles.xml")
                        if st.button(t("download_btn"), type="primary"):
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            status_text.text(t("downloading_pdfs"))

                            pdf_download_status = downloader.download_pdfs_from_xml(
                                xml_path,
                                PDF_DIR,
                                allowed_pmids=included_pmids,
                                email=st.session_state["picos"].get("email"),
                            )
                            for pmid, status in pdf_download_status.items():
                                db_manager.update_article(pmid, pdf_download_status=status)

                            # Refresh df to reflect status
                            df = db_manager.get_articles_df()

                            downloaded_pdfs = [
                                k for k, v in pdf_download_status.items() if "Downloaded" in v or "Already" in v
                            ]
                            st.session_state["stats"]["retrieved"] = len(downloaded_pdfs)
                            progress_bar.progress(100)
                            st.success(t("download_complete"))
                            time.sleep(1)
                            st.rerun()

                        # --- Check for missing files & Manual Helper ---
                        if os.path.exists(csv_path):
                            try:
                                df = pd.read_csv(csv_path)
                                if "pdf_download_status" in df.columns:
                                    failed_mask = ~df["pdf_download_status"].astype(str).str.contains(
                                        r"Downloaded|Exists|Skipped",
                                        case=False,
                                        na=False,
                                    )
                                    failed_df = df[failed_mask]

                                    if not failed_df.empty:
                                        st.divider()
                                        st.warning(
                                            t(
                                                "download_failed_warning",
                                                count=len(failed_df),
                                            )
                                        )
                                        # Manual Helper UI
                                        st.info(t("manual_helper_title"))

                                        # Bulk Uploader Section
                                        with st.expander(t("bulk_upload_title"), expanded=False):
                                            st.write(t("bulk_upload_desc"))
                                            bulk_files = st.file_uploader(
                                                t("bulk_upload_title"),
                                                type="pdf",
                                                accept_multiple_files=True,
                                                key="bulk_pdf_uploader",
                                            )
                                            if bulk_files:
                                                results, count = handle_bulk_upload(bulk_files, df, csv_path)
                                                for res in results:
                                                    if "✅" in res:
                                                        st.success(res)
                                                    else:
                                                        st.warning(res)
                                                if count > 0:
                                                    st.toast(
                                                        f"Successfully matched {count} files!",
                                                        icon="🚀",
                                                    )
                                                    time.sleep(1)
                                                    st.rerun()

                                        st.warning(t("ai_proposal_warning"))

                                        # Pagination
                                        batch_size = 5
                                        total_failed = len(failed_df)
                                        total_pages = (total_failed - 1) // batch_size + 1
                                        current_page = st.session_state.get("failed_pdfs_page", 0)

                                        if current_page >= total_pages:
                                            current_page = total_pages - 1
                                        if current_page < 0:
                                            current_page = 0
                                        st.session_state["failed_pdfs_page"] = current_page

                                        start_idx = current_page * batch_size
                                        end_idx = start_idx + batch_size
                                        batch_df = failed_df.iloc[start_idx:end_idx]

                                        col_p1, col_p2, col_p3 = st.columns([1, 2, 1])
                                        with col_p1:
                                            if st.button(
                                                t("prev_page"),
                                                disabled=(current_page == 0),
                                            ):
                                                st.session_state["failed_pdfs_page"] -= 1
                                                st.rerun()
                                        with col_p2:
                                            st.markdown(f"**Page {current_page + 1} / {total_pages}**")
                                        with col_p3:
                                            if st.button(
                                                t("next_page"),
                                                disabled=(current_page == total_pages - 1),
                                            ):
                                                st.session_state["failed_pdfs_page"] += 1
                                                st.rerun()

                                        for _, row in batch_df.iterrows():
                                            with st.container(border=True):
                                                pmid = str(row["pmid"])
                                                title = row.get("title", "No Title")
                                                doi = row.get("doi")
                                                target_path = os.path.join(PDF_DIR, f"{pmid}.pdf")
                                                file_exists = os.path.exists(target_path)

                                                pubmed_link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                                                scholar_link = f"https://scholar.google.com/scholar?q={pmid}"
                                                if isinstance(doi, str) and doi.strip():
                                                    doi_link = f"https://doi.org/{doi}"
                                                    sci_hub_link = f"https://sci-hub.st/{doi}"
                                                else:
                                                    doi_link = None
                                                    sci_hub_link = f"https://sci-hub.st/{pmid}"

                                                st.markdown(f"**{title}**")

                                                # Status Badge & File Detection
                                                status = str(row.get("pdf_download_status", "Failed"))

                                                # Use session state cache for file existence to speed up UI
                                                cache_key = f"exists_{pmid}"
                                                if cache_key not in st.session_state["file_cache"]:
                                                    st.session_state["file_cache"][cache_key] = os.path.exists(target_path)
                                                file_exists = st.session_state["file_cache"][cache_key]

                                                if file_exists:
                                                    if (
                                                        "Manual" not in status
                                                        and "Downloaded" not in status
                                                        and "Exists" not in status
                                                    ):
                                                        st.info(f"{t('status_manual')} (Auto-detected)")
                                                        # Auto-update status in DB if detected
                                                        db_manager.update_article(
                                                            pmid, pdf_download_status="Downloaded (Detected)"
                                                        )
                                                        # Update cache and stats potentially
                                                        st.session_state["file_cache"][cache_key] = True
                                                    else:
                                                        st.success(t("status_verified"))
                                                else:
                                                    st.error(t("status_failed"))

                                                # Action Buttons
                                                c_info, c_search = st.columns([1.5, 1.5])
                                                with c_info:
                                                    st.markdown(f"PMID: `{pmid}`")
                                                    st.code(f"{pmid}.pdf", language="text")
                                                    st.link_button(
                                                        t("view_pubmed"),
                                                        pubmed_link,
                                                        use_container_width=True,
                                                        type="primary",
                                                    )
                                                with c_search:
                                                    # Row 1: Primary Search
                                                    s_col1, s_col2 = st.columns(2)
                                                    with s_col1:
                                                        st.link_button(
                                                            t("search_scholar"),
                                                            scholar_link,
                                                            use_container_width=True,
                                                        )
                                                    with s_col2:
                                                        if doi_link:
                                                            st.link_button(
                                                                t("search_doi"),
                                                                doi_link,
                                                                use_container_width=True,
                                                            )
                                                        else:
                                                            st.button(
                                                                "No DOI",
                                                                disabled=True,
                                                                use_container_width=True,
                                                                key=f"nodoi_{pmid}",
                                                            )

                                                    # Row 2: Sci-Hub (Alternative)
                                                    st.link_button(
                                                        t("search_scihub"),
                                                        sci_hub_link,
                                                        use_container_width=True,
                                                    )

                                                # File Uploader
                                                uploaded_file = st.file_uploader(
                                                    f"{t('upload_pdf')} ({pmid})",
                                                    type="pdf",
                                                    key=f"upload_{pmid}",
                                                )
                                                if uploaded_file:
                                                    with open(target_path, "wb") as f:
                                                        f.write(uploaded_file.getbuffer())
                                                    db_manager.update_article(
                                                        pmid, pdf_download_status="Downloaded (Manual Upload)"
                                                    )
                                                    st.session_state["file_cache"][cache_key] = True
                                                    st.success(f"{pmid}.pdf saved!")
                                                    time.sleep(0.5)
                                                    st.rerun()

                                                c1, c2 = st.columns(2)
                                                with c1:
                                                    if st.button(
                                                        f"{t('check_file_btn')} ({pmid})",
                                                        key=f"check_{pmid}",
                                                    ):
                                                        # Force re-check on manual button
                                                        file_exists_physical = os.path.exists(target_path)
                                                        st.session_state["file_cache"][cache_key] = file_exists_physical
                                                        if file_exists_physical:
                                                            db_manager.update_article(
                                                                pmid, pdf_download_status="Downloaded (Manual)"
                                                            )
                                                            st.toast(
                                                                t(
                                                                    "file_verified",
                                                                    pmid=pmid,
                                                                ),
                                                                icon="✅",
                                                            )
                                                            time.sleep(0.5)
                                                            st.rerun()
                                                        else:
                                                            st.error(
                                                                t(
                                                                    "file_not_found",
                                                                    path=target_path,
                                                                )
                                                            )
                                                with c2:
                                                    if st.button(
                                                        f"{t('skip_file_btn')} ({pmid})",
                                                        key=f"skip_{pmid}",
                                                    ):
                                                        db_manager.update_article(pmid, pdf_download_status="Skipped_User")
                                                        st.toast(
                                                            t(
                                                                "file_skipped",
                                                                pmid=pmid,
                                                            ),
                                                            icon="⏭️",
                                                        )
                                                        time.sleep(0.5)
                                                        st.rerun()
                            except Exception as e:
                                st.error(f"Error loading helper: {e}")

                        # --- Section 2: Analysis ---
                        st.divider()
                        st.subheader(t("analysis_section"))

                        # Count ready files
                        ready_count = 0
                        df = db_manager.get_articles_df()
                        if not df.empty and "pdf_download_status" in df.columns:
                            ready_mask = (
                                df["pdf_download_status"].astype(str).str.contains(r"Downloaded|Exists", case=False, na=False)
                            )
                            ready_count = len(df[ready_mask])

                        st.info(t("analysis_ready", count=ready_count))

                        if st.button(t("analysis_btn"), type="primary"):
                            # Create a run version and archive current data
                            run_path = vm.create_run(st.session_state["picos"])
                            vm.archive_current_data(run_path, TABLES_DIR, RAW_DATA_DIR)
                            st.toast(
                                f"Run archived to {os.path.basename(run_path)}",
                                icon="📦",
                            )

                            progress_bar = st.progress(0)
                            status_text = st.empty()

                            # Re-read DF from DB
                            df = db_manager.get_articles_df()
                            doc_ready_mask = (
                                df["pdf_download_status"].astype(str).str.contains(r"Downloaded|Exists", case=False, na=False)
                            )
                            ready_pmids = df[doc_ready_mask]["pmid"].astype(str).tolist()

                            # 2. GROBID Parsing
                            status_text.text(t("parsing_pdfs"))
                            from src.parse import fallback_parser

                            for pmid in ready_pmids:
                                pdf_path = os.path.join(PDF_DIR, f"{pmid}.pdf")
                                tei_path = os.path.join(TEI_DIR, f"{pmid}.xml")
                                if os.path.exists(pdf_path) and not os.path.exists(tei_path):
                                    tei_xml = grobid_client.process_pdf(pdf_path)

                                    # Fallback logic: If GROBID fails or returns very little text
                                    if not tei_xml or len(tei_xml.strip()) < 500:
                                        status_text.text(f"GROBID failed for {pmid}. Using Fallback Parser...")
                                        tei_xml = fallback_parser.extract_text_from_pdf(pdf_path)
                                        db_manager.update_article(
                                            pmid, pdf_download_status="Parsed (Fallback)", pipeline_status=2
                                        )
                                    else:
                                        db_manager.update_article(
                                            pmid, pdf_download_status="Parsed (GROBID)", pipeline_status=2
                                        )

                                    if tei_xml:
                                        with open(tei_path, "w", encoding="utf-8") as f:
                                            f.write(tei_xml)
                            progress_bar.progress(50)

                            # 3. RoB Assessment
                            if os.path.exists(TEI_DIR):
                                rob_gen = assessor.batch_assess_rob(
                                    TEI_DIR, os.path.join(TABLES_DIR, "rob_assessment.csv"), allowed_pmids=ready_pmids
                                )
                                if rob_gen:
                                    for current_idx, total_count, pmid in rob_gen:
                                        status_text.text(
                                            f"[{current_idx}/{total_count}] Assessing Risk of Bias for PMID {pmid}..."
                                        )
                                        # Calculate progress between 50% and 75%
                                        progress = 50 + int((current_idx / total_count) * 25)
                                        progress_bar.progress(progress)
                            progress_bar.progress(75)

                            # 4. Data Extraction
                            status_text.text(t("extracting_data"))
                            tei_files = [
                                f for f in os.listdir(TEI_DIR) if f.endswith(".xml") and f.replace(".xml", "") in ready_pmids
                            ]
                            extracted_data = []

                            if tei_files:
                                from src.extract import pico_extractor

                                total_tei = len(tei_files)
                                for idx, tei_file in enumerate(tei_files):
                                    pmid = tei_file.replace(".xml", "")
                                    status_text.text(f"[{idx + 1}/{total_tei}] Extracting PICO for PMID {pmid}...")
                                    progress = 75 + int(((idx + 1) / total_tei) * 25)
                                    progress_bar.progress(progress)

                                    # Use optimized context slicing for PICO extraction
                                    full_text = tei_parser.extract_text_from_tei(
                                        os.path.join(TEI_DIR, tei_file), optimize_context=True
                                    )
                                    if full_text:
                                        text_snippet = (full_text[:8000] + "...") if len(full_text) > 8000 else full_text

                                        data = pico_extractor.extract_pico_multi_agent(text_snippet)
                                        if data:
                                            # Flatten the nested dict for dataframe compatibility
                                            flat_data = {"pmid": pmid}
                                            for k, v in data.items():
                                                if isinstance(v, dict):
                                                    flat_data[k] = v.get("description", v.get("design", ""))
                                                    if "subcategory" in v:
                                                        flat_data[f"{k}_subcategory"] = v["subcategory"]
                                                    if "scale_metric" in v:
                                                        flat_data[f"{k}_scale_metric"] = v["scale_metric"]
                                                    if "statistics_summary" in v:
                                                        flat_data[f"{k}_statistics_summary"] = v["statistics_summary"]
                                                    if "raw_quote" in v:
                                                        flat_data[f"{k}_quote"] = v["raw_quote"]
                                                else:
                                                    flat_data[k] = str(v)
                                            extracted_data.append(flat_data)

                                if extracted_data:
                                    pd.DataFrame(extracted_data).to_csv(
                                        os.path.join(TABLES_DIR, "extracted_pico.csv"),
                                        index=False,
                                    )

                            progress_bar.progress(100)
                            status_text.text(t("analysis_complete"))
                            st.success(t("analysis_complete"))

        # --- Human-in-the-Loop Verification & Navigation (Step 3 -> Step 4) ---
        extracted_csv_path = os.path.join(TABLES_DIR, "extracted_pico.csv")
        rob_csv_path = os.path.join(TABLES_DIR, "rob_assessment.csv")

        if os.path.exists(extracted_csv_path) and os.path.exists(rob_csv_path):
            if st.session_state.get("run_mode") == "scoping" and st.session_state.get("scoping_agreed"):
                if not st.session_state.get("human_verified", False):
                    st.session_state["human_verified"] = True
                    st.info("🚀 Scoping 모드 작동 중: 다음 단계(최종 보고서)로 자동 진입합니다...")
                    time.sleep(2)
                    st.session_state["current_tab_index"] = 3
                    st.rerun()
            else:
                st.divider()
                st.subheader("🧐 Human-in-the-Loop Verification")
                st.info(
                    "AI가 추출한 데이터를 확인하고 필요한 경우 직접 수정하세요. 수정 완료 후 반드시 '확정 및 저장' 버튼을 눌러야 다음 단계로 진행할 수 있습니다."
                )

            if not st.session_state.get("run_mode") == "scoping":
                pico_df = pd.read_csv(extracted_csv_path)
                rob_df = pd.read_csv(rob_csv_path)

                st.markdown("#### PICO Data")
                edited_pico = st.data_editor(pico_df, num_rows="dynamic", key="pico_editor", use_container_width=True)

                st.markdown("#### Risk of Bias (RoB)")
                edited_rob = st.data_editor(rob_df, num_rows="dynamic", key="rob_editor", use_container_width=True)

                if st.button("💾 확정 및 저장 (Confirm & Save)"):
                    edited_pico.to_csv(extracted_csv_path, index=False, encoding="utf-8-sig")
                    edited_rob.to_csv(rob_csv_path, index=False, encoding="utf-8-sig")
                    st.session_state["human_verified"] = True
                    st.success("데이터가 확정되었습니다! 이제 다음 단계로 넘어갈 수 있습니다.")
                    time.sleep(1)
                    st.rerun()

            if st.session_state.get("human_verified", False):
                st.divider()
                col_next, _ = st.columns([1, 4])
                with col_next:
                    if st.button(f"{t('tabs')[3]} >", type="primary", use_container_width=True):
                        next_step()

    # --- Tab 4: Reporting ---
    if current_tab == 3:
        st.header(t("step4_header"))
        st.warning(t("ai_proposal_warning"))

        current_lang = st.session_state["lang"]
        report_filename = f"report_{current_lang}.md"
        report_path = os.path.join(DATA_DIR, report_filename)
        articles_csv_path = os.path.join(TABLES_DIR, "articles.csv")

        auto_generate = False
        if st.session_state.get("run_mode") == "scoping" and st.session_state.get("scoping_agreed"):
            if not os.path.exists(report_path) and "generating_report" not in st.session_state:
                auto_generate = True

        if st.button(t("generate_report")) or auto_generate:
            st.session_state["generating_report"] = True

            # 1. Synthesize Answer (New)
            with st.spinner("AI is synthesizing the answer to your PICO question..."):
                synthesis_result = synthesizer.synthesize_answer(
                    st.session_state["picos"],
                    os.path.join(TABLES_DIR, "extracted_pico.csv"),
                    os.path.join(TABLES_DIR, "rob_assessment.csv"),
                    lang=current_lang,
                )

            # 2. Generate Report
            from src.report import generator

            generator.generate_report(
                st.session_state["stats"],
                st.session_state["picos"],
                os.path.join(TABLES_DIR, "extracted_pico.csv"),
                os.path.join(TABLES_DIR, "rob_assessment.csv"),
                report_path,
                lang=current_lang,
                synthesis_result=synthesis_result,
                articles_csv_path=articles_csv_path,
                run_mode=st.session_state.get("run_mode", "hitl"),
            )
            st.session_state["generating_report"] = False
            st.success(t("report_generated"))

        # Display report if it exists for the current language
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                report_content = f.read()
                st.markdown(report_content, unsafe_allow_html=True)

                # Download filename with date/time
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                download_filename = f"report_{current_lang}_{timestamp_str}.md"

                st.download_button(
                    label=t("download_report"),
                    data=report_content,
                    file_name=download_filename,
                    mime="text/markdown",
                )
        else:
            pass


if __name__ == "__main__":
    main()
