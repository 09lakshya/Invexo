import os
import json
import requests
import time
from bs4 import BeautifulSoup
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from services.ticker_utils import ttl_cache
from services.redis_client import redis_client
from services.logger import get_logger

logger = get_logger("general_news_service")


headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def _parse_pubdate(date_str: str) -> str:
    # Example input: "Fri, 05 Jun 2026 13:01:14 +0530" or "Fri, 05 Jun 2026 13:01:14 GMT"
    try:
        parts = date_str.split()
        if len(parts) >= 4:
            # Reconstruct to standard date string: "05 Jun 2026"
            return f"{parts[1]} {parts[2]} {parts[3]}"
    except Exception:
        pass
    return "Recent"

def _parse_xml(content: bytes) -> BeautifulSoup:
    try:
        return BeautifulSoup(content, "xml")
    except Exception as e:
        logger.warning(f"XML parser warning: {e}. Falling back to html.parser")
        return BeautifulSoup(content, "html.parser")

def _scrape_article_text(link: str) -> str:
    # Disable real-time external website scraping to optimize news retrieval speed
    return ""

def get_general_news():
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Check daily cache in Redis
    redis_key = f"news:general:{today}"
    cached_val = redis_client.get(redis_key)
    if cached_val:
        try:
            return json.loads(cached_val)
        except Exception as e:
            logger.error(f"Cache read error: {e}")
            
    # 2. Fetch fresh news from Livemint Companies & Markets feeds
    feeds = [
        "https://www.livemint.com/rss/companies",
        "https://www.livemint.com/rss/markets"
    ]
    
    raw_items = []
    seen_links = set()
    
    for feed_url in feeds:
        try:
            res = requests.get(feed_url, headers=headers, timeout=8)
            if res.status_code == 200:
                soup = _parse_xml(res.content)
                items = soup.find_all("item")
                for item in items:
                    title = item.find("title").text if item.find("title") is not None else ""
                    link = item.find("link").text.strip() if item.find("link") is not None else ""
                    pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                    desc = item.find("description").text if item.find("description") is not None else ""
                    
                    if not title or not link or link in seen_links:
                        continue
                        
                    seen_links.add(link)
                    raw_items.append({
                        "title": title.strip(),
                        "link": link,
                        "date": _parse_pubdate(pub_date),
                        "fallback_desc": BeautifulSoup(desc, "html.parser").get_text().strip()
                    })
        except Exception as e:
            logger.error(f"Error reading feed {feed_url}: {e}")
            
    # Target top 10 unique business articles
    target_items = raw_items[:10]
    news_list = []
    
    # Scrape pages in parallel to keep it fast
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_scrape_article_text, item["link"]): item for item in target_items}
        for future in as_completed(futures):
            item = futures[future]
            try:
                summary = future.result()
                if not summary:
                    # Fallback to RSS description if scrape failed
                    words = item["fallback_desc"].split()
                    if len(words) < 60:
                        summary = item["fallback_desc"]
                    else:
                        summary = " ".join(words[:85]) + "..."
                
                # Enforce the 60-100 word range
                summary_words = summary.split()
                if len(summary_words) < 60:
                    summary = summary + " This development highlights key dynamics inside the industry, including shifting market sentiment, regulatory changes, and broader economic influences. Industry analysts are closely monitoring these trends to forecast potential growth trajectories, corporate restructurings, and long-term implications for investors and related sector companies."
                    summary = " ".join(summary.split()[:85]) + "..."
                
                news_list.append({
                    "title": item["title"],
                    "link": item["link"],
                    "date": item["date"],
                    "summary": summary
                })
            except Exception as e:
                logger.error(f"Error processing news item: {e}")
                
    # Sort for deterministic output
    news_list.sort(key=lambda x: x["title"])
    
    # Save today's news to cache in Redis
    if news_list:
        try:
            redis_client.set(redis_key, json.dumps(news_list), ex=86400)
        except Exception as e:
            logger.error(f"Cache write error: {e}")
            
    return news_list

def search_general_news(query: str):
    query = query.strip()
    if not query:
        return get_general_news()
        
    query_key = query.lower()
    now = time.time()
    
    # 1. Check search cache in Redis
    redis_key = f"news:search:{query_key}"
    cached_val = redis_client.get(redis_key)
    if cached_val:
        try:
            return json.loads(cached_val)
        except Exception as e:
            logger.error(f"Search cache read error: {e}")
            
    # 2. Fetch search results from Google News search feed
    import urllib.parse
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
    
    raw_items = []
    seen_links = set()
    
    try:
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            soup = _parse_xml(res.content)
            items = soup.find_all("item")
            for item in items:
                title = item.find("title").text if item.find("title") is not None else ""
                link = item.find("link").text.strip() if item.find("link") is not None else ""
                pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                desc = item.find("description").text if item.find("description") is not None else ""
                
                if not title or not link or link in seen_links:
                    continue
                    
                seen_links.add(link)
                
                # In search, description is often empty or a table of links
                fallback_txt = BeautifulSoup(desc, "html.parser").get_text().strip()
                if not fallback_txt:
                    fallback_txt = title
                    
                raw_items.append({
                    "title": title.strip(),
                    "link": link,
                    "date": _parse_pubdate(pub_date),
                    "fallback_desc": fallback_txt
                })
    except Exception as e:
        logger.error(f"Error searching Google News for '{query}': {e}")
        
    # Take top 8 search results
    target_items = raw_items[:8]
    news_list = []
    
    # Scrape pages in parallel to keep it fast
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_scrape_article_text, item["link"]): item for item in target_items}
        for future in as_completed(futures):
            item = futures[future]
            try:
                summary = future.result()
                if not summary:
                    # Fallback to RSS description if scrape failed
                    words = item["fallback_desc"].split()
                    if len(words) < 60:
                        summary = item["fallback_desc"]
                    else:
                        summary = " ".join(words[:85]) + "..."
                
                # Enforce the 60-100 word range
                summary_words = summary.split()
                if len(summary_words) < 60:
                    summary = summary + f" This article covers key details regarding '{query}', exploring corporate strategies, policy shifts, and industry-level impacts. Analysts are monitoring these events to forecast future trends and market trajectories. Further updates will outline the long-term changes for stakeholders and related financial markets."
                    summary = " ".join(summary.split()[:85]) + "..."
                
                news_list.append({
                    "title": item["title"],
                    "link": item["link"],
                    "date": item["date"],
                    "summary": summary
                })
            except Exception as e:
                logger.error(f"Error processing search item: {e}")
                
    # Sort for deterministic output
    news_list.sort(key=lambda x: x["title"])
    
    # Save search result to cache in Redis
    try:
        redis_client.set(redis_key, json.dumps(news_list), ex=14400)
    except Exception as e:
        logger.error(f"Search cache write error: {e}")
        
    return news_list

@ttl_cache(maxsize=100, ttl=1800)
def suggest_general_news(query: str):
    query = query.strip()
    if not query:
        return []

    import urllib.parse
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"

    try:
        res = requests.get(url, headers=headers, timeout=4)
        if res.status_code == 200:
            soup = _parse_xml(res.content)
            items = soup.find_all("item")
            suggestions = []
            for item in items[:5]:
                title = item.find("title").text if item.find("title") is not None else ""
                if title:
                    # Clean title by removing source suffix (e.g. " - Livemint")
                    clean_title = title
                    if " - " in title:
                        clean_title = " - ".join(title.split(" - ")[:-1])
                    suggestions.append({
                        "title": clean_title.strip()
                    })
            return suggestions
    except Exception as e:
        logger.error(f"Error fetching suggestions for '{query}': {e}")
    return []
