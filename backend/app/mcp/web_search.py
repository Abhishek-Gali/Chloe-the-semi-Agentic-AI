"""
Project Chloe - Stealth Deep Web Scraper & Search Tool
Queries DuckDuckGo and concurrently crawls target pages to extract full text context.
"""

import re
import urllib.parse
import aiohttp
import asyncio
import logging
from bs4 import BeautifulSoup
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

class WebSearchTool:
    @staticmethod
    async def fetch_via_jina_reader(url: str) -> str:
        """Fetches markdown of any URL via Jina Reader (r.jina.ai) for stealth content extraction."""
        jina_url = f"https://r.jina.ai/{url}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(jina_url, headers=HEADERS, timeout=6) as response:
                    if response.status == 200:
                        text = await response.text()
                        return text[:1200]
        except Exception:
            pass
        return ""

    @staticmethod
    async def fetch_page_summary(session: aiohttp.ClientSession, url: str) -> str:
        """Fetches and cleans text content from a web page (with Jina Reader fallback)."""
        try:
            async with session.get(url, headers=HEADERS, timeout=4) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "html.parser")
                    
                    for s in soup(["script", "style", "nav", "footer", "aside"]):
                        s.decompose()
                        
                    text = soup.get_text(separator=" ", strip=True)
                    text = re.sub(r'\s+', ' ', text)
                    if text and len(text) > 50:
                        return text[:800]
        except Exception:
            pass

        # Fallback to Jina Reader
        return await WebSearchTool.fetch_via_jina_reader(url)

    @classmethod
    async def search_and_scrape(cls, query: str, max_results: int = 3) -> Dict[str, Any]:
        """Performs DuckDuckGo stealth search and concurrently fetches article summaries."""
        try:
            encoded_query = urllib.parse.quote_plus(query)
            ddg_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            results = []
            async with aiohttp.ClientSession() as session:
                async with session.get(ddg_url, headers=HEADERS, timeout=6) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        soup = BeautifulSoup(html, "html.parser")
                        links = soup.find_all("a", class_="result__snippet")
                        title_links = soup.find_all("a", class_="result__url")

                        extracted_urls = []
                        for tag in title_links[:max_results]:
                            href = tag.get("href", "")
                            # Parse actual target URL from DDG redirect
                            if "uddg=" in href:
                                actual_url = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
                                extracted_urls.append(actual_url)
                            elif href.startswith("http"):
                                extracted_urls.append(href)

                        # Crawl top URLs concurrently
                        tasks = [cls.fetch_page_summary(session, u) for u in extracted_urls]
                        page_summaries = await asyncio.gather(*tasks)

                        for u, summary in zip(extracted_urls, page_summaries):
                            results.append({
                                "url": u,
                                "summary": summary if summary else "Snippet preview unavailable."
                            })

            if not results:
                # Direct simple fallback
                return {
                    "status": "success",
                    "query": query,
                    "results": [{"url": "https://duckduckgo.com/?q=" + encoded_query, "summary": f"Search results for: {query}"}]
                }

            return {
                "status": "success",
                "query": query,
                "count": len(results),
                "results": results
            }
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return {
                "status": "error",
                "message": f"Search failed: {str(e)}"
            }
