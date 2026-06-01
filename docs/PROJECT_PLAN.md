# Project Plan

## 목표 (Goal)
체계적 문헌고찰(Systematic Review) 과정을 자동화하여 문헌 검색, 스크리닝, 데이터 추출, 분석 리포트 생성을 지원하는 통합 플랫폼 개발.

## 주요 마일스톤 (Milestones)

### Phase 1: MVP 완성 (완료)
- PubMed 기반 문헌 수집
- Gemma 2 모델 연동 및 프롬프트 최적화
- GROBID 기반 PDF 텍스트 파싱
- Streamlit 기반 인터페이스 제공

### Phase 2: 인프라 고도화 및 품질 향상 (현재 진행 중)
- 테스트 코드 (Integration test, Property-based test) 확충 및 Coverage 85% 이상 달성
- Type hints 및 Docstring 90% 이상 커버
- CI/CD 자동화 파이프라인 구성 및 패키징 (GitHub Releases 연동)
- 로깅 프레임워크 (loguru) 도입

### Phase 3: 분석 및 검증 능력 고도화 (예정)
- Cochrane RoB 2.0 평가 로직 세밀화
- 다중 데이터베이스 병합 (Embase, Cochrane 등) 및 퍼지 매칭 기반 중복 제거
- 사용자 데이터 피드백 루프 구축
