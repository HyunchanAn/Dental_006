import json
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from src.llm import pico_extractor

cases = [
    "60세 이하 환자에서 임플란트가 틀니에 비해 좋은지에 대해 알아볼거야.",
    "임플란트가 틀니에 비해 좋은지에 대해 알아볼거야.",
]

for i, description in enumerate(cases):
    print(f"\n--- Case {i + 1} ---")
    print(f"Input: {description}")
    try:
        result = pico_extractor.extract_pico_from_description(description)
        import json

        with open(f"reproduce_case_{i + 1}.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error: {e}")
        # The pico_extractor inside src/llm/pico_extractor.py already prints raw response on error,
        # but let's capture it here if we can modify the extractor to return raw on failure or similar.
        # For now, rely on stdout capture.
