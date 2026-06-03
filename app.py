import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import streamlit as st
import yaml

sys.path.append(os.getcwd())

from src.ingest import pubmed
from src.parse import pubmed_parser
from src.ui import sidebar, step1_search, step2_screen, step3_analysis, step4_extraction, step5_report
from src.ui.translations import TRANSLATIONS
from src.utils import data_manager, db_manager, versioning

# --- Configuration & Setup ---
DATA_DIR = "data"
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
TABLES_DIR = os.path.join(DATA_DIR, "tables")
TEI_DIR = os.path.join(DATA_DIR, "tei")
PDF_DIR = os.path.join(DATA_DIR, "pdf")
CONFIG_PATH = "picos_config.yaml"

os.makedirs(RAW_DATA_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)
os.makedirs(TEI_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)

st.set_page_config(page_title="Systematic Reviewer AI", layout="wide")


def t(key, **kwargs):
    lang = st.session_state.get("lang", "KO")
    text = TRANSLATIONS[lang].get(key, key)
    if kwargs and isinstance(text, str):
        return text.format(**kwargs)
    return text


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
        if "[" in term and "]" in term:
            return f"({term})"
        if " OR " in term or " AND " in term:
            return f"({term})"
        if " " in term:
            return f'"{term}"{field_tag}'
        return f"{term}{field_tag}"

    query_parts.append(format_part(picos.get("population")))
    query_parts.append(format_part(picos.get("intervention")))
    query_parts.append(format_part(picos.get("comparison")))
    query_parts.append(format_part(picos.get("outcome")))
    query_parts.append(format_part(picos.get("study_design"), "[pt]"))
    return " AND ".join(filter(None, query_parts))


def init_session_state():
    if "stats" not in st.session_state:
        st.session_state["stats"] = {"total_found": 0, "screened": 0, "excluded": 0, "included": 0, "retrieved": 0}
    if "picos" not in st.session_state:
        st.session_state["picos"] = load_config()
    if "lang" not in st.session_state:
        st.session_state["lang"] = "KO"
    if "current_tab_index" not in st.session_state:
        st.session_state["current_tab_index"] = 0
    if "failed_pdfs_page" not in st.session_state:
        st.session_state["failed_pdfs_page"] = 0
    if "file_cache" not in st.session_state:
        st.session_state["file_cache"] = {}


# --- Callbacks ---
def update_state(key, value):
    st.session_state[key] = value


def pop_state(key, default):
    return st.session_state.pop(key, default)


def update_config(key, value):
    st.session_state["picos"][key] = value
    save_config(st.session_state["picos"])


def update_config_batch(updates):
    st.session_state["picos"].update(updates)
    save_config(st.session_state["picos"])


def reset_data():
    data_manager.clear_generated_data_files()
    st.session_state["stats"] = {"total_found": 0, "screened": 0, "excluded": 0, "included": 0, "retrieved": 0}
    st.session_state["picos"] = {}
    save_config({})


def next_step():
    st.session_state["current_tab_index"] += 1
    st.rerun()


def set_tab(idx):
    st.session_state["current_tab_index"] = idx
    st.rerun()


def update_stats(**kwargs):
    st.session_state["stats"].update(kwargs)


def check_file_cache(pmid, path):
    key = f"exists_{pmid}"
    if key not in st.session_state["file_cache"]:
        st.session_state["file_cache"][key] = os.path.exists(path)
    return st.session_state["file_cache"][key]


def update_file_cache(pmid, val):
    st.session_state["file_cache"][f"exists_{pmid}"] = val


def execute_pubmed_search(query, max_ret, config):
    today = datetime.now()
    end_date = today.strftime("%Y/%m/%d")
    start_date = (today - timedelta(days=20 * 365)).strftime("%Y/%m/%d")
    _, total_count = pubmed.fetch_pmids(
        query,
        max_ret=1,
        mindate=start_date,
        maxdate=end_date,
        sort="relevance",
        email=config.get("email"),
        api_key=config.get("api_key"),
    )
    st.session_state["stats"]["total_found"] = total_count

    if total_count > 0:
        st.info(f"총 {total_count}개의 논문 발견. 상위 {max_ret}개 가져오는 중...")
        pmids, _ = pubmed.fetch_pmids(
            query,
            max_ret=max_ret,
            mindate=start_date,
            maxdate=end_date,
            sort="relevance",
            email=config.get("email"),
            api_key=config.get("api_key"),
        )
        articles_xml = pubmed.fetch_abstracts(pmids, email=config.get("email"), api_key=config.get("api_key"))

        # Filter by Year
        root = ET.fromstring(articles_xml)
        filtered_articles_elements = []
        current_year = datetime.now().year
        for article in root.findall(".//PubmedArticle"):
            pub_year_node = article.find(".//PubDate/Year")
            pub_year = (
                int(pub_year_node.text) if pub_year_node is not None and pub_year_node.text.isdigit() else current_year + 1
            )
            if pub_year <= current_year:
                filtered_articles_elements.append(article)

        filtered_root = ET.Element("PubmedArticleSet")
        for article_elem in filtered_articles_elements:
            filtered_root.append(article_elem)
        filtered_articles_xml = ET.tostring(filtered_root, encoding="unicode")

        with open(os.path.join(RAW_DATA_DIR, "articles.xml"), "w", encoding="utf-8") as f:
            f.write(filtered_articles_xml)

        df_parsed = pubmed_parser.parse_articles(filtered_articles_xml)
        if df_parsed is not None and not df_parsed.empty:
            db_manager.import_pubmed_results(df_parsed)
        st.success(f"{len(filtered_articles_elements)}개의 논문을 성공적으로 가져오고 파싱했습니다!")

        if st.session_state.get("run_mode") == "scoping" and st.session_state.get("scoping_agreed"):
            st.info("🚀 Scoping 모드 작동 중: 다음 단계(스크리닝)로 자동 진입합니다...")
            time.sleep(2)
            set_tab(1)
    else:
        st.warning("조건에 맞는 논문을 찾을 수 없습니다.")


def handle_bulk_upload(uploaded_files, df):
    import re

    from pypdf import PdfReader

    success_count = 0
    results = []
    for uploaded_file in uploaded_files:
        filename = uploaded_file.name
        match = re.search(r"(\d{8})", filename)
        if match:
            pmid = match.group(1)
            target_path = os.path.join(PDF_DIR, f"{pmid}.pdf")
            if pmid in df["pmid"].astype(str).values:
                try:
                    reader = PdfReader(uploaded_file)
                    if len(reader.pages) > 0:
                        uploaded_file.seek(0)
                        with open(target_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        db_manager.update_article(pmid, pdf_download_status="Downloaded (Bulk Match)")
                        df.loc[df["pmid"].astype(str) == pmid, "pdf_download_status"] = "Downloaded (Bulk Match)"
                        success_count += 1
                        results.append(f"✅ {filename} -> PMID {pmid} 매칭 완료")
                        update_file_cache(pmid, True)
                    else:
                        results.append(f"⚠️ {filename}: 유효하지 않은 PDF입니다.")
                except Exception as e:
                    results.append(f"⚠️ {filename}: PDF 파싱 실패 - {e}")
            else:
                results.append(f"⚠️ {filename}: PMID {pmid} not found in project.")
        else:
            results.append(f"⚠️ {filename}에서 PMID를 추출하지 못했습니다.")
    return results, success_count


def handle_data_editor_change():
    # Helper for df editing if needed directly via callback
    pass


# --- Main App Router ---
def main():
    init_session_state()
    vm = versioning.VersionManager(DATA_DIR)

    st.title("🤖 체계적 문헌고찰 AI")
    st.markdown("로컬 AI로 체계적 문헌고찰 파이프라인을 자동화하세요.")

    callbacks = {
        "update_state": update_state,
        "pop_state": pop_state,
        "update_config": update_config,
        "update_config_batch": update_config_batch,
        "reset_data": reset_data,
        "next_step": next_step,
        "set_tab": set_tab,
        "t": t,
        "db_manager": db_manager,
        "vm": vm,
        "construct_search_query": construct_search_query,
        "execute_pubmed_search": execute_pubmed_search,
        "update_stats": update_stats,
        "check_file_cache": check_file_cache,
        "update_file_cache": update_file_cache,
        "handle_bulk_upload": handle_bulk_upload,
        "handle_data_editor_change": handle_data_editor_change,
    }

    sidebar.render(st.session_state["picos"], st.session_state, **callbacks)

    tabs_labels = t("tabs")

    def update_tab_index():
        st.session_state["current_tab_index"] = tabs_labels.index(st.session_state["nav_radio"])

    if "nav_radio" not in st.session_state or st.session_state["current_tab_index"] < len(tabs_labels):
        st.session_state["nav_radio"] = tabs_labels[st.session_state["current_tab_index"]]

    st.radio("", tabs_labels, key="nav_radio", horizontal=True, on_change=update_tab_index, label_visibility="collapsed")
    st.divider()

    current_tab = st.session_state["current_tab_index"]

    # Simple Router
    if current_tab == 0:
        step1_search.render(st.session_state["picos"], st.session_state, **callbacks)
    elif current_tab == 1:
        step2_screen.render(st.session_state["picos"], st.session_state, **callbacks)
    elif current_tab == 2:
        step3_analysis.render(st.session_state["picos"], st.session_state, **callbacks)
    elif current_tab == 3:
        step4_extraction.render(st.session_state["picos"], st.session_state, **callbacks)
    elif current_tab == 4:
        step5_report.render(st.session_state["picos"], st.session_state, **callbacks)


if __name__ == "__main__":
    main()
