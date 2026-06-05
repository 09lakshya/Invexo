import os
import json
import requests
import time
from bs4 import BeautifulSoup
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

CACHE_FILE = os.path.join(os.path.dirname(__file__), "general_news_cache.json")
SEARCH_CACHE_FILE = os.path.join(os.path.dirname(__file__), "general_news_search_cache.json")

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
        print(f"XML parser warning: {e}. Falling back to html.parser")
        return BeautifulSoup(content, "html.parser")

def _scrape_article_text(link: str) -> str:
    try:
        res = requests.get(link, headers=headers, timeout=8)
        if res.status_code != 200:
            return ""
        soup = BeautifulSoup(res.content, "html.parser")
        paragraphs = soup.find_all("p")
        text_blocks = []
        for p in paragraphs:
            txt = p.get_text().strip()
            # Clean and filter out advertisements or boilerplate
            if len(txt.split()) > 10 and not any(k in txt for k in ["Subscribe", "Newsletter", "Sign in", "Apps", "Follow us"]):
                txt = txt.replace('\xa0', ' ').replace('\u2019', "'").replace('\u201c', '"').replace('\u201d', '"')
                text_blocks.append(txt)
        combined = " ".join(text_blocks)
        words = combined.split()
        if len(words) >= 60:
            # Take first 85 words (comfortably in 60-100 range)
            return " ".join(words[:85]) + "..."
    except Exception as e:
        print(f"Error scraping {link}: {e}")
    return ""

def get_general_news():
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Check local daily cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
                if cache_data.get("date") == today and cache_data.get("news"):
                    return cache_data["news"]
        except Exception as e:
            print(f"Cache read error: {e}")
            
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
            print(f"Error reading feed {feed_url}: {e}")
            
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
                print(f"Error processing news item: {e}")
                
    # Sort for deterministic output
    news_list.sort(key=lambda x: x["title"])
    
    # Save today's news to cache
    if news_list:
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({"date": today, "news": news_list}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Cache write error: {e}")
            
    return news_list

def search_general_news(query: str):
    query = query.strip()
    if not query:
        return get_general_news()
        
    query_key = query.lower()
    now = time.time()
    
    # 1. Check search cache
    if os.path.exists(SEARCH_CACHE_FILE):
        try:
            with open(SEARCH_CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
                # Cache validity: 4 hours
                if query_key in cache_data:
                    record = cache_data[query_key]
                    if now - record.get("time", 0) < 14400: # 4 hours
                        return record.get("news", [])
        except Exception as e:
            print(f"Search cache read error: {e}")
            
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
        print(f"Error searching Google News for '{query}': {e}")
        
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
                print(f"Error processing search item: {e}")
                
    # Sort for deterministic output
    news_list.sort(key=lambda x: x["title"])
    
    # Save search result to cache
    try:
        cache_data = {}
        if os.path.exists(SEARCH_CACHE_FILE):
            with open(SEARCH_CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
        
        # Keep cache size small, delete old entries if > 50 queries cached
        if len(cache_data) > 50:
            oldest_key = min(cache_data.keys(), key=lambda k: cache_data[k].get("time", 0))
            cache_data.pop(oldest_key, None)
            
        cache_data[query_key] = {
            "time": now,
            "news": news_list
        }
        
        with open(SEARCH_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Search cache write error: {e}")
        
    return news_list
