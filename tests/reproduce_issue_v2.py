import json
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from src.llm import pico_extractor

description = "65세 이상 환자에서 임플란트가 틀니보다 환자 만족도가 높은지"

print(f"Input: {description}")
try:
    result = pico_extractor.extract_pico_from_description(description)
    import json

    with open("reproduce_age_fix.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
except Exception as e:
    print(f"Error: {e}")
