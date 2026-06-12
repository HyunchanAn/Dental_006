import os

import aiohttp
import requests

# The default URL for the GROBID service started with docker-compose
GROBID_URL = "http://localhost:8090"
GROBID_API_URL = f"{GROBID_URL}/api/processFulltextDocument"


def process_pdf(pdf_path, timeout=60):
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return None

    print(f"Processing {os.path.basename(pdf_path)} with GROBID...")
    try:
        with open(pdf_path, "rb") as f:
            clean_filename = os.path.basename(pdf_path)
            files = {"input": (clean_filename, f, "application/pdf")}
            response = requests.post(GROBID_API_URL, files=files, timeout=timeout)

            if response.status_code == 200:
                print("  - Successfully processed by GROBID.")
                return response.text
            else:
                print(f"  - Error processing with GROBID. Status: {response.status_code}")
                return None
    except requests.exceptions.RequestException as e:
        print(f"  - GROBID service connection failed: {e}")
        return None


async def process_pdf_async(session, pdf_path, timeout=60):
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return None

    print(f"Processing {os.path.basename(pdf_path)} with GROBID asynchronously...")
    try:
        with open(pdf_path, "rb") as f:
            data = aiohttp.FormData()
            data.add_field("input", f.read(), filename=os.path.basename(pdf_path), content_type="application/pdf")

            async with session.post(GROBID_API_URL, data=data, timeout=timeout) as response:
                if response.status == 200:
                    print("  - Successfully processed by GROBID.")
                    return await response.text()
                else:
                    text = await response.text()
                    print(f"  - Error processing with GROBID. Status: {response.status}, Response: {text[:200]}")
                    return None
    except Exception as e:
        print(f"  - GROBID async service connection failed: {e}")
        return None
