#!/usr/bin/env python3
"""
zfuye.org 自动发布机器人
真实来源抓取 → DeepSeek提炼翻译 → WordPress发布
"""

import os, json, random, datetime, requests, re, time
import xml.etree.ElementTree as ET
from html import unescape
from base64 import b64encode

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY", "")
WP_USER      = os.environ.get("WP_USER", "")
WP_APP_PASS  = os.environ.get("WP_APP_PASS", "")
WP_BASE      = "https://www.zfuye.org/wp-json/wp/v2"

TODAY  = datetime.date.today().isoformat()
HOUR_U = datetime.datetime.utcnow().hour  # 0=早, 6=午, 12=晚

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
LOG_PATH = "data/log.json"

# ── 数据源配置 ────────────────────────────────────────────────────────────────
SOURCES = [
    # AI副业
    {"name": "Hacker News",       "cat": "AI副业",  "type": "hn",
     "keywords": ["ai","gpt","claude","llm","openai","anthropic","revenue","saas","product","launch","maker","tool"]},
    {"name": "ProductHunt",       "cat": "AI副业",  "type": "rss",
     "url": "https://www.producthunt.com/feed"},
    {"name": "IndieHackers",      "cat": "AI副业",  "type": "rss",
     "url": "https://www.indiehackers.com/feed.xml"},

    # 海外接单
    {"name": "Entrepreneur",      "cat": "海外接单", "type": "rss",
     "url": "https://www.entrepreneur.com/latest.rss"},
    {"name": "Freelancer Blog",   "cat": "海外接单", "type": "rss",
     "url": "https://www.freelancer.com/community/feed"},

    # 信息差·副业
    {"name": "Medium·副业",       "cat": "信息差",   "type": "rss",
     "url": "https://medium.com/feed/tag/side-hustle"},
    {"name": "Medium·创业",       "cat": "信息差",   "type": "rss",
     "url": "https://medium.com/feed/tag/entrepreneurship"},
    {"name": "DEV.to",            "cat": "信息差",   "type": "devto"},

    # 被动收入
    {"name": "Medium·被动收入",   "cat": "被动收入", "type": "rss",
     "url": "https://medium.com/feed/tag/passive-income"},
    {"name": "Smart Passive Income","cat": "被动收入","type": "rss",
     "url": "https://www.smartpassiveincome.com/feed/"},

    # 跨境电商
    {"name": "TechCrunch",        "cat": "跨境电商", "type": "rss",
     "url": "https://techcrunch.com/feed/"},
    {"name": "VentureBeat",       "cat": "跨境电商", "type": "rss",
     "url": "https://venturebeat.com/feed/"},
]

# 所有分类，随机轮转保证均匀覆盖
ALL_CATS = ["AI副业", "海外接单", "信息差", "被动收入", "跨境电商"]


# ── 抓取函数 ──────────────────────────────────────────────────────────────────
def fetch_rss(source, limit=8):
    try:
        r = requests.get(source["url"], headers=HEADERS, timeout=12)
        root = ET.fromstring(r.content)
        items = root.findall(".//item")
        results = []
        for item in items[:limit]:
            title = item.find("title")
            link  = item.find("link")
            desc  = item.find("description")
            if title is None or link is None: continue
            t = unescape((title.text or "").strip())
            l = (link.text or "").strip()
            d = unescape(re.sub(r'<[^>]+>', '', (desc.text or "") if desc is not None else "")[:500]).strip()
            if t and l:
                results.append({"title": t, "url": l, "summary": d, "source": source["name"]})
        return results
    except Exception as e:
        print(f"  [{source['name']}] 失败: {e}")
        return []


def fetch_hn(source, limit=6):
    keywords = source.get("keywords", ["ai","saas","startup","revenue"])
    try:
        ids = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10
        ).json()[:80]
        results = []
        for i in ids:
            try:
                item = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{i}.json", timeout=8
                ).json()
                title = item.get("title", "")
                score = item.get("score", 0)
                url   = item.get("url") or f"https://news.ycombinator.com/item?id={i}"
                if score > 60 and any(k in title.lower() for k in keywords):
                    results.append({"title": title, "url": url,
                                    "summary": f"HN评分: {score}",
                                    "source": "Hacker News"})
                    if len(results) >= limit: break
                time.sleep(0.05)
            except: continue
        return results
    except Exception as e:
        print(f"  [HN] 失败: {e}")
        return []


def fetch_devto(source, limit=6):
    keywords = ["ai","side","saas","earn","income","startup","product","tool","freelance"]
    try:
        r = requests.get("https://dev.to/api/articles?top=1&per_page=30", timeout=12)
        results = []
        for a in r.json():
            title = a.get("title","")
            if any(k in title.lower() for k in keywords):
                results.append({
                    "title":   title,
                    "url":     a.get("url",""),
                    "summary": (a.get("description") or "")[:400],
                    "source":  "DEV.to",
                })
                if len(results) >= limit: break
        return results
    except Exception as e:
        print(f"  [DEV.to] 失败: {e}")
        return []


def fetch_source(source):
    t = source["type"]
    if t == "rss":    return fetch_rss(source)
    if t == "hn":     return fetch_hn(source)
    if t == "devto":  return fetch_devto(source)
    return []


# ── 选文章 ────────────────────────────────────────────────────────────────────
def load_log():
    try:
        with open(LOG_PATH) as f: return json.load(f)
    except: return {"used_urls": [], "published": []}


def save_log(log):
    os.makedirs("data", exist_ok=True)
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def pick_article(log):
    used_urls = set(log.get("used_urls", []))

    # 统计今天各分类已发数量，优先发数量少的
    today_counts = {}
    for p in log.get("published", []):
        if isinstance(p, dict) and p.get("date") == TODAY:
            today_counts[p.get("cat", "")] = today_counts.get(p.get("cat",""), 0) + 1

    # 按今日发布数从少到多排序分类
    sorted_cats = sorted(ALL_CATS, key=lambda c: today_counts.get(c, 0))

    for cat in sorted_cats:
        sources = [s for s in SOURCES if s["cat"] == cat]
        random.shuffle(sources)
        for source in sources:
            articles = fetch_source(source)
            fresh = [a for a in articles if a["url"] not in used_urls]
            if fresh:
                article = random.choice(fresh[:4])
                article["cat"] = cat
                return article


    # 全分类都试过还没找到，放开used限制
    for source in random.sample(SOURCES, len(SOURCES)):
        articles = fetch_source(source)
        if articles:
            article = articles[0]
            article["cat"] = source["cat"]
            return article

    return None


# ── AI提炼写作 ────────────────────────────────────────────────────────────────
def write_from_source(article):
    if not DEEPSEEK_KEY:
        return f"<p>测试：{article['title']}</p>"

    prompt = f"""你是一个专注副业赚钱的中文博客作者，读者是25-40岁想增加收入的普通人。

以下是一篇英文资讯：
标题：{article['title']}
来源：{article['source']}
摘要/内容：{article.get('summary', '（无摘要）')}
原文链接：{article['url']}

请根据这篇文章的核心信息，写一篇800-1000字的中文博客文章：
- 不要直译，要提炼核心价值点，结合中国读者视角
- 文章结构：钩子开头 + 3-4个核心要点（每点给具体数字/方法）+ 行动建议
- 口语化、有干货，读者能直接用
- HTML格式（用<h2><p><ul><li>），不要```html标记
- 不要写文章大标题（单独处理）
- 结尾自然提及：搭副业网站推荐Hostinger（不要广告感）
- 文末注明：「资讯来源：{article['source']}」"""

    try:
        r = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}",
                     "Content-Type": "application/json"},
            json={"model": "deepseek-v4-flash",
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.7},
            timeout=90,
        )
        content = r.json()["choices"][0]["message"]["content"].strip()
        print(f"  [DeepSeek] 完成 {len(content)} 字")
        return content
    except Exception as e:
        print(f"  [DeepSeek] 失败: {e}")
        return None  # 失败时不发布


def gen_cn_title(article):
    """用AI生成吸引人的中文标题"""
    if not DEEPSEEK_KEY:
        return article["title"]
    try:
        r = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}",
                     "Content-Type": "application/json"},
            json={"model": "deepseek-v3-0324",
                  "messages": [{"role": "user", "content":
                      f"把这个英文标题翻译成吸引人的中文博客标题（10-20字，口语化，有好奇心驱动）：\n{article['title']}\n只输出标题，不加引号"}],
                  "model": "deepseek-v4-flash",
                  "temperature": 0.6},
            timeout=30,
        )
        return r.json()["choices"][0]["message"]["content"].strip()
    except:
        return article["title"]


# ── WordPress发布 ─────────────────────────────────────────────────────────────
CAT_CN = {
    "AI副业": "AI副业", "海外接单": "海外接单", "信息差": "信息差",
    "被动收入": "被动收入", "跨境电商": "跨境电商",
}

def get_or_create_category(name, auth_h):
    try:
        r = requests.get(f"{WP_BASE}/categories?search={name}&per_page=5",
                         headers=auth_h, timeout=10)
        for c in r.json():
            if c["name"] == name: return c["id"]
        r2 = requests.post(f"{WP_BASE}/categories",
                           headers={**auth_h, "Content-Type": "application/json"},
                           json={"name": name}, timeout=10)
        return r2.json().get("id")
    except: return None


def publish_post(title_cn, content, article):
    cred   = b64encode(f"{WP_USER}:{WP_APP_PASS}".encode()).decode()
    auth_h = {"Authorization": f"Basic {cred}"}
    cat_id = get_or_create_category(CAT_CN.get(article["cat"], article["cat"]), auth_h)

    payload = {
        "title":   title_cn,
        "content": content,
        "status":  "publish",
        "format":  "standard",
    }
    if cat_id:
        payload["categories"] = [cat_id]

    try:
        r = requests.post(f"{WP_BASE}/posts",
                          headers={**auth_h, "Content-Type": "application/json"},
                          json=payload, timeout=20)
        data = r.json()
        if "id" in data:
            print(f"  ✅ 发布成功: {data['link']}")
            return data["link"]
        else:
            print(f"  ❌ 发布失败: {data}")
            return None
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        return None


# ── 主流程 ────────────────────────────────────────────────────────────────────
def main():
    print(f"🚀 zfuye.org 自动发布 — {TODAY} UTC+{HOUR_U}h")
    log = load_log()

    article = pick_article(log)
    if not article:
        print("  ⚠️ 没有新文章可用，跳过")
        return

    print(f"  来源: {article['source']} [{article['cat']}]")
    print(f"  原标题: {article['title'][:60]}")

    title_cn = gen_cn_title(article)
    print(f"  中文标题: {title_cn}")

    content = write_from_source(article)
    if not content:
        print("  ⚠️ 内容生成失败，跳过发布")
        return

    link = publish_post(title_cn, content, article)

    if link:
        log.setdefault("used_urls", []).append(article["url"])
        log.setdefault("published", []).append({
            "date": TODAY, "title": title_cn,
            "source": article["source"], "url": link
        })
        # 只保留最近500条used_urls
        if len(log["used_urls"]) > 500:
            log["used_urls"] = log["used_urls"][-500:]
        save_log(log)

    print("✅ 完成")


if __name__ == "__main__":
    main()
