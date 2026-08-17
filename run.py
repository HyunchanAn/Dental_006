import os
import sys
from streamlit.web import cli as stcli

if __name__ == "__main__":
    addr = "0.0.0.0" if os.getenv("ALLOW_EXTERNAL_ACCESS", "false").lower() == "true" else "127.0.0.1"
    sys.argv = ["streamlit", "run", "app.py", f"--server.address={addr}"]
    sys.exit(stcli.main())
