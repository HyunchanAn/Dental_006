import streamlit as st
import subprocess
import requests
import time

def render(config: dict, state: dict, **callbacks) -> None:
    """
    Renders the sidebar including mode selection, language, API keys, and system status.
    """
    with st.sidebar:
        # Language Selector
        lang = state.get("lang", "KO")
        selected_lang = st.radio(
            "언어 / Language",
            ["KO", "EN"],
            index=0 if lang == "KO" else 1,
            horizontal=True,
        )
        if selected_lang != lang:
            callbacks["update_state"]("lang", selected_lang)
            st.rerun()

        st.divider()

        # API Settings
        st.subheader("API Settings")
        email_input = st.text_input(
            "Email (Required for NCBI)",
            value=config.get("email", ""),
        )
        api_key_input = st.text_input(
            "NCBI API Key (Optional)",
            value=config.get("api_key", ""),
            type="password",
        )

        if email_input != config.get("email", "") or api_key_input != config.get("api_key", ""):
            callbacks["update_config"]("email", email_input)
            callbacks["update_config"]("api_key", api_key_input)
            st.toast("Settings saved!", icon="💾")
            
        st.divider()

        # System Status
        st.subheader("시스템 상태 점검 (System Status)")
        col_st1, col_st2 = st.columns(2)
        with col_st1:
            try:
                result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    st.success("✅ Docker", icon="🐳")
                else:
                    st.error("❌ Docker", icon="🐳")
            except Exception:
                st.error("❌ Docker", icon="🐳")

        with col_st2:
            try:
                response = requests.get("http://localhost:11434/", timeout=2)
                if response.status_code == 200:
                    st.success("✅ Ollama", icon="🦙")
                else:
                    st.error("❌ Ollama", icon="🦙")
            except Exception:
                st.error("❌ Ollama", icon="🦙")
                
        if st.button("🔄 상태 새로고침 (Refresh)", use_container_width=True):
            st.rerun()
            
        st.divider()

        # Mode Selector
        st.subheader("실행 모드 / Run Mode")
        run_mode = state.get("run_mode", "hitl")
        mode_val = st.radio(
            "Mode",
            ["Human-in-the-Loop Mode", "Full AI-driven Scoping Mode"],
            index=0 if run_mode == "hitl" else 1,
            label_visibility="collapsed",
        )
        new_run_mode = "scoping" if "Scoping" in mode_val else "hitl"
        if new_run_mode != run_mode:
            callbacks["update_state"]("run_mode", new_run_mode)
            st.rerun()

        if state.get("run_mode") == "scoping":
            st.warning(
                "⚠️ **예비 타당성 검토 모드**\n\n본 모드는 예비 연구 기획 및 문헌 탐색(Scoping) 목적으로만 제한됩니다. LLM 추론 특성상 누락이나 환각이 포함될 수 있으므로, 실제 정밀 임상 연구 및 학술지 출판물(Publication) 데이터로의 직접적인 인용 및 활용을 절대 금지합니다."
            )
            scoping_agreed = st.checkbox(
                "위 경고사항을 확인했으며, 동의합니다.", value=state.get("scoping_agreed", False)
            )
            if scoping_agreed != state.get("scoping_agreed", False):
                callbacks["update_state"]("scoping_agreed", scoping_agreed)
                st.rerun()
                
        st.divider()

        # Project Data Reset
        st.header("프로젝트 및 데이터")
        if st.button("🗑️ 모든 데이터 초기화", type="primary"):
            callbacks["reset_data"]()
            st.success("데이터가 초기화되었습니다!")
            time.sleep(1)
            st.rerun()

        st.divider()
        st.subheader("현재 설정")
        st.json(config)
