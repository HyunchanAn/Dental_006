import json
import time

import pandas as pd
import streamlit as st


def render(config: dict, state: dict, **callbacks) -> None:
    """
    Renders Step 4: Data Extraction and Human Verification.
    """
    t = callbacks.get("t", lambda k, **kw: k)
    db_manager = callbacks["db_manager"]

    st.header("Step 4: Data Extraction Verification")

    articles_df = db_manager.get_articles_df()

    pico_records = []
    rob_records = []
    if not articles_df.empty:
        for _, row in articles_df.iterrows():
            if row.get("pico_data"):
                try:
                    pico_records.append(json.loads(row["pico_data"]))
                except Exception:
                    pass
            if row.get("rob_data"):
                try:
                    rob_json = json.loads(row["rob_data"])
                    flat_result = {"pmid": str(row["pmid"])}
                    for domain, details in rob_json.items():
                        if domain == "pmid":
                            continue
                        if isinstance(details, dict):
                            flat_result[f"{domain}_Level"] = details.get("level", "Unclear")
                            quote = details.get("quote", "")
                            reasoning = details.get("reasoning", "")
                            flat_result[f"{domain}_Explanation"] = f"Quote: '{quote}' | Reasoning: {reasoning}"
                        else:
                            flat_result[domain] = str(details)
                    rob_records.append(flat_result)
                except Exception:
                    pass

    if len(pico_records) == 0 and len(rob_records) == 0:
        st.info("데이터가 추출되지 않았습니다. 3단계를 완료해주세요.")
        return

    st.subheader("🧐 Human-in-the-Loop Verification")
    st.info(
        "AI가 추출한 데이터를 확인하고 필요한 경우 직접 수정하세요. 수정 완료 후 반드시 '확정 및 저장' 버튼을 눌러야 다음 단계로 진행할 수 있습니다."
    )

    pico_df = pd.DataFrame(pico_records)
    if not pico_df.empty and "pmid" in pico_df.columns:
        pico_df["pmid"] = pico_df["pmid"].apply(
            lambda x: f"https://pubmed.ncbi.nlm.nih.gov/{x}/" if pd.notna(x) and str(x).strip() else x
        )

    rob_df = pd.DataFrame(rob_records)
    if not rob_df.empty and "pmid" in rob_df.columns:
        rob_df["pmid"] = rob_df["pmid"].apply(
            lambda x: f"https://pubmed.ncbi.nlm.nih.gov/{x}/" if pd.notna(x) and str(x).strip() else x
        )

    st.markdown("#### PICO Data")
    edited_pico = st.data_editor(
        pico_df,
        num_rows="dynamic",
        key="pico_editor",
        use_container_width=True,
        column_config={"pmid": st.column_config.LinkColumn("PMID", display_text=r"https://pubmed\.ncbi\.nlm\.nih\.gov/(.*)/")},
    )

    st.markdown("#### Risk of Bias (RoB)")
    edited_rob = st.data_editor(
        rob_df,
        num_rows="dynamic",
        key="rob_editor",
        use_container_width=True,
        column_config={"pmid": st.column_config.LinkColumn("PMID", display_text=r"https://pubmed\.ncbi\.nlm\.nih\.gov/(.*)/")},
    )

    if st.button("💾 확정 및 저장 (Confirm & Save)"):
        # Save back to DB
        for _, row in edited_pico.iterrows():
            if pd.notna(row.get("pmid")):
                raw_pmid = str(row["pmid"]).replace("https://pubmed.ncbi.nlm.nih.gov/", "").replace("/", "")
                pico_dict = row.to_dict()
                pico_dict["pmid"] = raw_pmid
                db_manager.update_article(
                    raw_pmid, pico_data=json.dumps(pico_dict, ensure_ascii=False), _is_manual=True, is_user_verified=1
                )

        for _, row in edited_rob.iterrows():
            if pd.notna(row.get("pmid")):
                raw_pmid = str(row["pmid"]).replace("https://pubmed.ncbi.nlm.nih.gov/", "").replace("/", "")
                rob_dict: dict = {"pmid": raw_pmid}
                domains = ["Randomization", "Deviations", "MissingData", "Measurement", "Reporting"]
                for domain in domains:
                    level = row.get(f"{domain}_Level", "Unclear")
                    explanation = row.get(f"{domain}_Explanation", "")
                    quote = ""
                    reasoning = explanation
                    if "Quote: '" in explanation and "' | Reasoning: " in explanation:
                        parts = explanation.split("' | Reasoning: ")
                        if len(parts) == 2:
                            quote = parts[0].replace("Quote: '", "")
                            reasoning = parts[1]
                    rob_dict[domain] = {"quote": quote, "reasoning": reasoning, "level": level}
                db_manager.update_article(
                    raw_pmid, rob_data=json.dumps(rob_dict, ensure_ascii=False), _is_manual=True, is_user_verified=1
                )

        callbacks["update_state"]("human_verified", True)
        st.success("데이터가 확정되었습니다! 이제 다음 단계로 넘어갈 수 있습니다.")
        time.sleep(1)
        st.rerun()

    if state.get("human_verified", False):
        st.divider()
        col_next, _ = st.columns([1, 4])
        with col_next:
            if st.button(f"{t('tabs')[4]} >", type="primary", use_container_width=True):
                callbacks["next_step"]()
