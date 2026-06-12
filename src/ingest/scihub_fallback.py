import os
from typing import Optional, cast

from playwright.async_api import BrowserContext, async_playwright
from playwright_stealth import Stealth


class SciHubDownloader:
    def __init__(self, user_data_dir: Optional[str] = None):
        self.mirrors = ["https://sci-hub.se", "https://sci-hub.st", "https://sci-hub.ru"]
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        self.user_data_dir = user_data_dir

    async def _create_context(self, p) -> BrowserContext:
        """
        Creates a playwright context.
        Attempts to use persistent context if user_data_dir is provided.
        Falls back to standard ephemeral context if locked or path invalid.
        """
        if self.user_data_dir and os.path.exists(os.path.dirname(self.user_data_dir)):
            try:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=self.user_data_dir,
                    headless=True,
                    user_agent=self.user_agent,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                print(f"  - Successfully launched persistent context at {self.user_data_dir}")
                return cast(BrowserContext, context)
            except Exception as e:
                print(
                    f"  - Failed to launch persistent context (locked by another Chrome instance?). Fallback to ephemeral: {e}"
                )

        # Fallback to standard context
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(user_agent=self.user_agent)
        return cast(BrowserContext, context)

    async def download_by_doi(self, doi: str, save_path: str) -> bool:
        """
        Attempts to download a PDF from Sci-Hub mirrors for the given DOI.
        Uses stealth plugin to bypass anti-bot challenges.
        """
        if not doi:
            return False

        print(f"  - Attempting Stealth Sci-Hub Direct Fallback for DOI: {doi}")
        try:
            async with async_playwright() as p:
                context = await self._create_context(p)
                page = await context.new_page()
                await Stealth().apply_stealth_async(page)

                success = False
                for mirror in self.mirrors:
                    target_url = f"{mirror}/{doi}"
                    try:
                        response = await page.goto(target_url, timeout=30000)
                        if not response or response.status != 200:
                            continue

                        # Search for PDF source inside iframe/embed
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
                                    print(f"  - SUCCESS: Downloaded PDF from Sci-Hub mirror {mirror}")
                                    success = True
                                    break

                        # Fallback: click download button
                        download_btn = await page.query_selector("button:has-text('download'), a:has-text('download')")
                        if download_btn:
                            async with page.expect_download(timeout=15000) as download_info:
                                await download_btn.click()
                            download = await download_info.value
                            await download.save_as(save_path)
                            print(f"  - SUCCESS: Downloaded PDF from Sci-Hub mirror {mirror} (clicked download)")
                            success = True
                            break

                    except Exception as mirror_e:
                        print(f"  - Mirror {mirror} failed: {mirror_e}")
                        continue

                await context.close()
                # If the context is persistent, browser object is tied to context, otherwise we close the browser.
                # Playwright async_context manager will handle cleanups but explicit close is safe.
                if hasattr(context, "browser") and context.browser:
                    await context.browser.close()

                return success
        except Exception as e:
            print(f"  - Sci-Hub Downloader encountered an error: {e}")
            return False
