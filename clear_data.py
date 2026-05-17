import os
import sys

# Add the project root to the Python path to allow importing src.utils
# This assumes clear_data.py is at the project root
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.utils import data_manager

if __name__ == "__main__":
    print("--- 모든 생성된 데이터를 초기화합니다 ---")
    data_manager.clear_generated_data_files()
    print("--- 데이터 초기화 완료 ---")
