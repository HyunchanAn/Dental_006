import time
from datetime import datetime, timedelta

import streamlit as st

from src.ingest import pubmed


def render(config: dict, state: dict, **callbacks) -> None:
    """
    Renders Step 1: Scoping, 3-Scope PICO Hit-Count Selection, and PubTator 3.0 Supplemental Search.
    """
    t = callbacks.get("t", lambda k, **kw: k)
    st.header(t("step1_header"))

    st.subheader("AI PICO Assistant (3-Scope Query & Hit Count Preview)")
    topic_description = st.text_area(
        "연구 주제를 평문으로 서술하세요 / Plain-Language Research Question",
        placeholder="예: 65세 이상 노인에게 치과 임플란트가 가철성 의치보다 저작 효율과 생존율이 높은지 비교하고 싶다.",
        height=100,
    )

    is_scoping = state.get("run_mode") == "scoping" and state.get("scoping_agreed")
    btn_label = (
        "AI 스코핑 자동 실행 (Auto Run End-to-End)"
        if is_scoping
        else "3가지 스코프 PICO 후보 및 예상 검색 건수 조회"
    )

    if st.button(btn_label, type="primary" if is_scoping else "secondary"):
        if topic_description.strip():
            from src.llm import pico_extractor

            today = datetime.now()
            end_date = today.strftime("%Y/%m/%d")
            start_date = (today - timedelta(days=20 * 365)).strftime("%Y/%m/%d")

            with st.spinner("Gemma 4가 3가지 스코프 후보를 생성하고 PubMed 예상 검색 건수를 조회 중입니다..."):
                candidates = pico_extractor.generate_pico_scope_candidates(
                    topic_description,
                    email=config.get("email"),
                    api_key=config.get("api_key"),
                    mindate=start_date,
                    maxdate=end_date,
                )
                callbacks["update_state"]("pico_scope_candidates", candidates)

                rec = next((c for c in candidates if c.get("recommended")), candidates[0])
                if is_scoping and rec.get("hit_count", 0) >= 10:
                    callbacks["update_config_batch"](
                        {**rec.get("picos", {}), "custom_query": rec.get("query", "")}
                    )
                    callbacks["update_state"]("auto_trigger_search", True)
                    time.sleep(0.5)
                    st.rerun()
        else:
            st.warning("먼저 연구 주제를 입력해 주세요.")

    scope_candidates = state.get("pico_scope_candidates") or []
    if scope_candidates:
        st.markdown("#### 스코프 후보 비교 및 선택 (PubMed Hit Count)")
        cols = st.columns(len(scope_candidates))
        for idx, cand in enumerate(scope_candidates):
            with cols[idx]:
                rec_tag = " [권장]" if cand.get("recommended") else ""
                st.markdown(f"`{cand['label']}{rec_tag}`")
                st.metric("예상 논문 건수 (PubMed)", f"{cand.get('hit_count', 0):,}건")
                st.caption(f"[{cand.get('suitability', 'OPTIMAL')}] {cand.get('guidance', '')}")
                st.code(cand.get("query", ""), language="text")

        option_labels = [
            f"{c['label']} — {c.get('hit_count', 0):,}건 ({c.get('suitability', 'OPTIMAL')})"
            for c in scope_candidates
        ]
        default_idx = next(
            (i for i, c in enumerate(scope_candidates) if c.get("recommended")), 0
        )
        selected_label = st.radio(
            "적용할 검색 스코프 후보를 선택하세요",
            option_labels,
            index=default_idx,
            key="selected_pico_scope_radio",
        )
        chosen_idx = option_labels.index(selected_label)
        if st.button("선택한 스코프 후보를 PICO 및 검색식에 적용", type="primary"):
            chosen = scope_candidates[chosen_idx]
            callbacks["update_config_batch"](
                {
                    **chosen.get("picos", {}),
                    "custom_query": chosen.get("query", ""),
                }
            )
            st.success(f"{chosen['label']} 후보가 적용되었습니다. 아래에서 세부 수정 후 검색을 실행할 수 있습니다.")
            st.rerun()

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
            "custom_query": "",
        }
        callbacks["update_config_batch"](new_picos)
        st.success(t("config_saved"))
        st.rerun()

    default_query = config.get("custom_query") or callbacks["construct_search_query"](config)
    editable_query = st.text_area(t("generated_query"), value=default_query, height=100)

    # Optional PubTator 3.0 Entity/Relation Supplemental Search (#58)
    use_pubtator = st.checkbox(
        "PubTator 3.0 개념·관계 보조 검색 포함 (약물·전신질환·유전자 동의어 보완)",
        value=bool(config.get("use_pubtator_supplement", False)),
    )
    pubtator_query_text = ""
    if use_pubtator:
        default_pt_seed = config.get("pubtator_query") or " ".join(
            filter(None, [config.get("intervention", ""), config.get("population", "")])
        )
        pubtator_query_text = st.text_input(
            "PubTator 3.0 보조 검색 키워드 또는 정규화 개체/관계식 (예: Denosumab Osteonecrosis 또는 @CHEMICAL_Denosumab)",
            value=default_pt_seed,
        )

    st.divider()
    col_s1, col_s2 = st.columns([1, 2])
    with col_s1:
        max_ret = st.number_input(t("max_articles"), min_value=1, max_value=1000, value=20)
    with col_s2:
        auto_search = callbacks["pop_state"]("auto_trigger_search", False)

        if st.button(t("search_button")) or auto_search:
            run_cfg = {
                **config,
                "use_pubtator_supplement": use_pubtator,
                "pubtator_query": pubtator_query_text.strip(),
            }
            callbacks["update_config_batch"](
                {
                    "custom_query": editable_query.strip(),
                    "use_pubtator_supplement": use_pubtator,
                    "pubtator_query": pubtator_query_text.strip(),
                }
            )
            with st.spinner(t("searching")):
                callbacks["execute_pubmed_search"](editable_query.strip(), max_ret, run_cfg)

    # External DB Upload Expander
    st.divider()
    with st.expander("외부 DB 검색 결과 업로드 (External DB Upload)", expanded=False):
        st.markdown("PubMed 외 Embase, Cochrane 등에서 익스포트한 `RIS` 또는 `CSV/TSV` 파일을 업로드하세요.")
        source_db = st.selectbox("출처 DB (Source DB)", ["embase", "cochrane", "scopus", "other_external"])
        uploaded_file = st.file_uploader("파일 업로드 (RIS, CSV, TSV)", type=["ris", "csv", "tsv"])

        if uploaded_file and st.button("업로드 및 중복 제거 실행"):
            with st.spinner("파일 파싱 및 중복 제거 중..."):
                from src.ingest import deduplicator, external_parser
                from src.utils import db_manager

                file_ext = uploaded_file.name.split(".")[-1].lower()
                if file_ext == "ris":
                    string_content = uploaded_file.getvalue().decode("utf-8")
                    new_df = external_parser.parse_ris(string_content, source_db=source_db)
                else:
                    new_df = external_parser.parse_csv(uploaded_file, source_db=source_db)

                existing_df = db_manager.get_articles_df()
                deduped_df, stats = deduplicator.deduplicate_records(existing_df, new_df)
                db_manager.import_external_results(deduped_df)

                old_uploaded = int(db_manager.get_meta("total_external_uploaded", 0))
                old_dups = int(db_manager.get_meta("total_duplicates_removed", 0))
                db_manager.set_meta("total_external_uploaded", old_uploaded + stats["total_uploaded"])
                db_manager.set_meta("total_duplicates_removed", old_dups + stats["duplicates_removed"])

                st.success(
                    f"업로드 완료: 총 업로드 {stats['total_uploaded']}건, 중복 제거 {stats['duplicates_removed']}건, 신규 적재 {stats['new_records']}건"
                )
                callbacks["update_state"](
                    "stats", {"total_found": len(existing_df) + stats["new_records"]}
                )

    stats = state.get("stats", {})
    if stats.get("total_found", 0) > 0:
        st.divider()
        col_next, _ = st.columns([1, 4])
        with col_next:
            if st.button(f"{t('tabs')[1]} >", type="primary", use_container_width=True):
                callbacks["next_step"]()
