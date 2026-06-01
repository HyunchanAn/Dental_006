# 모델/알고리즘 평가 자동화 가이드 (Evaluation Automation)

본 문서는 `Systematic Reviewer AI`의 데이터 추출(PICO) 모듈의 성능을 평가하고 벤치마킹하는 방법을 안내합니다.

## 1. 평가 방식 개요
거대 언어 모델(LLM, Gemma)을 활용하여 논문에서 PICO(Population, Intervention, Comparison, Outcome)를 추출하는 작업의 정확도를 측정하기 위해 다음과 같은 지표를 사용합니다.
- **ROUGE-1, ROUGE-L F-Measure**: 생성된 텍스트와 사람이 직접 추출한 정답(Ground Truth) 간의 형태소 및 문장 구조의 유사도를 측정합니다.
- **Token F1 Score**: 단어 단위의 Precision과 Recall을 결합하여 정보가 누락 없이 정확하게 추출되었는지 평가합니다.

## 2. 필요 의존성 설치
평가 스크립트는 `rouge-score` 라이브러리를 필요로 합니다.
```bash
uv pip install rouge-score
```

## 3. 정답 셋(Ground Truth) 준비
평가를 위해서는 테스트용 논문들에 대해 사람이 직접 작성한 정답 JSON 파일이 필요합니다.
```json
{
  "12345678": {
    "population": "Adult patients with diabetes",
    "intervention": "Insulin therapy",
    "outcome": "Blood glucose reduction"
  }
}
```

## 4. 평가 스크립트 실행
예측 결과(Predictions) JSON과 정답(Ground Truth) JSON을 준비한 뒤 다음 명령어를 실행합니다.
```bash
python scripts/evaluate_extraction.py --preds path/to/predictions.json --truth path/to/ground_truth.json
```

결과 출력 예시:
```text
--- Evaluation Results ---
Data points evaluated: 45
Average ROUGE-1 F-Measure: 0.8240
Average ROUGE-L F-Measure: 0.7950
Average Token F1 Score:    0.8120
```

## 5. 지속적인 벤치마크
모델 버전이 업데이트되거나 프롬프트 엔지니어링을 개선할 때마다 본 평가 파이프라인을 실행하여 모델의 성능 변화를 모니터링하시기 바랍니다.
