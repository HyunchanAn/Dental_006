import time

import pandas as pd
import streamlit as st

from src.screen import screener


def render(config: dict, state: dict, **callbacks) -> None:
    """
    Renders Step 2: Automated Screening.
    """
    t = callbacks.get("t", lambda k, **kw: k)
    db_manager = callbacks["db_manager"]

    st.header(t("step2_header"))

    df = db_manager.get_articles_df()

    if not df.empty:
        disp_df = df[["pmid", "title", "journal", "pub_year"]].copy()
        disp_df["pmid"] = disp_df["pmid"].apply(
            lambda x: f"https://pubmed.ncbi.nlm.nih.gov/{x}/" if pd.notna(x) and str(x).strip() else x
        )
        st.dataframe(
            disp_df,
            use_container_width=True,
            column_config={
                "pmid": st.column_config.LinkColumn("PMID", display_text=r"https://pubmed\.ncbi\.nlm\.nih\.gov/(.*)/")
            },
        )

        auto_start_screening = False
        if state.get("run_mode") == "scoping" and state.get("scoping_agreed"):
            # Check if ANY article is unscreened (df.isna().any()) or empty string
            if (
                "screening_decision" not in df.columns
                or df["screening_decision"].isna().any()
                or (df["screening_decision"] == "").any()
            ):
                auto_start_screening = True

        if st.button(t("start_screening")) or auto_start_screening:
            st.write("스크리닝을 시작합니다. 중단되어도 다시 시작하면 이어서 진행됩니다 (Resume).")
            progress_bar = st.progress(0)
            status_text = st.empty()

            screen_gen = screener.screen_abstracts(df, config)

            for current_idx, total_count, pmid, result in screen_gen:
                progress_bar.progress(current_idx / total_count)
                if result:
                    status_text.text(
                        f"[{current_idx}/{total_count}] Screening PMID {pmid}... Decision: {result['screening_decision']}"
                    )
                    db_manager.update_article(
                        pmid,
                        screening_decision=result["screening_decision"],
                        screening_reason=result["screening_reason"],
                        pipeline_status="SCREENED",
                    )
                else:
                    status_text.text(f"[{current_idx}/{total_count}] Skipping PMID {pmid} (Already screened)")

            status_text.text(f"Screening completed! ({total_count}/{total_count})")

            # Reload df from DB to update stats
            df = db_manager.get_articles_df()

            screened = len(df[df["screening_decision"].notna() & (df["screening_decision"] != "")])
            included = len(df[df["screening_decision"] == "Included"])
            excluded = screened - included

            callbacks["update_stats"](screened=screened, included=included, excluded=excluded)

            if state.get("run_mode") == "scoping" and state.get("scoping_agreed"):
                st.info("🚀 Scoping 모드 작동 중: 다음 단계(분석 파이프라인)로 자동 진입합니다...")
                time.sleep(2)
                callbacks["set_tab"](2)
            else:
                st.rerun()

        # Show Screening Results if available
        if (
            "screening_decision" in df.columns
            and len(df[df["screening_decision"].notna() & (df["screening_decision"] != "")]) > 0
        ):
            st.divider()
            st.subheader(t("screening_results"))
            stats = state.get("stats", {})
            st.metric(
                t("inclusion_rate"),
                f"{stats.get('included', 0)} / {stats.get('screened', 0)}",
            )

            # PRISMA Flow Diagram rendering
            st.subheader("PRISMA Flow Diagram")
            total_found = len(df)
            total_screened = stats.get("screened", 0)
            total_included = stats.get("included", 0)

            if "exclusion_category" in df.columns:
                exclusion_counts = df[df["screening_decision"] == "Excluded"]["exclusion_category"].value_counts().to_dict()
                exclusion_html = "".join([f"<li>{k}: {v}</li>" for k, v in exclusion_counts.items() if str(k).strip()])
            else:
                exclusion_html = f"<li>{t('prisma_no_category')}</li>"

            prisma_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto; padding: 20px; background-color: #f9f9f9; border-radius: 10px; border: 1px solid #ddd;">
                <h3 style="text-align: center; color: #333;">{t("prisma_title")}</h3>
                <div style="text-align: center; padding: 10px; margin: 10px; background-color: #e3f2fd; border: 1px solid #90caf9; border-radius: 5px;">
                    <strong>{t("prisma_id")}</strong><br>
                    {t("prisma_id_desc")}<br>
                    (n = {total_found})
                </div>
                <div style="text-align: center; font-size: 24px;">&#8595;</div>
                <div style="text-align: center; padding: 10px; margin: 10px; background-color: #fff3e0; border: 1px solid #ffcc80; border-radius: 5px; display: flex; justify-content: space-between;">
                    <div style="width: 45%;">
                        <strong>{t("prisma_screened")}</strong><br>
                        {t("prisma_screened_desc")}<br>
                        (n = {total_screened})
                    </div>
                    <div style="width: 45%; border-left: 2px solid #ffcc80; padding-left: 10px; text-align: left;">
                        <strong>{t("prisma_excluded")}</strong> (n = {total_screened - total_included})<br>
                        <ul style="margin: 0; padding-left: 20px; font-size: 0.9em;">
                            {exclusion_html}
                        </ul>
                    </div>
                </div>
                <div style="text-align: center; font-size: 24px;">&#8595;</div>
                <div style="text-align: center; padding: 10px; margin: 10px; background-color: #e8f5e9; border: 1px solid #a5d6a7; border-radius: 5px;">
                    <strong>{t("prisma_included")}</strong><br>
                    {t("prisma_included_desc")}<br>
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

            st.data_editor(
                df[display_cols],
                hide_index=True,
                column_config={
                    "pmid": st.column_config.TextColumn("PMID", disabled=True),
                    "title": st.column_config.TextColumn("Title", disabled=True),
                    "screening_decision": st.column_config.SelectboxColumn("Decision", options=["Included", "Excluded"]),
                    "screening_reason": st.column_config.TextColumn("Reason"),
                    "exclusion_category": st.column_config.SelectboxColumn(
                        "Exclusion Category",
                        options=[
                            "Wrong Population",
                            "Wrong Intervention",
                            "Wrong Comparison",
                            "Wrong Outcome",
                            "Wrong Study Design",
                            "Not Relevant",
                            "",
                        ],
                    ),
                },
                use_container_width=True,
                key="screening_editor",
            )
            
            # Check for edits and save them
            editor_state = st.session_state.get("screening_editor", {})
            if editor_state.get("edited_rows"):
                for row_idx_str, edits in editor_state["edited_rows"].items():
                    row_idx = int(row_idx_str)
                    pmid = str(df.iloc[row_idx]["pmid"])
                    
                    # Update kwargs mapped to DB columns
                    update_kwargs = {"_is_manual": True, "is_user_verified": 1}
                    if "screening_decision" in edits:
                        update_kwargs["screening_decision"] = edits["screening_decision"]
                    if "screening_reason" in edits:
                        update_kwargs["screening_reason"] = edits["screening_reason"]
                    if "exclusion_category" in edits:
                        update_kwargs["exclusion_category"] = edits["exclusion_category"]
                        
                    db_manager.update_article(pmid, **update_kwargs)
                
                # Clear session state so it doesn't loop, but st.data_editor manages its own state
                # We need to rerun to refresh DB stats, but wait a moment
                st.toast("✅ 수동 변경사항이 저장되었습니다.")
                time.sleep(0.5)
                # To clear the edited state, we can increment a key or just let Streamlit handle it
                # Streamlit clears edited_rows upon rerun!
                st.rerun()

            # Navigation Button (Step 2 -> Step 3)
            if stats.get("included", 0) > 0:
                st.divider()
                col_next, _ = st.columns([1, 4])
                with col_next:
                    if st.button(f"{t('tabs')[2]} >", type="primary", use_container_width=True, key="next_step3"):
                        callbacks["next_step"]()
    else:
        st.info(t("search_first"))
