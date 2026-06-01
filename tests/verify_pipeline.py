import os
import sys

import requests
import yaml


def check_python():
    print(f"[1/5] Checking Python version: {sys.version.split()[0]}")
    return True


def check_directories():
    dirs = ["data", "data/raw", "data/tables", "data/pdf", "data/tei", "src", "models"]
    missing = [d for d in dirs if not os.path.exists(d)]
    if missing:
        print(f"[2/5] Missing directories: {', '.join(missing)}")
        return False
    print("[2/5] Directory structure: OK")
    return True


def check_ollama():
    print("[3/5] Checking Ollama service...")
    try:
        response = requests.get("http://127.0.0.1:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = [m["name"] for m in response.json().get("models", [])]
            if "gemma4:latest" in models or "gemma4:9b" in models or "gemma4" in models:
                print(" - Ollama is running with gemma4: OK")
                return True
            else:
                print(f" - Ollama is running, but gemma4 not found. Models: {models}")
                return False
        else:
            print(f" - Ollama returned status code: {response.status_code}")
            return False
    except Exception as e:
        print(f" - Ollama connection failed: {e}")
        return False


def check_grobid():
    print("[4/5] Checking GROBID service...")
    try:
        response = requests.get("http://127.0.0.1:8070/api/isalive", timeout=5)
        if response.status_code == 200 and response.text.strip().lower() == "true":
            print(" - GROBID is running: OK")
            return True
        else:
            print(f" - GROBID returned unexpected response: {response.text}")
            return False
    except Exception as e:
        print(f" - GROBID connection failed (Docker might be down): {e}")
        return False


def check_config():
    print("[5/5] Checking picos_config.yaml...")
    if not os.path.exists("picos_config.yaml"):
        print(" - picos_config.yaml not found.")
        return False
    try:
        with open("picos_config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            if "picos" in config:
                print(" - picos_config.yaml: OK")
                return True
    except Exception as e:
        print(f" - Error reading config: {e}")
        return False


if __name__ == "__main__":
    print("=== Systematic Reviewer AI Environment Verification ===\n")
    results = [check_python(), check_directories(), check_ollama(), check_grobid(), check_config()]

    print("\n" + "=" * 50)
    if all(results):
        print("Verification SUCCESS: All systems ready.")
    else:
        print("Verification PARTIAL: Some services are offline (Expected if Docker is not running).")
    print("=" * 50)
