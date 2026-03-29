# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

import pytest

playwright_sync_api = pytest.importorskip(
    "playwright.sync_api",
    reason="Playwright not installed - run: pip install playwright && playwright install",
)

expect = playwright_sync_api.expect
sync_playwright = playwright_sync_api.sync_playwright


def test_readme_images():
    """Verify all images in README render correctly on GitHub."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Check the raw README for image links
        page.goto("https://github.com/ecomlounge/agentic-brain/blob/main/README.md")

        # Wait for images to load
        page.wait_for_load_state("networkidle")

        # Find all images
        images = page.locator("img").all()
        print(f"Found {len(images)} images")

        broken = []
        for i, img in enumerate(images):
            src = img.get_attribute("src") or ""
            alt = img.get_attribute("alt") or ""
            # Check if image loaded (has natural width > 0)
            natural_width = img.evaluate("el => el.naturalWidth")
            if natural_width == 0:
                broken.append(f"Image {i}: src={src}, alt={alt}")
                print(f"BROKEN: {src}")
            else:
                print(f"OK: {src} ({natural_width}px wide)")

        browser.close()

        if broken:
            pytest.fail(f"Broken images found: {broken}")


if __name__ == "__main__":
    test_readme_images()
