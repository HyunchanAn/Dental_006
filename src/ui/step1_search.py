import time
from datetime import datetime, timedelta

import streamlit as st

from src.ingest import pubmed


def render(config: dict, state: dict, **callbacks) -> None:
    """
    Renders Step 1: Scoping and Search Strategy.
    """
    t = callbacks.get("t", lambda k, **kw: k)  # translation function
    st.header(t("step1_header"))

    # AI PICO Extraction
    st.subheader("🤖 AI PICO Assistant")
    topic_description = st.text_area(
        "연구 주제를 자유롭게 서술하세요 / Research Topic Description",
        placeholder="예: 65세 이상 노인에게 치과 임플란트가 틀니보다 저작 효율이 좋은지 알고 싶어.",
        height=100,
    )

    is_scoping = state.get("run_mode") == "scoping" and state.get("scoping_agreed")
    btn_label = "🚀 AI 스코핑 자동 실행 (Auto Run End-to-End)" if is_scoping else "✨ PICO 자동 추출 (Auto-extract with AI)"

    if st.button(btn_label, type="primary" if is_scoping else "secondary"):
        if topic_description:
            from src.llm import pico_extractor

            max_retries = 3 if is_scoping else 1
            feedback = ""
            success = False

            for attempt in range(max_retries):
                with st.spinner(f"AI가 PICO를 분석 중입니다... (시도 {attempt + 1}/{max_retries})"):
                    extracted = pico_extractor.extract_pico_from_description(topic_description, feedback)
                    if extracted:
                        callbacks["update_config_batch"](extracted)
                        # We need to use updated config for the query
                        current_config = {**config, **extracted}

                        if not is_scoping:
                            st.success("PICO 추출 완료! 아래 필드가 업데이트되었습니다.")
                            success = True
                            break

                        # In scoping mode, verify the query
                        query = callbacks["construct_search_query"](current_config)
                        today = datetime.now()
                        end_date = today.strftime("%Y/%m/%d")
                        start_date = (today - timedelta(days=20 * 365)).strftime("%Y/%m/%d")
                        _, total_count = pubmed.fetch_pmids(
                            query,
                            max_ret=1,
                            mindate=start_date,
                            maxdate=end_date,
                            email=current_config.get("email"),
                            api_key=current_config.get("api_key"),
                        )
                        if total_count >= 20:
                            st.success(f"PICO 추출 및 쿼리 생성 완료! 예상 논문 수: {total_count}")
                            callbacks["update_config"]("query", query)
                            success = True
                            callbacks["update_state"]("auto_trigger_search", True)
                            break
                        else:
                            feedback = f"The query '{query}' returned {total_count} results. We need at least 20 results. Please use broader MeSH terms or synonyms. Remove overly restrictive constraints."
                            st.warning(
                                f"검색 결과가 {total_count}건입니다 (최소 20건 필요). 조건을 완화하여 재시도합니다... (시도 {attempt + 1}/{max_retries})"
                            )
                    else:
                        st.error("PICO 추출에 실패했습니다.")
                        break

            if success:
                time.sleep(1)
                st.rerun()
            elif is_scoping:
                st.error("3회 시도에도 불구하고 검색 결과가 20건 미만입니다. 연구 주제를 더 포괄적으로 변경해주세요.")
        else:
            st.warning("먼저 연구 주제를 입력해주세요.")

    st.divider()
    st.subheader("PICO Details")

    col1, col2 = st.columns(2)
    with col1:
        population = st.text_input(t("population"), value=config.get("population", ""))
        intervention = st.text_input(t("intervention"), value=config.get("intervention", ""))
        comparison = st.text_input(t("comparison"), value=config.get("comparison", ""))
    with col2:
        outcome = st.text_input(t("outcome"), value=config.get("outcome", ""))
        study_design = st.text_input(t("study_design"), value=config.get("study_design", ""))

    if st.button(t("save_config")):
        new_picos = {
            "population": population,
            "intervention": intervention,
            "comparison": comparison,
            "outcome": outcome,
            "study_design": study_design,
        }
        callbacks["update_config_batch"](new_picos)
        st.success(t("config_saved"))
        # Force a rerun to pick up the updated query immediately
        st.rerun()

    query = callbacks["construct_search_query"](config)
    st.text_area(t("generated_query"), value=query, height=100)

    st.divider()
    col_s1, col_s2 = st.columns([1, 2])
    with col_s1:
        max_ret = st.number_input(t("max_articles"), min_value=1, max_value=1000, value=20)
    with col_s2:
        # Retrieve auto_trigger_search flag without leaving it in state permanently
        auto_search = callbacks["pop_state"]("auto_trigger_search", False)

        if st.button(t("search_button")) or auto_search:
            with st.spinner(t("searching")):
                callbacks["execute_pubmed_search"](query, max_ret, config)

    # Add External DB Upload Expander
    st.divider()
    with st.expander("📂 외부 DB 검색 결과 업로드 (External DB Upload)", expanded=False):
        st.markdown("PubMed 외 Embase, Cochrane 등에서 익스포트한 **RIS** 또는 **CSV/TSV** 파일을 업로드하세요.")
        source_db = st.selectbox("출처 DB (Source DB)", ["embase", "cochrane", "scopus", "other_external"])
        uploaded_file = st.file_uploader("파일 업로드 (RIS, CSV, TSV)", type=["ris", "csv", "tsv"])

        if uploaded_file and st.button("업로드 및 중복 제거 실행"):
            with st.spinner("파일 파싱 및 중복 제거 중..."):
                from src.ingest import deduplicator, external_parser
                from src.utils import db_manager

                # Parse
                file_ext = uploaded_file.name.split(".")[-1].lower()
                if file_ext == "ris":
                    # ris expects string content
                    string_content = uploaded_file.getvalue().decode("utf-8")
                    new_df = external_parser.parse_ris(string_content, source_db=source_db)
                else:
                    # csv/tsv expects file stream
                    new_df = external_parser.parse_csv(uploaded_file, source_db=source_db)

                # Deduplicate
                existing_df = db_manager.get_articles_df()
                deduped_df, stats = deduplicator.deduplicate_records(existing_df, new_df)

                # Save
                db_manager.import_external_results(deduped_df)

                # Update stats
                old_uploaded = int(db_manager.get_meta("total_external_uploaded", 0))
                old_dups = int(db_manager.get_meta("total_duplicates_removed", 0))

                db_manager.set_meta("total_external_uploaded", old_uploaded + stats["total_uploaded"])
                db_manager.set_meta("total_duplicates_removed", old_dups + stats["duplicates_removed"])

                st.success(
                    f"업로드 완료! (총 업로드: {stats['total_uploaded']}건, 중복 제거: {stats['duplicates_removed']}건, 신규 적재: {stats['new_records']}건)"
                )
                callbacks["update_state"](
                    "stats", {"total_found": len(existing_df) + stats["new_records"]}
                )  # update local state stats to enable next step

    # Navigation Button (Step 1 -> Step 2)
    stats = state.get("stats", {})
    if stats.get("total_found", 0) > 0:
        st.divider()
        col_next, _ = st.columns([1, 4])
        with col_next:
            if st.button(f"{t('tabs')[1]} >", type="primary", use_container_width=True):
                callbacks["next_step"]()
