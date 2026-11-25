# [ 261125 1530 랩탑 개발팀 ] (Dental_006#59 핵심 리포트 모듈 복구 및 GROBID/Ollama 통신 정합화 실행 계획서)

## 1. 대상 이슈 및 위치

- 대상 이슈: [Dental_006#59](https://github.com/HyunchanAn/Dental_006/issues/59) (`[P0][복구] 삭제된 src/report/generator.py 복구, GROBID/Ollama 포트·환경변수 정합화 및 README 현행화`)
- 상위 Umbrella: [Dental_000#18](https://github.com/HyunchanAn/Dental_000/issues/18) (`Dental_000/plans_replies_walkthrough/261125_1530_Dental_Series_Remediation_Umbrella_Plan.md` Track 1)
- 실행 우선순위: 2순위 (독립 P0, 현재 실행 시 즉시 `ModuleNotFoundError` 발생)

---

## 2. 즉시 실행 가능 작업 (`[READY]`)

### 2.1 삭제된 `src/report/` 모듈 복구 (치명적 P0)
- 원인: 커밋 `f955370`에서 삭제되어 `Dental_000/reports_archive/generator.py` 및 `__init__.py`로 오이관됨. 현재 `main.py:11`, `src/ui/step5_report.py:7` 실행 시 즉시 `ModuleNotFoundError` 발생.
- 작업 내용:
  - `Dental_000/reports_archive/generator.py` 및 `__init__.py`를 확인하여 `Dental_006/src/report/` 경로로 원복.
  - `main.py` 및 `src/ui/step5_report.py` 임포트 정상 동작 검증.
  - 복구 검증 완료 후 `Dental_000#19` 절차에 따라 `Dental_000/reports_archive/` 잔존 파일 정리 연계.

### 2.2 GROBID 및 Ollama 통신 환경변수·포트 정합화
- `src/parse/grobid_client.py:7`: 하드코딩 `http://localhost:8090` 제거 -> `os.getenv("GROBID_URL", "http://localhost:8070")`로 통일 (`docker-compose.yml` 및 `.env.example`의 `8070` 기준).
- `docker-compose.yml` (`OLLAMA_BASE_URL`) vs `.env.example` (`OLLAMA_HOST`): 환경변수명 통일 및 `src/llm/client.py:13`, `src/ui/sidebar.py:61`의 `localhost`/`127.0.0.1` 하드코딩을 환경변수 기반으로 대체.

### 2.3 배치 스크립트 및 `README.md` 현행화
- `scripts/start_services.bat`, `scripts/start_services_test.bat`: 미존재 `cd tools\grobid` 경로를 실제 서비스 구조(Docker 또는 유효 경로)에 맞게 수정.
- `README.md` 현행화: 포트(`8502` vs Docker `8501`), Python 버전(배지 `3.12+` / 본문 `3.11` / CI `3.10`) 정합화, 디렉토리 트리(`pubtator.py`, `llm/`, `ui/`, `run.py`) 및 로컬 테스트(`tests/test_scope_and_pubtator.py`) 반영.

---

## 3. `[FREEZE]` 보류 항목

- 없음 (전체 항목 코드·설정·문서 수준에서 즉시 해결 가능. 단, 실제 GROBID/Ollama 외부 컨테이너 실기동 연동 테스트는 해당 서비스 기동 시점에 별도 확인).

---

## 4. 검증 기준

- `python -c "import src.report.generator; import src.ui.step5_report"` 임포트 에러 없음 확인.
- `pytest tests -v` (특히 `tests/test_scope_and_pubtator.py` 및 환경변수 폴백 단위 테스트) 전수 통과.
- 원격 GitHub Actions CI 통과 확인.
