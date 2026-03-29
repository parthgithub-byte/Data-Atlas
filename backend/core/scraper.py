"""Layer 3: Investigation Engine â€” live page scraper with metadata and forensic extraction."""

import asyncio
import random
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader

from .forensics import extract_image_metadata, extract_pdf_metadata
from .http_client import build_live_url, build_request_headers, create_async_client


def clean_html(html_content):
    """Strip scripts, CSS, and extract human-readable text."""
    soup = BeautifulSoup(html_content, "lxml")

    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = " ".join(chunk for chunk in chunks if chunk)

    return text[:5000]


def extract_meta_info(html_content):
    """Extract meta description, title, and og tags from HTML."""
    soup = BeautifulSoup(html_content, "lxml")
    info = {}

    title_tag = soup.find("title")
    if title_tag:
        info["title"] = title_tag.get_text(strip=True)

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc:
        info["description"] = meta_desc.get("content", "")

    for og_tag in ["og:title", "og:description", "og:image", "og:url"]:
        tag = soup.find("meta", attrs={"property": og_tag})
        if tag:
            info[og_tag.replace("og:", "og_")] = tag.get("content", "")

    for prop in ["profile:username", "profile:first_name", "profile:last_name"]:
        tag = soup.find("meta", attrs={"property": prop})
        if tag:
            info[prop.replace(":", "_")] = tag.get("content", "")

    return info


def extract_links(html_content, base_url):
    """Extract first-party links worth inspecting."""
    soup = BeautifulSoup(html_content, "lxml")
    links = []
    for tag in soup.find_all(["a", "img", "source"]):
        href = tag.get("href") or tag.get("src")
        if not href:
            continue
        absolute_url = urljoin(base_url, href)
        if absolute_url.startswith("http") and absolute_url not in links:
            links.append(absolute_url)
        if len(links) >= 20:
            break
    return links


async def _extract_pdf_text(response):
    """Extract a lightweight text summary from a PDF response."""
    reader = PdfReader(response.content)
    text_parts = []
    for page in reader.pages[:3]:
        try:
            text_parts.append(page.extract_text() or "")
        except Exception:
            continue
    return " ".join(text_parts).strip()[:5000]


async def _collect_forensics(client, page_url, meta, links, timeout):
    """Fetch and extract metadata from related high-value resources."""
    artifacts = []

    pdf_targets = [page_url] if page_url.lower().endswith(".pdf") else []
    pdf_targets.extend([link for link in links if link.lower().endswith(".pdf")])

    image_targets = []
    og_image = meta.get("og_image")
    if og_image:
        image_targets.append(og_image)
    image_targets.extend([
        link for link in links if link.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".tiff"))
    ])

    for pdf_url in pdf_targets[:1]:
        try:
            metadata = await extract_pdf_metadata(client, pdf_url, timeout=timeout)
            if metadata:
                artifacts.append(metadata)
        except Exception:
            continue

    for image_url in image_targets[:1]:
        try:
            metadata = await extract_image_metadata(client, image_url, timeout=timeout)
            if metadata:
                artifacts.append(metadata)
        except Exception:
            continue

    return artifacts


async def scrape_url(client, url, timeout=10):
    """Scrape a single URL and return cleaned text plus metadata."""
    try:
        await asyncio.sleep(random.uniform(0.1, 0.5))
        response = await client.get(
            build_live_url(url),
            headers=build_request_headers(),
            follow_redirects=True,
            timeout=timeout,
        )

        if response.status_code != 200:
            return None

        content_type = response.headers.get("content-type", "")
        retrieved_at = datetime.now(timezone.utc).isoformat()
        last_modified = response.headers.get("last-modified")

        if "application/pdf" in content_type or str(response.url).lower().endswith(".pdf"):
            pdf_meta = await extract_pdf_metadata(client, str(response.url), timeout=timeout)
            return {
                "url": str(response.url),
                "final_url": str(response.url),
                "text": "",
                "meta": {"title": pdf_meta.get("metadata", {}).get("title", "PDF document")} if pdf_meta else {},
                "links": [],
                "forensics": [pdf_meta] if pdf_meta else [],
                "status_code": response.status_code,
                "retrieved_at": retrieved_at,
                "last_modified": last_modified,
            }

        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return None

        html = response.text
        meta = extract_meta_info(html)
        links = extract_links(html, str(response.url))
        forensics = await _collect_forensics(client, str(response.url), meta, links, timeout)

        return {
            "url": url,
            "final_url": str(response.url),
            "text": clean_html(html),
            "meta": meta,
            "links": links,
            "forensics": forensics,
            "status_code": response.status_code,
            "retrieved_at": retrieved_at,
            "last_modified": last_modified,
        }

    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError, Exception):
        return None


async def scrape_urls(urls, max_concurrent=10, timeout=10):
    """Scrape multiple URLs concurrently with rate limiting."""
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)

    async with create_async_client(verify=False) as client:
        async def limited_scrape(url):
            async with semaphore:
                return await scrape_url(client, url, timeout)

        tasks = [limited_scrape(url) for url in urls]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for result in completed:
            if result and not isinstance(result, Exception):
                results.append(result)

    return results
