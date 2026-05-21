#!/usr/bin/env python3
"""
VelvetRopeDaily - Global Entertainment News Pipeline
Hollywood · Broadway · Nashville · West End · Celebrity · Awards
"""

import feedparser
import requests
import re
import os
from datetime import datetime, timezone
from anthropic import Anthropic
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

# ── CONFIG ────────────────────────────────────────────────────────────────────

SITE_TITLE = "VelvetRopeDaily"
SITE_TAGLINE = "Hollywood · Broadway · Nashville · West End · Celebrity · Awards"
OUTPUT_FILE = "index.html"
MAX_ARTICLES_PER_FEED = 6

FEEDS = {
    "Hollywood": [
        "https://variety.com/feed/",
        "https://www.hollywoodreporter.com/feed/",
        "https://deadline.com/feed/",
        "https://www.thewrap.com/feed/",
        "https://www.indiewire.com/feed/",
        "https://collider.com/feed/",
        "https://screenrant.com/feed/",
    ],
    "Broadway": [
        "https://playbill.com/feed",
        "https://www.broadwayworld.com/rss.cfm",
        "https://variety.com/t/theater/feed/",
        "https://deadline.com/category/broadway/feed/",
        "https://www.theatermania.com/rss/news.xml",
        "https://www.hollywoodreporter.com/t/theater/feed/",
    ],
    "Nashville & Country": [
        "https://www.billboard.com/c/country/feed/",
        "https://tasteofcountry.com/feed/",
        "https://nashcountryreview.com/feed/",
        "https://www.cmt.com/feeds/news/rss.jhtml",
        "https://www.rollingstone.com/music/music-country/feed/",
        "https://countrylineup.com/feed/",
        "https://www.nashvillelifestyles.com/feed/",
        "https://musicrow.com/feed/",
    ],
    "West End & London": [
        "https://www.thestage.co.uk/rss",
        "https://www.whatsonstage.com/rss",
        "https://www.timeout.com/london/theatre/rss",
        "https://www.theguardian.com/stage/rss",
        "https://www.standard.co.uk/culture/theatre/rss",
        "https://www.broadwayworld.com/london/rss.cfm",
    ],
    "Celebrity": [
        "https://people.com/feed/",
        "https://www.eonline.com/syndication/feeds/rssfeeds/topstories.xml",
        "https://www.tmz.com/rss.xml",
        "https://justjared.com/feed/",
        "https://pagesix.com/feed/",
        "https://www.usmagazine.com/feed/",
    ],
    "Movies": [
        "https://variety.com/v/film/feed/",
        "https://deadline.com/category/film/feed/",
        "https://collider.com/category/movie-news/feed/",
        "https://screenrant.com/category/movie-news/feed/",
        "https://www.empireonline.com/movies/news/rss/",
        "https://www.indiewire.com/category/film/feed/",
    ],
    "TV & Streaming": [
        "https://variety.com/v/tv/feed/",
        "https://deadline.com/category/tv/feed/",
        "https://collider.com/category/tv-news/feed/",
        "https://tvline.com/feed/",
        "https://www.hollywoodreporter.com/t/television/feed/",
        "https://screenrant.com/category/tv-news/feed/",
    ],
    "Music": [
        "https://variety.com/v/music/feed/",
        "https://www.billboard.com/feed/",
        "https://pitchfork.com/rss/news/",
        "https://www.rollingstone.com/music/feed/",
        "https://www.hollywoodreporter.com/t/music/feed/",
        "https://nme.com/feed",
    ],
    "Awards": [
        "https://deadline.com/category/awards/feed/",
        "https://variety.com/v/awards/feed/",
        "https://www.hollywoodreporter.com/t/awards/feed/",
        "https://www.indiewire.com/category/awards/feed/",
        "https://www.broadwayworld.com/rss.cfm?category=awards",
    ],
    "Box Office": [
        "https://deadline.com/category/box-office/feed/",
        "https://variety.com/v/film/box-office/feed/",
        "https://www.hollywoodreporter.com/t/box-office/feed/",
        "https://screenrant.com/category/box-office/feed/",
    ],
    "Reviews": [
        "https://www.rogerebert.com/feed",
        "https://www.indiewire.com/category/reviews/feed/",
        "https://collider.com/category/reviews/feed/",
        "https://www.avclub.com/rss",
        "https://www.theguardian.com/culture/reviews/rss",
    ],
}

AWARDS_CALENDAR = [
    {"award": "Tony Awards",           "date": "June 2026",      "venue": "Lincoln Center, NYC",         "category": "Broadway"},
    {"award": "CMA Awards",            "date": "November 2026",  "venue": "Bridgestone Arena, Nashville", "category": "Country"},
    {"award": "Emmy Awards",           "date": "September 2026", "venue": "Peacock Theater, LA",          "category": "Television"},
    {"award": "Academy Awards",        "date": "March 2027",     "venue": "Dolby Theatre, Hollywood",     "category": "Film"},
    {"award": "Golden Globes",         "date": "January 2027",   "venue": "Beverly Hilton",               "category": "Film/TV"},
    {"award": "Grammy Awards",         "date": "February 2027",  "venue": "Crypto.com Arena, LA",         "category": "Music"},
    {"award": "Olivier Awards",        "date": "April 2027",     "venue": "Royal Albert Hall, London",    "category": "West End"},
    {"award": "BAFTA Awards",          "date": "February 2027",  "venue": "Royal Festival Hall, London",  "category": "Film"},
    {"award": "SAG Awards",            "date": "February 2027",  "venue": "Shrine Auditorium, LA",        "category": "Film/TV"},
    {"award": "Cannes Film Festival",  "date": "May 2027",       "venue": "Palais des Festivals, Cannes", "category": "International"},
]

# ── HELPERS ───────────────────────────────────────────────────────────────────

client = Anthropic()

def clean_html(text):
    return re.sub(r'<[^>]+>', '', text or '').strip()

def extract_image(entry):
    """Extract the best image URL from an RSS entry."""
    # Try media:content
    media = entry.get("media_content", [])
    if media and isinstance(media, list):
        for m in media:
            url = m.get("url", "")
            if url and any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                return url

    # Try media:thumbnail
    thumb = entry.get("media_thumbnail", [])
    if thumb and isinstance(thumb, list) and thumb[0].get("url"):
        return thumb[0]["url"]

    # Try enclosures
    enclosures = entry.get("enclosures", [])
    for enc in enclosures:
        if enc.get("type", "").startswith("image/"):
            return enc.get("href", enc.get("url", ""))

    # Try to find img tag in summary/content
    content = entry.get("summary", "") or entry.get("content", [{}])[0].get("value", "") if entry.get("content") else ""
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
    if img_match:
        url = img_match.group(1)
        if url.startswith("http"):
            return url

    return ""

def fetch_feed(url):
    try:
        feed = feedparser.parse(url)
        return feed.entries[:MAX_ARTICLES_PER_FEED]
    except Exception as e:
        print(f"  ⚠ Feed error {url}: {e}")
        return []

def summarize(title, description):
    prompt = f"""You are an entertainment journalist for VelvetRopeDaily, a glamorous publication covering Hollywood, Broadway, Nashville, and London's West End. Write a 2-sentence summary that is vivid, engaging, and captures the drama or excitement. 

Title: {title}
Content: {description[:800]}

Return only the 2-sentence summary. No preamble."""
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.content[0].text.strip()
    except Exception as e:
        print(f"  ⚠ AI error: {e}")
        return clean_html(description)[:200] + "..."

def fetch_all_articles():
    all_data = {}
    for category, urls in FEEDS.items():
        print(f"\n🎭 Fetching: {category}")
        articles = []
        seen_titles = set()
        for url in urls:
            entries = fetch_feed(url)
            for entry in entries:
                title = clean_html(entry.get("title", ""))
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                link = entry.get("link", "#")
                description = clean_html(entry.get("summary", entry.get("description", "")))
                pub = entry.get("published", entry.get("updated", ""))
                image = extract_image(entry)
                print(f"  {'🖼' if image else '·'} {title[:55]}...")
                summary = summarize(title, description)
                articles.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "pub": pub,
                    "source": url.split("/")[2].replace("www.", "").replace("feeds.", ""),
                    "image": image,
                })
                if len(articles) >= 10:
                    break
            if len(articles) >= 10:
                break
        all_data[category] = articles
        print(f"  → {len(articles)} articles ({sum(1 for a in articles if a['image'])} with images)")
    return all_data

# ── HTML GENERATION ───────────────────────────────────────────────────────────

def make_card(art):
    img_html = ""
    if art.get("image"):
        img_html = f'<div class="card-img" style="background-image:url(\'{art["image"]}\')"></div>'
    return f"""
    <a class="article-card" href="{art['link']}" target="_blank" rel="noopener">
      {img_html}
      <div class="card-body">
        <div class="card-source">{art['source']}</div>
        <div class="card-title">{art['title']}</div>
        <div class="card-summary">{art['summary']}</div>
        <div class="card-footer">
          <span class="card-date">{art['pub'][:16] if art['pub'] else ''}</span>
          <span class="card-read">Read →</span>
        </div>
      </div>
    </a>"""

def build_html(articles_by_category):
    now = datetime.now(timezone.utc).strftime("%B %d, %Y · %H:%M UTC")

    category_sections = ""
    category_nav_items = ""
    all_categories = list(articles_by_category.keys())

    for i, category in enumerate(all_categories):
        articles = articles_by_category[category]
        cat_id = category.lower().replace(" ", "-").replace("&", "and")
        active = "active" if i == 0 else ""
        category_nav_items += f'<button class="cat-btn {active}" onclick="showCat(\'{cat_id}\')" id="catbtn-{cat_id}">{category}</button>\n'
        cards = "".join(make_card(art) for art in articles)
        display = "block" if i == 0 else "none"
        category_sections += f"""
        <div class="cat-section" id="cat-{cat_id}" style="display:{display}">
          <div class="cat-header"><h2>{category}</h2></div>
          <div class="articles-grid">{cards}</div>
        </div>"""

    awards_rows = ""
    for a in AWARDS_CALENDAR:
        cat_color = {
            "Broadway": "#c9a84c", "Country": "#8B4513", "Television": "#4169E1",
            "Film": "#c9a84c", "Film/TV": "#9B59B6", "Music": "#E91E63",
            "West End": "#2ECC71", "International": "#E74C3C"
        }.get(a["category"], "#888")
        awards_rows += f"""
        <tr>
          <td class='award-name'>{a['award']}</td>
          <td style='color:#ccc;'>{a['date']}</td>
          <td style='color:#aaa;font-size:12px;'>{a['venue']}</td>
          <td><span class='cat-pill' style='border-color:{cat_color};color:{cat_color};'>{a['category']}</span></td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>VelvetRopeDaily</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400;1,700&family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,400&family=Montserrat:wght@300;400;500;600;700&display=swap"/>
<style>
  :root {{
    --black: #080808;
    --dark: #101010;
    --dark2: #161616;
    --panel: #131313;
    --border: #252525;
    --gold: #c9a84c;
    --gold2: #e8c96a;
    --gold3: #f5e6b0;
    --silver: #b8b8c8;
    --cream: #f0ebe0;
    --text: #ddd8cc;
    --muted: #7a7670;
    --display: 'Playfair Display', Georgia, serif;
    --body: 'Georgia', Georgia, serif;
    --sans: 'Montserrat', Helvetica, sans-serif;
  }}
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    background: var(--black);
    color: var(--text);
    font-family: var(--body);
    font-size: 16px;
    line-height: 1.6;
    background-image: radial-gradient(ellipse at 30% 0%, rgba(201,168,76,0.04) 0%, transparent 50%);
  }}

  /* TOP BAR */
  .top-bar {{
    background: var(--dark);
    border-bottom: 1px solid #1a1a1a;
    padding: 5px 24px;
    display: flex;
    justify-content: space-between;
    font-family: var(--sans);
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
  }}
  .top-bar-l {{ color: var(--gold); }}
  .top-bar-r {{ color: var(--muted); }}

  /* GOLD MARQUEE */
  .marquee-wrap {{ background: var(--gold); overflow: hidden; padding: 5px 0; }}
  .marquee-inner {{
    display: flex; gap: 50px;
    animation: marquee 45s linear infinite;
    width: max-content;
  }}
  .mi {{
    font-family: var(--sans); font-size: 10px; font-weight: 700;
    color: var(--black); white-space: nowrap;
    text-transform: uppercase; letter-spacing: 2px;
  }}
  .md {{ color: rgba(0,0,0,0.35); margin: 0 6px; }}
  @keyframes marquee {{ 0% {{ transform:translateX(0); }} 100% {{ transform:translateX(-50%); }} }}

  /* MASTHEAD */
  .masthead {{
    background: var(--dark);
    text-align: center;
    padding: 44px 20px 32px;
    border-bottom: 3px solid var(--gold);
    position: relative; overflow: hidden;
  }}
  .masthead::before {{
    content: '';
    position: absolute; top: 0; left: 0; right: 0; bottom: 0;
    background: radial-gradient(ellipse at 50% 0%, rgba(201,168,76,0.1) 0%, transparent 65%);
    pointer-events: none;
  }}
  .masthead-eyebrow {{
    font-family: var(--sans); font-size: 9px;
    letter-spacing: 6px; text-transform: uppercase; color: var(--gold);
    margin-bottom: 14px;
  }}
  .masthead-name {{
    font-family: var(--display);
    font-size: clamp(40px, 7vw, 100px);
    font-weight: 900; letter-spacing: -2px; line-height: 0.9;
    color: var(--cream);
    text-shadow: 0 2px 40px rgba(201,168,76,0.25);
  }}
  .masthead-name span {{ color: var(--gold); font-style: italic; }}
  .masthead-rule {{
    display: flex; align-items: center; gap: 16px;
    margin: 18px auto; max-width: 600px;
  }}
  .masthead-rule::before, .masthead-rule::after {{
    content: ''; flex: 1; height: 1px;
    background: linear-gradient(90deg, transparent, var(--gold), transparent);
  }}
  .masthead-star {{ color: var(--gold); font-size: 14px; letter-spacing: 8px; }}
  .masthead-tagline {{
    font-family: var(--body); font-style: italic;
    font-size: 16px; color: var(--silver); letter-spacing: 2px;
  }}
  .masthead-date {{
    font-family: var(--sans); font-size: 10px;
    color: var(--muted); margin-top: 12px; letter-spacing: 1px;
  }}

  /* NAV */
  .main-nav {{
    background: #0d0d0d; border-bottom: 1px solid var(--border);
    display: flex; overflow-x: auto; padding: 0 20px;
  }}
  .nav-tab {{
    font-family: var(--sans); font-size: 10px; font-weight: 600;
    color: var(--muted); padding: 13px 20px; cursor: pointer;
    border: none; background: none; text-transform: uppercase;
    letter-spacing: 1.5px; border-bottom: 2px solid transparent;
    white-space: nowrap; transition: color 0.15s, border-color 0.15s;
  }}
  .nav-tab:hover {{ color: var(--gold); }}
  .nav-tab.active {{ color: var(--gold); border-bottom-color: var(--gold); }}

  /* LAYOUT */
  .site-wrap {{ max-width: 1440px; margin: 0 auto; }}
  .page {{ display: none; }}
  .page.active {{ display: block; }}

  /* NEWS LAYOUT */
  .news-layout {{
    display: grid; grid-template-columns: 1fr 290px; gap: 0; min-height: 80vh;
  }}
  .news-main {{ border-right: 1px solid var(--border); }}
  .news-sidebar {{ background: var(--panel); }}

  /* CAT FILTER */
  .cat-filter {{
    background: var(--dark2); border-bottom: 1px solid var(--border);
    padding: 10px 20px; display: flex; gap: 6px; overflow-x: auto;
  }}
  .cat-btn {{
    font-family: var(--sans); font-size: 9px; font-weight: 600;
    color: var(--muted); background: transparent;
    border: 1px solid var(--border); padding: 5px 13px;
    cursor: pointer; white-space: nowrap; text-transform: uppercase;
    letter-spacing: 1px; transition: all 0.15s;
  }}
  .cat-btn:hover, .cat-btn.active {{
    background: var(--gold); color: var(--black); border-color: var(--gold);
  }}

  /* ARTICLE GRID — magazine style with images */
  .articles-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1px; background: var(--border);
  }}
  .article-card {{
    background: var(--dark); text-decoration: none; color: var(--text);
    display: flex; flex-direction: column;
    transition: background 0.15s; border-left: 3px solid transparent;
  }}
  .article-card:hover {{ background: #1a1a1a; border-left-color: var(--gold); }}

  /* Image area */
  .card-img {{
    width: 100%; height: 180px;
    background-size: cover; background-position: center top;
    background-color: #1a1a1a;
    position: relative;
    flex-shrink: 0;
  }}
  .card-img::after {{
    content: '';
    position: absolute; bottom: 0; left: 0; right: 0; height: 60px;
    background: linear-gradient(transparent, var(--dark));
  }}

  /* Card body */
  .card-body {{ padding: 16px 20px 18px; display: flex; flex-direction: column; gap: 8px; flex: 1; }}
  .card-source {{
    font-family: var(--sans); font-size: 9px; color: var(--gold);
    text-transform: uppercase; letter-spacing: 1.5px;
  }}
  .card-title {{
    font-family: var(--display); font-size: 16px; font-weight: 700;
    line-height: 1.3; color: var(--cream);
  }}
  .article-card:hover .card-title {{ color: var(--gold2); }}
  .card-summary {{
    font-family: var(--body); font-size: 14px; color: #9a9690;
    line-height: 1.6; flex: 1;
  }}
  .card-footer {{
    display: flex; justify-content: space-between; align-items: center;
    border-top: 1px solid var(--border); padding-top: 10px; margin-top: 4px;
  }}
  .card-date {{ font-family: var(--sans); font-size: 9px; color: var(--muted); }}
  .card-read {{ font-family: var(--sans); font-size: 9px; color: var(--gold); text-transform: uppercase; letter-spacing: 1px; }}

  .cat-header {{ padding: 20px 24px 8px; border-bottom: 1px solid var(--border); }}
  .cat-header h2 {{
    font-family: var(--display); font-size: 26px; font-weight: 700;
    font-style: italic; color: var(--cream);
  }}

  /* SIDEBAR */
  .sidebar-section {{ border-bottom: 1px solid var(--border); padding: 20px; }}
  .sidebar-title {{
    font-family: var(--sans); font-size: 9px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 2px; color: var(--gold);
    margin-bottom: 14px; padding-bottom: 8px; border-bottom: 1px solid var(--border);
  }}
  .trending-item {{
    display: flex; gap: 12px; padding: 8px 0;
    border-bottom: 1px solid #1a1a1a; align-items: flex-start;
  }}
  .trending-num {{
    font-family: var(--display); font-size: 22px; font-weight: 900;
    color: #2a2a2a; line-height: 1; min-width: 26px;
  }}
  .trending-title {{ font-family: var(--body); font-size: 13px; color: var(--silver); line-height: 1.4; }}

  /* AWARDS PAGE */
  .data-page {{ padding: 36px 28px; }}
  .data-page h1 {{
    font-family: var(--display); font-size: 38px; font-style: italic;
    font-weight: 700; color: var(--cream); margin-bottom: 6px;
  }}
  .data-page .subtitle {{
    font-family: var(--sans); font-size: 10px; color: var(--muted);
    margin-bottom: 28px; text-transform: uppercase; letter-spacing: 2px;
  }}
  .data-table {{
    width: 100%; border-collapse: collapse; font-size: 13px;
    background: var(--dark); border: 1px solid var(--border);
  }}
  .data-table th {{
    background: #0d0d0d; color: var(--gold);
    font-family: var(--sans); font-size: 9px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 1.5px;
    padding: 12px 16px; text-align: left; border-bottom: 1px solid var(--gold);
  }}
  .data-table td {{ padding: 13px 16px; border-bottom: 1px solid var(--border); vertical-align: middle; }}
  .data-table tr:hover td {{ background: #1a1a1a; }}
  .award-name {{
    font-family: var(--display); font-style: italic; font-size: 16px; color: var(--cream);
  }}
  .cat-pill {{
    border: 1px solid; padding: 3px 10px;
    font-family: var(--sans); font-size: 9px; letter-spacing: 1px; text-transform: uppercase;
  }}

  /* ABOUT */
  .about-wrap {{ max-width: 720px; margin: 48px auto; padding: 0 28px 80px; }}
  .about-wrap h1 {{
    font-family: var(--display); font-size: 42px; font-style: italic;
    color: var(--cream); margin-bottom: 10px;
  }}
  .about-wrap p {{ font-family: var(--body); font-size: 16px; line-height: 1.8; color: #aaa; margin-bottom: 16px; }}

  /* FOOTER */
  .site-footer {{
    background: var(--dark); border-top: 2px solid #1a1a1a;
    text-align: center; padding: 32px 20px;
    font-family: var(--sans); font-size: 10px; color: var(--muted);
    letter-spacing: 1px; line-height: 2.2;
  }}
  .footer-logo {{ font-family: var(--display); font-size: 26px; font-style: italic; color: var(--gold); margin-bottom: 6px; }}

  @media (max-width: 768px) {{
    .news-layout {{ grid-template-columns: 1fr; }}
    .news-sidebar {{ display: none; }}
    .articles-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>

<div class="top-bar">
  <span class="top-bar-l">✦ VelvetRopeDaily.com ✦</span>
  <span class="top-bar-r">Updated: {now}</span>
</div>

<div class="marquee-wrap">
  <div class="marquee-inner">
    <span class="mi">Hollywood<span class="md">✦</span></span>
    <span class="mi">Broadway<span class="md">✦</span></span>
    <span class="mi">Nashville<span class="md">✦</span></span>
    <span class="mi">West End<span class="md">✦</span></span>
    <span class="mi">Celebrity<span class="md">✦</span></span>
    <span class="mi">Awards<span class="md">✦</span></span>
    <span class="mi">Box Office<span class="md">✦</span></span>
    <span class="mi">Reviews<span class="md">✦</span></span>
    <span class="mi">Music<span class="md">✦</span></span>
    <span class="mi">Streaming<span class="md">✦</span></span>
    <span class="mi">Hollywood<span class="md">✦</span></span>
    <span class="mi">Broadway<span class="md">✦</span></span>
    <span class="mi">Nashville<span class="md">✦</span></span>
    <span class="mi">West End<span class="md">✦</span></span>
    <span class="mi">Celebrity<span class="md">✦</span></span>
    <span class="mi">Awards<span class="md">✦</span></span>
    <span class="mi">Box Office<span class="md">✦</span></span>
    <span class="mi">Reviews<span class="md">✦</span></span>
    <span class="mi">Music<span class="md">✦</span></span>
    <span class="mi">Streaming<span class="md">✦</span></span>
  </div>
</div>

<div class="masthead">
  <div class="masthead-eyebrow">Est. 2026 · The Global Entertainment Daily</div>
  <div class="masthead-name"><span>Velvet</span>RopeDaily</div>
  <div class="masthead-rule"><span class="masthead-star">✦ ✦ ✦</span></div>
  <div class="masthead-tagline">{SITE_TAGLINE}</div>
  <div class="masthead-date">{now}</div>
</div>

<nav style="background:#0d0d0d;border-bottom:1px solid #1e1e1e;">
  <div class="site-wrap">
    <div class="main-nav">
      <button class="nav-tab active" onclick="showPage('news',this)">News</button>
      <button class="nav-tab" onclick="showPage('awards',this)">Awards Calendar</button>
      <button class="nav-tab" onclick="showPage('about',this)">About</button>
    </div>
  </div>
</nav>

<div class="site-wrap">

  <div class="page active" id="page-news">
    <div class="cat-filter">{category_nav_items}</div>
    <div class="news-layout">
      <div class="news-main">{category_sections}</div>
      <aside class="news-sidebar">
        <div class="sidebar-section">
          <div class="sidebar-title">✦ On The Red Carpet</div>
          <div class="trending-item"><span class="trending-num">1</span><span class="trending-title">Hollywood film & TV coverage</span></div>
          <div class="trending-item"><span class="trending-num">2</span><span class="trending-title">Broadway & West End theater</span></div>
          <div class="trending-item"><span class="trending-num">3</span><span class="trending-title">Nashville country & Americana</span></div>
          <div class="trending-item"><span class="trending-num">4</span><span class="trending-title">Celebrity news & features</span></div>
          <div class="trending-item"><span class="trending-num">5</span><span class="trending-title">Awards season coverage</span></div>
          <div class="trending-item"><span class="trending-num">6</span><span class="trending-title">Box office & streaming</span></div>
        </div>
        <div class="sidebar-section">
          <div class="sidebar-title">✦ Awards Watch</div>
          {''.join(f"<div style='padding:7px 0;border-bottom:1px solid #1a1a1a;'><div style='font-family:var(--display);font-style:italic;font-size:13px;color:var(--cream);'>{a['award']}</div><div style='font-family:var(--sans);font-size:9px;color:var(--gold);letter-spacing:1px;margin-top:2px;'>{a['date']} · {a['category']}</div></div>" for a in AWARDS_CALENDAR[:6])}
        </div>
        <div class="sidebar-section">
          <div class="sidebar-title">✦ Coverage</div>
          <p style="font-family:var(--body);font-size:13px;color:var(--muted);line-height:1.7;">VelvetRopeDaily covers the full spectrum of global entertainment — from Hollywood blockbusters and Broadway openings to Nashville chart-toppers and London's West End. Updated daily.</p>
        </div>
      </aside>
    </div>
  </div>

  <div class="page" id="page-awards">
    <div class="data-page">
      <h1>Awards Calendar</h1>
      <div class="subtitle">Global Entertainment Awards · 2026–2027 Season</div>
      <table class="data-table">
        <thead><tr><th>Award</th><th>Date</th><th>Venue</th><th>Category</th></tr></thead>
        <tbody>{awards_rows}</tbody>
      </table>
    </div>
  </div>

  <div class="page" id="page-about">
    <div class="about-wrap">
      <h1>About VelvetRopeDaily</h1>
      <p>VelvetRopeDaily is the premier global entertainment news destination — covering Hollywood films and television, Broadway and West End theater, Nashville's music scene, celebrity culture, awards seasons, box office, and streaming.</p>
      <p>Every morning our AI-powered pipeline pulls from the world's top entertainment publications — Variety, Deadline, The Hollywood Reporter, Playbill, Broadway World, Billboard, The Stage, NME and more — delivering concise, beautifully written summaries so you never miss a story.</p>
      <p style="font-size:13px;color:var(--muted);">Content sourced from third-party RSS feeds. All articles link to their original source. VelvetRopeDaily does not claim ownership of any syndicated content.</p>
    </div>
  </div>

</div>

<footer class="site-footer">
  <div class="footer-logo">VelvetRopeDaily</div>
  <div>© {datetime.now().year} VelvetRopeDaily · Powered by Claude AI · Updated Daily</div>
  <div style="font-size:9px;color:#333;margin-top:4px;">Content sourced from third-party RSS feeds · All articles link to original sources</div>
</footer>

<script>
function showPage(name, btn) {{
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  if (btn) btn.classList.add('active');
  window.scrollTo(0,0);
}}
function showCat(catId) {{
  document.querySelectorAll('.cat-section').forEach(s => s.style.display = 'none');
  document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
  var el = document.getElementById('cat-' + catId);
  if (el) el.style.display = 'block';
  var btn = document.getElementById('catbtn-' + catId);
  if (btn) btn.classList.add('active');
}}
</script>
</body>
</html>"""
    return html

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  VelvetRopeDaily Pipeline")
    print("=" * 60)
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    articles = fetch_all_articles()
    total = sum(len(v) for v in articles.values())
    images = sum(1 for cat in articles.values() for a in cat if a.get("image"))
    print(f"\n✅ Total articles: {total} ({images} with images)")
    print("🎬 Building HTML...")
    html = build_html(articles)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Site saved to: {OUTPUT_FILE}")
    print("=" * 60)

if __name__ == "__main__":
    main()
