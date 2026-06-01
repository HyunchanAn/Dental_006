# Architecture Decision Records (ADR)

이 문서는 프로젝트 개발 중 이루어진 주요 아키텍처 결정 사항들을 기록합니다.

## ADR 001: LLM 모델로 Ollama 기반 Gemma 2 선택
- **Date**: 2026-01-10
- **Status**: Accepted
- **Context**: 상용 API(OpenAI 등)를 사용할 경우, 다량의 의료 문헌(수십만 자 이상)을 처리할 때 토큰 비용과 데이터 프라이버시 문제가 발생함.
- **Decision**: 로컬에서 구동 가능한 오픈소스 언어 모델을 활용하기로 함. 그 중 리소스 대비 추론 성능이 우수한 `gemma2:9b-instruct` 모델과 이를 관리하는 Ollama를 채택.
- **Consequences**: 인프라 비용 감소 및 프라이버시 유지 효과. 하지만 사용자의 로컬 환경에 최소 8GB 이상의 VRAM과 충분한 RAM이 요구됨.

## ADR 002: PDF 파서로 GROBID 선택
- **Date**: 2026-01-15
- **Status**: Accepted
- **Context**: 학술 논문 PDF는 다단 편집이 많아 단순 텍스트 추출 라이브러리(PyPDF2 등)로는 본문과 참고문헌, 표, 그림 캡션을 분리하기 어려움.
- **Decision**: 학술 논문 구조 분석에 특화된 머신러닝 기반 파서인 GROBID를 채택.
- **Consequences**: 텍스트 추출 품질 대폭 향상. 단, GROBID 구동을 위해 Docker 데스크톱 환경이 추가로 요구됨.
