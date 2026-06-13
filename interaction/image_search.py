"""interaction/image_search.py — Image search for reference shape anchors.

When the user does NOT upload a reference image, this module searches for
candidate images via a configured provider and returns them for the user to
pick one (or skip). The chosen image becomes the session's shape anchor.

Images confirm shape/topology only; they NEVER gate dimensions or influence
the geometrically_valid / manufacturable verdict.

ARCHITECTURE:
  - Abstract ImageSearchProvider base class
  - Provider discovered from config/image_search.yaml
  - Headless-browser (Playwright) implementation as primary provider
  - Graceful degradation: if no provider configured, log and proceed
"""

from __future__ import annotations
import abc
import os
import logging
import tempfile
import time

logger = logging.getLogger("pipeline")


class ImageSearchProvider(abc.ABC):
    """Abstract base for image search backends."""

    @abc.abstractmethod
    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Search for candidate reference images.

        Returns:
            list of dicts: [{"url": str, "thumbnail_url": str, "title": str, "source": str}, ...]
            Empty list if nothing found or on error.

        Must NOT raise — degrade gracefully on failure.
        """
        ...


class PlaywrightImageSearchProvider(ImageSearchProvider):
    """Searches for images using a Playwright headless browser on DuckDuckGo Images.

    No API key required. Requires `playwright` Python package.
    Degrades gracefully if Playwright is unavailable or search fails.
    """

    def __init__(self, timeout_s: int = 15):
        self._timeout_s = timeout_s

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("[IMAGE_SEARCH] Playwright not installed; skipping image search.")
            return []

        results: list[dict] = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 800},
                )
                page = context.new_page()

                # DuckDuckGo image search
                search_url = f"https://duckduckgo.com/?q={query}&iax=images&ia=images"
                page.goto(search_url, timeout=self._timeout_s * 1000, wait_until="domcontentloaded")

                # Wait for image tiles to appear
                try:
                    page.wait_for_selector("img.tile--img__img", timeout=8000)
                except Exception:
                    # Some DDG layouts use different selectors
                    try:
                        page.wait_for_selector('img[src*="image"]', timeout=5000)
                    except Exception:
                        pass

                # Wait a bit for lazy-loaded images
                time.sleep(1.5)

                # Extract image tiles
                tiles = page.query_selector_all("img.tile--img__img")
                if not tiles:
                    # Try alternative selectors for different DDG layouts
                    tiles = page.query_selector_all('a[data-testid="result-tile"] img')
                if not tiles:
                    tiles = page.query_selector_all('.tile--img__media img')

                for tile in tiles[:max_results]:
                    src = tile.get_attribute("src") or tile.get_attribute("data-src") or ""
                    alt = tile.get_attribute("alt") or ""
                    if src and (src.startswith("http") or src.startswith("/")):
                        if src.startswith("/"):
                            src = "https://duckduckgo.com" + src
                        results.append({
                            "url": src,
                            "thumbnail_url": src,
                            "title": alt or query,
                            "source": "duckduckgo",
                        })

                browser.close()
        except Exception as e:
            logger.warning(f"[IMAGE_SEARCH] Playwright search failed: {e}")
            return []

        # Deduplicate by URL
        seen = set()
        unique = []
        for r in results:
            url = r.get("url", "")
            if url and url not in seen:
                seen.add(url)
                unique.append(r)
        return unique[:max_results]


def _load_image_search_config() -> dict:
    """Load image_search.yaml from config/, returning defaults if unavailable."""
    try:
        from core.config_loader import load_config
        return load_config("image_search")
    except Exception:
        return {}


def get_image_search_provider() -> ImageSearchProvider | None:
    """Instantiate the configured image search provider, or None if unavailable.

    Config (config/image_search.yaml):
        provider: "playwright"    # or null / "" to disable
        timeout_s: 15

    Falls back to Playwright provider if config is missing, but returns None
    if Playwright is not installed or the config explicitly disables search.
    """
    config = _load_image_search_config()
    provider_name = config.get("provider", "").lower().strip()

    if not provider_name or provider_name == "none" or provider_name == "null":
        logger.info("[IMAGE_SEARCH] No provider configured; image search disabled.")
        return None

    timeout_s = int(config.get("timeout_s", 15))

    if provider_name == "playwright":
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError:
            logger.warning("[IMAGE_SEARCH] Playwright provider configured but not installed.")
            return None
        return PlaywrightImageSearchProvider(timeout_s=timeout_s)

    logger.warning(f"[IMAGE_SEARCH] Unknown provider '{provider_name}'; disabling image search.")
    return None


def search_reference_images(query: str, max_results: int = 5) -> list[dict] | None:
    """Main entry point: search for candidate reference images.

    Args:
        query: The design prompt or object name to search for.
        max_results: Maximum number of candidates to return.

    Returns:
        List of {url, thumbnail_url, title, source} dicts, or None if unavailable.
    """
    provider = get_image_search_provider()
    if provider is None:
        return None

    logger.info(f"[IMAGE_SEARCH] Searching for: {query[:120]}")
    results = provider.search(query, max_results=max_results)

    if not results:
        logger.info("[IMAGE_SEARCH] No candidate images found.")
        return None

    logger.info(f"[IMAGE_SEARCH] Found {len(results)} candidate(s).")
    return results


def download_image(url: str, dest_path: str, timeout_s: int = 15) -> bool:
    """Download an image from a URL to a local path.

    Returns True on success, False on failure.
    """
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = resp.read()
            if len(data) < 512:  # Too small to be a real image
                return False
            os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(data)
        return True
    except Exception as e:
        logger.warning(f"[IMAGE_SEARCH] Failed to download {url}: {e}")
        return False