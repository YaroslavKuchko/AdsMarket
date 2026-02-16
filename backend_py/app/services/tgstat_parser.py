"""
TGStat channel statistics parser.

Fetches public channel statistics from tgstat.ru for initial data.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# TGStat base URLs
TGSTAT_RU_URL = "https://tgstat.ru/channel/@{username}"
TGSTAT_STAT_URL = "https://tgstat.ru/channel/@{username}/stat"


@dataclass
class TGStatHistoryPoint:
    """Single point in subscriber history."""
    date: str  # YYYY-MM-DD
    subscribers: int


@dataclass
class TGStatData:
    """Parsed channel statistics from TGStat."""
    username: str
    title: str | None = None
    subscribers: int = 0
    avg_post_views: int = 0
    avg_reach: int = 0
    er_percent: float = 0.0  # Engagement Rate
    err_percent: float = 0.0  # ERR (views/subscribers * 100)
    citation_index: float = 0.0
    posts_per_day: float = 0.0
    recent_views: list[int] | None = None  # Views from recent posts
    growth_day: int = 0
    growth_week: int = 0
    growth_month: int = 0
    subscriber_history: list[TGStatHistoryPoint] | None = None  # Real 30-day history


def parse_number(text: str) -> int:
    """Parse number from text like '10 697 090' or '1.8m' or '820k'."""
    if not text:
        return 0
    
    text = text.strip().lower()
    
    # Handle K/M suffixes
    multiplier = 1
    if text.endswith('k'):
        multiplier = 1000
        text = text[:-1]
    elif text.endswith('m'):
        multiplier = 1000000
        text = text[:-1]
    
    # Remove spaces and non-breaking spaces
    text = re.sub(r'[\s\xa0]', '', text)
    
    # Replace comma with dot for decimals
    text = text.replace(',', '.')
    
    try:
        return int(float(text) * multiplier)
    except (ValueError, TypeError):
        return 0


def parse_float(text: str) -> float:
    """Parse float from text like '6.2%' or '4,7'."""
    if not text:
        return 0.0
    
    text = text.strip()
    # Remove % sign
    text = text.replace('%', '').strip()
    # Replace comma with dot
    text = text.replace(',', '.')
    # Remove spaces
    text = re.sub(r'[\s\xa0]', '', text)
    
    try:
        return float(text)
    except (ValueError, TypeError):
        return 0.0


async def fetch_tgstat_data(username: str) -> TGStatData | None:
    """
    Fetch channel statistics from TGStat.
    
    Args:
        username: Channel username without @ prefix
        
    Returns:
        TGStatData with parsed statistics or None if failed
    """
    # Clean username
    username = username.lstrip('@').strip()
    if not username:
        return None
    
    url = TGSTAT_RU_URL.format(username=username)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            
            if resp.status_code == 404:
                logger.warning(f"Channel @{username} not found on TGStat")
                return None
            
            if resp.status_code != 200:
                logger.warning(f"TGStat returned {resp.status_code} for @{username}")
                return None
            
            return parse_tgstat_html(username, resp.text)
            
    except httpx.TimeoutException:
        logger.error(f"Timeout fetching TGStat for @{username}")
        return None
    except Exception as e:
        logger.error(f"Error fetching TGStat for @{username}: {e}")
        return None


def parse_subscriber_history(html: str) -> list[TGStatHistoryPoint] | None:
    """
    Extract subscriber history from ApexCharts data embedded in HTML.
    
    TGStat embeds 30-day history in ApexCharts config like:
    series: [{ name: 'participants', data: [10828617, 10823745, ...] }],
    labels: ['2025-11-23', '2025-11-24', ...]
    """
    # Find ApexCharts config for participants
    chart_match = re.search(
        r"new\s+ApexCharts\([^,]+,\s*\{[^}]*series:\s*\[\s*\{[^}]*name:\s*['\"]participants['\"][^}]*data:\s*\[([^\]]+)\]\s*\}[^]]*\][^}]*labels:\s*\[([^\]]+)\]",
        html,
        re.DOTALL
    )
    
    if not chart_match:
        # Try alternative pattern
        chart_match = re.search(
            r"data:\s*\[(\d+(?:,\d+)*)\].*?labels:\s*\[(['\"][^'\"]+['\"](?:,['\"][^'\"]+['\"])*)\]",
            html,
            re.DOTALL
        )
    
    if not chart_match:
        return None
    
    try:
        # Parse data array
        data_str = chart_match.group(1)
        data_values = [int(x.strip()) for x in data_str.split(',') if x.strip().isdigit()]
        
        # Parse labels array
        labels_str = chart_match.group(2)
        labels = re.findall(r"['\"](\d{4}-\d{2}-\d{2})['\"]", labels_str)
        
        if len(data_values) != len(labels):
            logger.warning(f"Mismatched data/labels: {len(data_values)} vs {len(labels)}")
            # Use minimum length
            min_len = min(len(data_values), len(labels))
            data_values = data_values[:min_len]
            labels = labels[:min_len]
        
        if not data_values or not labels:
            return None
        
        history = [
            TGStatHistoryPoint(date=date, subscribers=subs)
            for date, subs in zip(labels, data_values)
        ]
        
        logger.info(f"Parsed {len(history)} days of subscriber history from TGStat")
        return history
        
    except Exception as e:
        logger.error(f"Error parsing subscriber history: {e}")
        return None


def parse_tgstat_html(username: str, html: str) -> TGStatData:
    """Parse TGStat HTML page and extract statistics."""
    soup = BeautifulSoup(html, "lxml")
    data = TGStatData(username=username)
    
    # 0. Parse subscriber history from ApexCharts
    data.subscriber_history = parse_subscriber_history(html)
    if data.subscriber_history:
        logger.info(f"Got {len(data.subscriber_history)} days of history for @{username}")
        # Calculate growth from history
        if len(data.subscriber_history) >= 2:
            first = data.subscriber_history[0].subscribers
            last = data.subscriber_history[-1].subscribers
            data.growth_month = last - first
            
            if len(data.subscriber_history) >= 7:
                week_ago = data.subscriber_history[-7].subscribers
                data.growth_week = last - week_ago
            
            if len(data.subscriber_history) >= 2:
                yesterday = data.subscriber_history[-2].subscribers
                data.growth_day = last - yesterday
    
    # 1. Parse title
    title_elem = soup.find("h1")
    if title_elem:
        data.title = title_elem.get_text(strip=True)
    
    # 2. Parse subscribers
    # Pattern: <h2>10 697 090</h2> followed by "подписчиков"
    subs_match = re.search(r'<h2[^>]*>([\d\s\xa0]+)</h2>\s*<div[^>]*>\s*подписчик', html, re.I)
    if subs_match:
        data.subscribers = parse_number(subs_match.group(1))
    
    # Also try to get from history if available
    if data.subscriber_history and not data.subscribers:
        data.subscribers = data.subscriber_history[-1].subscribers
    
    # 3. Parse recent post views
    # Pattern: Stats like ['1.8m', '63', '2.5k', '184.6k'] where first is views
    recent_views = []
    
    # Find all stat groups (views, comments, forwards, reactions)
    for container in soup.find_all("div", class_=True):
        texts = [t.strip() for t in container.stripped_strings]
        
        # Look for view patterns - usually 4 numbers in a row (views, replies, forwards, reactions)
        nums = []
        for t in texts:
            if re.match(r'^[\d.,]+[kmKM]?$', t):
                nums.append(t)
        
        # If we have exactly 4 numbers and first looks like views (high number)
        if len(nums) == 4:
            views = parse_number(nums[0])
            if views > 1000:  # Reasonable views count
                recent_views.append(views)
    
    if recent_views:
        data.recent_views = recent_views[:20]  # Keep last 20 posts
        # Calculate average views
        data.avg_post_views = sum(recent_views) // len(recent_views)
        data.avg_reach = data.avg_post_views
        
        # Calculate ERR (views/subscribers * 100)
        if data.subscribers > 0:
            data.err_percent = round((data.avg_post_views / data.subscribers) * 100, 2)
    
    # 4. Try to find specific stats (ERR, ER, growth) from stat blocks
    # These might be in different formats
    
    # Look for growth indicators (e.g., "+1 234" or "-567")
    growth_match = re.search(r'([+-]?\s*[\d\s]+)\s*за\s*(сутки|день|24)', html, re.I)
    if growth_match:
        data.growth_day = parse_number(growth_match.group(1))
    
    growth_week_match = re.search(r'([+-]?\s*[\d\s]+)\s*за\s*недел', html, re.I)
    if growth_week_match:
        data.growth_week = parse_number(growth_week_match.group(1))
    
    growth_month_match = re.search(r'([+-]?\s*[\d\s]+)\s*за\s*месяц', html, re.I)
    if growth_month_match:
        data.growth_month = parse_number(growth_month_match.group(1))
    
    # Look for ER/ERR percentages
    er_match = re.search(r'ERR?\s*[:=]?\s*([\d.,]+)\s*%', html, re.I)
    if er_match:
        data.er_percent = parse_float(er_match.group(1))
    
    # Citation index
    ci_match = re.search(r'индекс\s*цитирования\s*[:=]?\s*([\d.,]+)', html, re.I)
    if ci_match:
        data.citation_index = parse_float(ci_match.group(1))
    
    logger.info(f"Parsed TGStat for @{username}: {data.subscribers} subs, {data.avg_post_views} avg views")
    
    return data


async def fetch_channel_stats_from_tgstat(username: str) -> dict | None:
    """
    Fetch channel stats and return as dict for database storage.
    
    Returns dict compatible with ChannelStats model, including subscriber_history.
    """
    data = await fetch_tgstat_data(username)
    if not data:
        return None
    
    result = {
        "subscriber_count": data.subscribers,
        "avg_post_views": data.avg_post_views,
        "avg_reach_24h": data.avg_reach,
        "engagement_rate": data.err_percent,
        "subscriber_growth_24h": data.growth_day,
        "subscriber_growth_7d": data.growth_week,
        "subscriber_growth_30d": data.growth_month,
        "citation_index": data.citation_index,
        "source": "tgstat",
    }
    
    # Add subscriber history if available
    if data.subscriber_history:
        result["subscriber_history"] = [
            {"date": h.date, "subscribers": h.subscribers}
            for h in data.subscriber_history
        ]
    
    return result


# Quick test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        result = await fetch_tgstat_data("durov")
        if result:
            print(f"Title: {result.title}")
            print(f"Subscribers: {result.subscribers:,}")
            print(f"Avg Views: {result.avg_post_views:,}")
            print(f"ERR: {result.err_percent}%")
            print(f"Recent views: {result.recent_views[:5] if result.recent_views else 'N/A'}")
    
    asyncio.run(test())

