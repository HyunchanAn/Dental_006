from playwright.async_api import async_playwright


class SciHubDownloader:
    def __init__(self):
        self.mirrors = ["https://sci-hub.se", "https://sci-hub.st", "https://sci-hub.ru"]
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

    async def download_by_doi(self, doi: str, save_path: str) -> bool:
        """
        Attempts to download a PDF from Sci-Hub mirrors for the given DOI.
        """
        if not doi:
            return False

        print(f"  - Attempting Sci-Hub Direct Fallback for DOI: {doi}")
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=self.user_agent)
                page = await context.new_page()

                for mirror in self.mirrors:
                    target_url = f"{mirror}/{doi}"
                    try:
                        response = await page.goto(target_url, timeout=30000)
                        if not response or response.status != 200:
                            continue

                        # iframe 또는 embed 태그 내부의 실제 PDF 바이너리 소스 탐색
                        pdf_element = await page.query_selector("iframe#pdf, embed#pdf, iframe")
                        if pdf_element:
                            src = await pdf_element.get_attribute("src")
                            if src:
                                if src.startswith("//"):
                                    pdf_url = "https:" + src
                                elif src.startswith("/"):
                                    pdf_url = mirror + src
                                else:
                                    pdf_url = src

                                pdf_response = await context.request.get(pdf_url)
                                if pdf_response.status == 200:
                                    with open(save_path, "wb") as f:
                                        f.write(await pdf_response.body())
                                    await browser.close()
                                    print(f"  - SUCCESS: Downloaded PDF from Sci-Hub mirror {mirror}")
                                    return True

                        # Fallback 조치: download 텍스트를 포함한 버튼 직접 클릭 유도
                        download_btn = await page.query_selector("button:has-text('download'), a:has-text('download')")
                        if download_btn:
                            async with page.expect_download() as download_info:
                                await download_btn.click()
                            download = await download_info.value
                            await download.save_as(save_path)
                            await browser.close()
                            print(f"  - SUCCESS: Downloaded PDF from Sci-Hub mirror {mirror} (clicked download)")
                            return True

                    except Exception:
                        # Continue to next mirror on error
                        continue

                await browser.close()
                return False
        except Exception as e:
            print(f"  - Sci-Hub Downloader encountered an error: {e}")
            return False
