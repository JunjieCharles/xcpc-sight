"""Optional HTTP browser regression; see doc/static-site-data.md for execution."""

import argparse

from playwright.sync_api import sync_playwright


def check_page(page, base_url, query, selector):
    page.goto(f"{base_url}?series=2026-2027{query}")
    shell = page.locator(selector)
    shell.wait_for(state="visible")
    page.wait_for_function(
        "selector => document.querySelector(selector)?.querySelector('tbody tr[aria-rowindex]')",
        arg=selector,
    )
    shell.scroll_into_view_if_needed()
    # Keep the pointer over the table, including cells with hover tooltips.
    box = shell.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + 150)
    page.wait_for_timeout(200)
    page_y = page.evaluate("window.scrollY")
    previous = 0
    for _ in range(8):
        page.mouse.wheel(0, 350)
        page.wait_for_timeout(150)
        current = shell.evaluate("el => el.scrollTop")
        assert current > previous, (selector, previous, current)
        previous = current
        assert abs(page.evaluate("window.scrollY") - page_y) < 2
    page.mouse.wheel(300, 0)
    page.wait_for_timeout(150)
    horizontal = shell.evaluate("el => el.scrollLeft")
    if shell.evaluate("el => el.scrollWidth > el.clientWidth"):
        assert horizontal > 0
    page.mouse.wheel(0, 350)
    page.wait_for_timeout(150)
    assert shell.evaluate("el => el.scrollLeft") == horizontal
    assert shell.evaluate("el => el.scrollTop") > previous
    page.mouse.wheel(0, -700)
    page.wait_for_timeout(150)
    assert 0 < shell.evaluate("el => el.scrollTop") < previous
    # Scrolling to the bottom must render the actual last row, with bounded DOM size.
    shell.evaluate("el => el.scrollTop = el.scrollHeight")
    page.wait_for_timeout(250)
    result = shell.evaluate("""el => ({
      last: Number(el.querySelector('tbody tr[aria-rowindex]:last-of-type')
        ?.getAttribute('aria-rowindex')),
      total: Number(el.querySelector('table').getAttribute('aria-rowcount')),
      rows: el.querySelectorAll('tbody tr[aria-rowindex]').length,
      remaining: el.scrollHeight - el.clientHeight - el.scrollTop
    })""")
    assert result["last"] == result["total"], result
    assert result["rows"] < 60, result
    assert abs(result["remaining"]) < 44, result
    # A viewport resize should retain the current section of the list.
    shell.evaluate("el => el.scrollTop = 2000")
    page.wait_for_timeout(150)
    viewport = page.viewport_size
    page.set_viewport_size({**viewport, "height": viewport["height"] - 100})
    page.wait_for_timeout(150)
    assert abs(shell.evaluate("el => el.scrollTop") - 2000) < 2
    page.set_viewport_size(viewport)
    if "contest=" not in query:
        page.locator("#search-input").fill("__no_matching_team__")
        page.wait_for_function(
            "selector => document.querySelector(selector).scrollTop === 0",
            arg=selector,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-url", default="http://127.0.0.1:8000/")
    parser.add_argument("--browser", choices=["webkit", "chromium"], default="webkit")
    args = parser.parse_args()
    with sync_playwright() as playwright:
        options = {"channel": "chrome"} if args.browser == "chromium" else {}
        browser = getattr(playwright, args.browser).launch(**options)
        try:
            for width in [1440, 390]:
                page = browser.new_page(viewport={"width": width, "height": 900})
                errors = []
                page.on("pageerror", lambda error, target=errors: target.append(error))
                for query, selector in [
                    ("", "#series-scroll"),
                    ("&contest=icpc2026preliminary-1", "#detail-view .table-shell"),
                    ("&view=preview&previewContest=icpc-2026-nanjing", "#preview-scroll"),
                    ("&view=preview&previewContest=icpc-2026-shenyang", "#preview-scroll"),
                    ("&view=review", "#review-scroll"),
                ]:
                    check_page(page, args.site_url, query, selector)
                    print(args.browser, width, selector, query, "OK", flush=True)
                assert not errors, errors
                page.close()
        finally:
            browser.close()


if __name__ == "__main__":
    main()
