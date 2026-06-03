import os
from datetime import datetime

import streamlit as st

from src.llm import synthesizer
from src.report import generator

DATA_DIR = "data"


def render(config: dict, state: dict, **callbacks) -> None:
    """
    Renders Step 5: Final Report Generation.
    """

    st.header("Step 5: Final Report")
    st.warning(
        "⚠️ 주의: 모든 비뚤림 위험(RoB) 평가 및 데이터 추출 결과는 AI가 생성한 '제안'입니다. 학술적 엄밀성을 위해 반드시 최종 검토를 거쳐주세요."
    )

    current_lang = state.get("lang", "KO")
    report_filename = f"report_{current_lang}.md"
    report_path = os.path.join(DATA_DIR, report_filename)

    auto_generate = False
    if state.get("run_mode") == "scoping" and state.get("scoping_agreed"):
        if not os.path.exists(report_path) and not state.get("generating_report", False):
            auto_generate = True

    if st.button("📄 보고서 생성 (Generate Report)") or auto_generate:
        callbacks["update_state"]("generating_report", True)

        with st.spinner("AI is synthesizing the answer to your PICO question..."):
            synthesis_result = synthesizer.synthesize_answer(
                config,
                lang=current_lang,
            )

        generator.generate_report(
            state.get("stats", {}),
            config,
            report_path,
            lang=current_lang,
            synthesis_result=synthesis_result,
            run_mode=state.get("run_mode", "hitl"),
        )
        callbacks["update_state"]("generating_report", False)
        st.success("보고서가 생성되었습니다!")
        st.rerun()

    if os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            report_content = f.read()
            st.markdown(report_content, unsafe_allow_html=True)

            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            download_filename = f"report_{current_lang}_{timestamp_str}.md"

            st.download_button(
                label="보고서 다운로드 (Download Report)",
                data=report_content,
                file_name=download_filename,
                mime="text/markdown",
            )
