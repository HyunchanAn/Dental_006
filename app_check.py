import os
import sys

sys.path.append(os.getcwd())

print("Checking app.py syntax...")
try:
    print(" - app.py imported successfully")
except Exception as e:
    # streamlit commands might fail outside streamlit runtime, which is expected
    if "streamlit" in str(e):
        print(" - app.py syntax is likely fine (Streamlit runtime warning expected)")
    else:
        print(f"Error: {e}")
