# 다중 DB 지원 및 중복 제거 구현 체크리스트

## 1. 데이터베이스 마이그레이션 (`src/utils/db_manager.py`)
- `[x]` `articles` 테이블의 PK를 `id` (UUID)로 변경하는 단일 트랜잭션 마이그레이션 로직 구현 (기존 데이터 보존)
- `[x]` 기존 `pmid` 컬럼 Nullable 처리 및 `source_db` (출처) 컬럼 추가
- `[x]` `pipeline_meta` 등 중복 제거 통계 보존을 위한 구조 신설

## 2. 외부 데이터 파싱 및 정제 (`src/ingest/external_parser.py`)
- `[x]` RIS, CSV 파일 리더 구현 (`rispy` 또는 `pandas`)
- `[x]` 필드 매핑 (`title`, `abstract`, `doi`, `journal`, `pub_year`, `first_author`) 및 `source_db` 기입
- `[x]` PMID가 없는 경우 고유 `id` 부여 로직 구현

## 3. 중복 제거 엔진 (`src/ingest/deduplicator.py`)
- `[x]` 마스터 레코드 유지 정책 (완전 드롭 방식, PubMed > Embase > Cochrane 우선)
- `[x]` 1단계 매칭: DOI
- `[x]` 2단계 매칭: Title 정규화 매칭
- `[x]` 3단계 매칭: Title 1차 + `pub_year` + `first_author` (Last name 정규화 추출) 교차 검증 로직 구현

## 4. UI 연동 및 리포팅 반영 (`src/ui/step1_search.py`, `src/report/generator.py`)
- `[x]` 1단계 화면에 외부 DB 결과 업로드용 `st.expander` 및 `st.file_uploader` 추가
- `[x]` 파일 업로드 시 파싱 -> 중복 제거 -> DB 적재 워크플로우 연동
- `[x]` PRISMA 리포트 생성 시 중복 제거된 외부 DB 문헌 수 통계 자동 반영

## 5. 테스트 및 검증 (`Dental_000/tests/tests_006/`)
- `[x]` DB 마이그레이션 안정성 테스트 (`test_db_manager.py`)
- `[x]` 저자명/타이틀 정규화 기반 3단계 중복 제거 엣지 케이스 테스트 (`test_deduplicator.py`)

---

# [ 261025 1455 랩탑 개발팀 ] 다중 DB 지원 및 3단계 중복 제거 엔진 구현·검증 완결 (`[CLOSED]` / `[PASS]`)

- 상태: 공식 종결 (`[CLOSED]` / `[PASS]` 완결)
- 이행 결과: `src/utils/db_manager.py`, `src/ingest/external_parser.py`, `src/ingest/deduplicator.py`, `src/ui/step1_search.py` 및 중앙 단위 테스트(`Dental_000/tests/tests_006/test_deduplicator.py`, `test_external_parser.py`)에 본 체크리스트의 전 항목이 100% 구현·통과되었으므로 `[CLOSED]` / `[PASS]` 완결로 공식 종결한다.
