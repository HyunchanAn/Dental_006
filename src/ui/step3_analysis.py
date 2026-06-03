import os
import time

import streamlit as st

from src.ingest import downloader
from src.parse import fallback_parser, grobid_client
from src.rob import assessor

DATA_DIR = "data"
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
TABLES_DIR = os.path.join(DATA_DIR, "tables")
TEI_DIR = os.path.join(DATA_DIR, "tei")
PDF_DIR = os.path.join(DATA_DIR, "pdf")


def render(config: dict, state: dict, **callbacks) -> None:
    """
    Renders Step 3: Analysis Pipeline (Download, GROBID, RoB).
    """
    t = callbacks.get("t", lambda k, **kw: k)
    db_manager = callbacks["db_manager"]
    vm = callbacks["vm"]

    st.header(t("step3_header"))
    st.markdown(t("step3_desc"))

    df = db_manager.get_articles_df()
    if df.empty:
        st.warning(t("no_included"))
        return

    if "screening_decision" not in df.columns:
        st.warning(t("screen_first_warning"))
        return

    included_df = df[df["screening_decision"] == "Included"]
    included_pmids = included_df["pmid"].astype(str).tolist()

    if not included_pmids:
        st.warning(t("no_included"))
        return

    # --- Section 1: PDF Download ---
    st.subheader(t("download_section"))

    xml_path = os.path.join(RAW_DATA_DIR, "articles.xml")

    auto_download = False
    if state.get("run_mode") == "scoping" and state.get("scoping_agreed"):
        if "pdf_download_status" not in df.columns:
            auto_download = True
        else:
            included_missing = included_df["pdf_download_status"]
            if included_missing.isna().any() or (included_missing == "").any():
                auto_download = True

    if auto_download or st.button(t("download_btn"), type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.text("PDF 다운로드 중...")

        pdf_download_status = downloader.download_pdfs_from_xml(
            xml_path,
            PDF_DIR,
            allowed_pmids=included_pmids,
            email=config.get("email"),
            enable_scihub_fallback=config.get("enable_scihub_fallback", False),
        )
        for pmid, status in pdf_download_status.items():
            db_manager.update_article(pmid, pdf_download_status=status)

        df = db_manager.get_articles_df()
        downloaded_pdfs = [k for k, v in pdf_download_status.items() if "Downloaded" in v or "Already" in v]

        callbacks["update_stats"](retrieved=len(downloaded_pdfs))

        progress_bar.progress(100)
        st.success(t("download_complete"))
        time.sleep(1)
        st.rerun()

    # --- Check for missing files & Manual Helper ---
    if "pdf_download_status" in df.columns:
        status_series = df["pdf_download_status"].astype(str).str.strip()
        is_attempted = (status_series != "") & (status_series.str.lower() != "nan") & (status_series.str.lower() != "none")
        is_not_success = ~status_series.str.contains(r"Downloaded|Exists|Skipped", case=False, na=False)
        failed_mask = is_attempted & is_not_success
        failed_df = df[failed_mask]

        if not failed_df.empty:
            st.divider()
            st.warning(t("download_failed_warning", count=len(failed_df)))
            st.info(t("manual_helper_title"))

            with st.expander(t("bulk_upload_title"), expanded=False):
                st.write(t("bulk_upload_desc"))
                bulk_files = st.file_uploader(
                    t("bulk_upload_title"),
                    type="pdf",
                    accept_multiple_files=True,
                    key="bulk_pdf_uploader",
                )
                if bulk_files:
                    results, count = callbacks["handle_bulk_upload"](bulk_files, df)
                    for res in results:
                        if "✅" in res:
                            st.success(res)
                        else:
                            st.warning(res)
                    if count > 0:
                        st.toast(f"Successfully matched {count} files!", icon="🚀")
                        time.sleep(1)
                        st.rerun()

            st.warning(t("ai_proposal_warning"))

            batch_size = 5
            total_failed = len(failed_df)
            total_pages = (total_failed - 1) // batch_size + 1
            current_page = state.get("failed_pdfs_page", 0)

            if current_page >= total_pages:
                current_page = total_pages - 1
            if current_page < 0:
                current_page = 0

            if current_page != state.get("failed_pdfs_page", 0):
                callbacks["update_state"]("failed_pdfs_page", current_page)

            start_idx = current_page * batch_size
            end_idx = start_idx + batch_size
            batch_df = failed_df.iloc[start_idx:end_idx]

            col_p1, col_p2, col_p3 = st.columns([1, 2, 1])
            with col_p1:
                if st.button(t("prev_page"), disabled=(current_page == 0)):
                    callbacks["update_state"]("failed_pdfs_page", current_page - 1)
                    st.rerun()
            with col_p2:
                st.markdown(f"**Page {current_page + 1} / {total_pages}**")
            with col_p3:
                if st.button(t("next_page"), disabled=(current_page == total_pages - 1)):
                    callbacks["update_state"]("failed_pdfs_page", current_page + 1)
                    st.rerun()

            for _, row in batch_df.iterrows():
                with st.container(border=True):
                    pmid = str(row["pmid"])
                    display_title = row.get("title", f"PMID {pmid}")
                    target_path = os.path.join(PDF_DIR, f"{pmid}.pdf")

                    st.markdown(f"**{display_title}**")

                    # Status Badge
                    status = str(row.get("pdf_download_status", "Failed"))
                    file_exists = callbacks["check_file_cache"](pmid, target_path)

                    if file_exists:
                        if "Manual" not in status and "Downloaded" not in status and "Exists" not in status:
                            st.info(f"{t('status_manual')} (Auto-detected)")
                            db_manager.update_article(pmid, pdf_download_status="Downloaded (Detected)")
                            callbacks["update_file_cache"](pmid, True)
                        else:
                            st.success(t("status_verified"))
                    else:
                        st.error(t("status_failed"))

                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button(f"{t('check_file_btn')} ({pmid})", key=f"check_{pmid}"):
                            file_exists_physical = os.path.exists(target_path)
                            callbacks["update_file_cache"](pmid, file_exists_physical)
                            if file_exists_physical:
                                db_manager.update_article(pmid, pdf_download_status="Downloaded (Manual)")
                                st.toast(t("file_verified", pmid=pmid), icon="✅")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error(t("file_not_found", path=target_path))
                    with c2:
                        if st.button(f"{t('skip_file_btn')} ({pmid})", key=f"skip_{pmid}"):
                            db_manager.update_article(pmid, pdf_download_status="Skipped_User")
                            st.toast(t("file_skipped", pmid=pmid), icon="⏭️")
                            time.sleep(0.5)
                            st.rerun()

    # --- Section 2: Analysis ---
    st.divider()
    st.subheader(t("analysis_section"))

    ready_count = 0
    df = db_manager.get_articles_df()
    if not df.empty and "pdf_download_status" in df.columns:
        ready_mask = df["pdf_download_status"].astype(str).str.contains(r"Downloaded|Exists", case=False, na=False)
        ready_count = len(df[ready_mask])

    st.info(t("analysis_ready", count=ready_count))

    auto_analyze = False
    if state.get("run_mode") == "scoping" and state.get("scoping_agreed"):
        if not df.empty and "pipeline_status" in df.columns:
            unparsed_mask = ready_mask & (df["pipeline_status"].fillna(0) < 2)
            if unparsed_mask.any():
                auto_analyze = True

    if auto_analyze or st.button(t("analysis_btn"), type="primary"):
        run_path = vm.create_run(config)
        vm.archive_current_data(run_path, TABLES_DIR, RAW_DATA_DIR)
        st.toast(f"Run archived to {os.path.basename(run_path)}", icon="📦")

        progress_bar = st.progress(0)
        status_text = st.empty()

        df = db_manager.get_articles_df()
        doc_ready_mask = df["pdf_download_status"].astype(str).str.contains(r"Downloaded|Exists", case=False, na=False)
        ready_pmids = df[doc_ready_mask]["pmid"].astype(str).tolist()

        status_text.text("PDF 텍스트 추출 (GROBID)...")
        total_ready = len(ready_pmids)
        for idx, pmid in enumerate(ready_pmids):
            status_text.text(f"[{idx + 1}/{total_ready}] Parsing PDF for PMID {pmid}...")
            pdf_path = os.path.join(PDF_DIR, f"{pmid}.pdf")
            tei_path = os.path.join(TEI_DIR, f"{pmid}.xml")
            if os.path.exists(pdf_path) and not os.path.exists(tei_path):
                tei_xml = grobid_client.process_pdf(pdf_path)
                if not tei_xml or len(tei_xml.strip()) < 500:
                    status_text.text(f"[{idx + 1}/{total_ready}] GROBID failed for {pmid}. Using Fallback Parser...")
                    tei_xml = fallback_parser.extract_text_from_pdf(pdf_path)
                    db_manager.update_article(pmid, pdf_download_status="Parsed (Fallback)", pipeline_status=2)
                else:
                    db_manager.update_article(pmid, pdf_download_status="Parsed (GROBID)", pipeline_status=2)

                if tei_xml:
                    with open(tei_path, "w", encoding="utf-8") as f:
                        f.write(tei_xml)
        progress_bar.progress(50)

        if os.path.exists(TEI_DIR):
            status_text.text("비뚤림 위험(RoB) 평가 진행 중...")
            rob_gen = assessor.batch_assess_rob(TEI_DIR, allowed_pmids=ready_pmids)
            if rob_gen:
                for current_idx, total_count, pmid in rob_gen:
                    status_text.text(f"[{current_idx}/{total_count}] Completed Risk of Bias for PMID {pmid}.")
                    progress = 50 + int((current_idx / total_count) * 25)
                    progress_bar.progress(progress)
        progress_bar.progress(75)

        status_text.text("데이터 추출 중...")
        tei_files = [f for f in os.listdir(TEI_DIR) if f.endswith(".xml") and f.replace(".xml", "") in ready_pmids]

        if tei_files:
            import json

            from src.extract import pico_extractor
            from src.parse import tei_parser

            total_tei = len(tei_files)
            for idx, tei_file in enumerate(tei_files):
                try:
                    pmid = tei_file.replace(".xml", "")
                    status_text.text(f"[{idx + 1}/{total_tei}] Extracting PICO for PMID {pmid}...")
                    progress = 75 + int(((idx + 1) / total_tei) * 25)
                    progress_bar.progress(progress)

                    full_text = tei_parser.extract_text_from_tei(os.path.join(TEI_DIR, tei_file), optimize_context=True)
                    if full_text == "CLOUDFLARE_BLOCK":
                        db_manager.update_article(
                            pmid,
                            pdf_download_status="Failed (Cloudflare Block)",
                            pipeline_status=-1,
                            pico_data="",
                            rob_data="",
                        )
                        continue
                    elif full_text:
                        text_snippet = (full_text[:8000] + "...") if len(full_text) > 8000 else full_text
                        data = pico_extractor.extract_pico_multi_agent(text_snippet)
                        if data:
                            db_manager.update_article(pmid, pico_data=json.dumps(data, ensure_ascii=False))
                except Exception as e:
                    print(f"Error extracting PICO for {tei_file}: {e}")

        progress_bar.empty()
        status_text.empty()
        st.success(t("analysis_complete"))

        # In scaffolding mode we auto jump
        if state.get("run_mode") == "scoping" and state.get("scoping_agreed"):
            st.info("🚀 Scoping 모드 작동 중: 다음 단계(최종 보고서)로 자동 진입합니다...")
            time.sleep(2)
            callbacks["set_tab"](4)
        else:
            st.rerun()

    if ready_count > 0:
        st.divider()
        col_next, _ = st.columns([1, 4])
        with col_next:
            if st.button(f"{t('tabs')[3]} >", type="primary", use_container_width=True):
                callbacks["next_step"]()
