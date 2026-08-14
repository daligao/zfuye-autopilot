#!/usr/bin/env python3
"""
zfuye.org 自动发布机器人
真实来源抓取 → DeepSeek提炼翻译 → WordPress发布
"""

import os, json, random, datetime, requests, re
import xml.etree.ElementTree as ET
from html import unescape
from base64 import b64encode
from urllib.parse import urlparse

DEEPSEEK_KEY   = os.environ.get("DEEPSEEK_KEY", "")
WP_USER        = os.environ.get("WP_USER", "")
WP_APP_PASS    = os.environ.get("WP_APP_PASS", "")
WEBSHARE_USER  = os.environ.get("WEBSHARE_USER", "")
WEBSHARE_PASS  = os.environ.get("WEBSHARE_PASS", "")
WP_BASE        = "https://www.zfuye.org/wp-json/wp/v2"

# 需要走代理才能绕过软付费墙的域名
PROXY_DOMAINS = {"medium.com", "entrepreneur.com"}

TODAY  = datetime.date.today().isoformat()
HOUR_U = datetime.datetime.utcnow().hour  # 0=早, 6=午, 12=晚

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
LOG_PATH = "data/log.json"

# ── 数据源配置 ────────────────────────────────────────────────────────────────
SOURCES = [
    # AI副业（英文）
    {"name": "ProductHunt",           "cat": "AI副业",  "type": "rss", "lang": "en",
     "url": "https://www.producthunt.com/feed"},
    {"name": "Niche Pursuits",        "cat": "AI副业",  "type": "rss", "lang": "en",
     "url": "https://www.nichepursuits.com/feed/"},
    {"name": "Blogging Wizard",       "cat": "AI副业",  "type": "rss", "lang": "en",
     "url": "https://bloggingwizard.com/feed/"},
    {"name": "Starter Story",         "cat": "AI副业",  "type": "rss", "lang": "en",
     "url": "https://www.starterstory.com/rss"},
    {"name": "Noah Kagan",            "cat": "AI副业",  "type": "rss", "lang": "en",
     "url": "https://noahkagan.com/feed/"},

    # 海外接单（英文）
    {"name": "Entrepreneur",          "cat": "海外接单", "type": "rss", "lang": "en",
     "url": "https://www.entrepreneur.com/latest.rss"},
    {"name": "Side Hustle Nation",    "cat": "海外接单", "type": "rss", "lang": "en",
     "url": "https://www.sidehustlenation.com/feed/"},
    {"name": "Millo",                 "cat": "海外接单", "type": "rss", "lang": "en",
     "url": "https://millo.co/feed"},
    {"name": "My Wife Quit Her Job",  "cat": "海外接单", "type": "rss", "lang": "en",
     "url": "https://mywifequitherjob.com/feed/"},
    {"name": "Freelancers Union",     "cat": "海外接单", "type": "rss", "lang": "en",
     "url": "https://blog.freelancersunion.org/feed/"},

    # 信息差·副业（英文）
    {"name": "Medium·副业",           "cat": "信息差",   "type": "rss", "lang": "en",
     "url": "https://medium.com/feed/tag/side-hustle"},
    {"name": "Medium·创业",           "cat": "信息差",   "type": "rss", "lang": "en",
     "url": "https://medium.com/feed/tag/entrepreneurship"},
    {"name": "Making Sense of Cents", "cat": "信息差",   "type": "rss", "lang": "en",
     "url": "https://www.makingsenseofcents.com/feed"},
    {"name": "Dollar Sprout",         "cat": "信息差",   "type": "rss", "lang": "en",
     "url": "https://dollarsprout.com/feed/"},
    {"name": "The Hustle",            "cat": "信息差",   "type": "rss", "lang": "en",
     "url": "https://thehustle.co/feed/"},

    # 被动收入（英文）
    {"name": "Medium·被动收入",       "cat": "被动收入", "type": "rss", "lang": "en",
     "url": "https://medium.com/feed/tag/passive-income"},
    {"name": "Smart Passive Income",  "cat": "被动收入", "type": "rss", "lang": "en",
     "url": "https://www.smartpassiveincome.com/feed/"},
    {"name": "Financial Samurai",     "cat": "被动收入", "type": "rss", "lang": "en",
     "url": "https://www.financialsamurai.com/feed/"},
    {"name": "Well Kept Wallet",      "cat": "被动收入", "type": "rss", "lang": "en",
     "url": "https://wellkeptwallet.com/feed/"},
    {"name": "Passive Income MD",     "cat": "被动收入", "type": "rss", "lang": "en",
     "url": "https://passiveincomemd.com/feed/"},

    # 跨境电商（英文）
    {"name": "Entrepreneur·电商",     "cat": "跨境电商", "type": "rss", "lang": "en",
     "url": "https://www.entrepreneur.com/topic/ecommerce.rss"},
    {"name": "A2X Blog",              "cat": "跨境电商", "type": "rss", "lang": "en",
     "url": "https://www.a2xaccounting.com/blog/rss.xml"},
    {"name": "Jungle Scout",          "cat": "跨境电商", "type": "rss", "lang": "en",
     "url": "https://www.junglescout.com/blog/feed/"},

    # ── 中文源（直接发布，省去翻译）────────────────────────────────────────────
    {"name": "36氪",                  "cat": "AI副业",  "type": "rss", "lang": "zh",
     "url": "https://36kr.com/feed"},
    {"name": "虎嗅",                  "cat": "信息差",   "type": "rss", "lang": "zh",
     "url": "https://www.huxiu.com/rss/0.xml"},
    {"name": "爱范儿",                "cat": "信息差",   "type": "rss", "lang": "zh",
     "url": "https://www.ifanr.com/feed"},
    {"name": "钛媒体",                "cat": "跨境电商", "type": "rss", "lang": "zh",
     "url": "https://www.tmtpost.com/rss"},
]

# 所有分类，随机轮转保证均匀覆盖
ALL_CATS = ["AI副业", "海外接单", "信息差", "被动收入", "跨境电商"]


# ── 抓取函数 ──────────────────────────────────────────────────────────────────
def fetch_full_text(url, max_chars=4000):
    """抓取文章页面正文，付费墙域名走Webshare代理"""
    try:
        domain = urlparse(url).hostname or ""
        use_proxy = WEBSHARE_USER and any(d in domain for d in PROXY_DOMAINS)
        proxies = {
            "http":  f"http://{WEBSHARE_USER}:{WEBSHARE_PASS}@p.webshare.io:80/",
            "https": f"http://{WEBSHARE_USER}:{WEBSHARE_PASS}@p.webshare.io:80/",
        } if use_proxy else None
        if use_proxy:
            print(f"  [抓取正文] 走代理: {domain}")
        r = requests.get(url, headers=HEADERS, timeout=15, proxies=proxies)
        r.encoding = r.apparent_encoding or "utf-8"
        html = r.text
        html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.S|re.I)
        text = re.sub(r'<[^>]+>', ' ', html)
        text = unescape(text)
        text = re.sub(r'\s{2,}', '\n', text).strip()
        return text[:max_chars]
    except Exception as e:
        print(f"  [抓取正文] 失败: {e}")
        return ""


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


def fetch_source(source):
    return fetch_rss(source)


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


    # 全分类都试过还没找到，放开 used 限制
    for source in random.sample(SOURCES, len(SOURCES)):
        articles = fetch_source(source)
        if not articles:
            continue
        fresh = [a for a in articles if a["url"] not in used_urls]
        candidates = fresh if fresh else articles[:1]
        if candidates:
            article = candidates[0]
            article["cat"] = source["cat"]
            return article

    return None


# ── AI提炼写作 ────────────────────────────────────────────────────────────────
def write_from_source(article):
    if not DEEPSEEK_KEY:
        return f"<p>测试：{article['title']}</p>"

    # 先抓原文正文
    full_text = fetch_full_text(article["url"])
    body = full_text if len(full_text) > 200 else article.get("summary", "")
    print(f"  [正文] {len(body)} 字符")
    if len(body) < 500:
        print(f"  ⚠️ 正文太短（可能有付费墙），跳过")
        return None

    # ── 中文源：直接用正文 + 只加编者按（省翻译token）──────────────────────────
    if article.get("lang") == "zh":
        prompt = f"""以下是一篇中文资讯：
标题：{article['title']}
来源：{article['source']}
正文内容：{body}
原文链接：{article['url']}

【重要】请先判断这篇文章是否适合发布：
- 如果内容涉及政治、军事、地缘冲突、政府批评、敏感社会议题，请直接回复"SKIP"
- 只发布科技、商业、副业、赚钱、工具、创业类内容

如果内容合适，请做两件事：
1. 把正文内容整理成规范的HTML格式（用<h2><p><ul><li>，保留原有结构）
2. 最后加3个FAQ问答，用读者会搜索的问题，格式：
<h2>常见问题</h2>
<h3>Q：[问题]</h3>
<p>A：[回答，2-3句]</p>
（重复3次）

格式要求：
- 不要写文章大标题
- 不要```html 代码块标记
- 结尾加编者按：<blockquote style="border-left:3px solid #f0a500;padding:12px 16px;margin:24px 0;background:#fffbf0;color:#555">[2-3句AI编辑点评]</blockquote>
- 最后一行：<p style="color:#999;font-size:13px">资讯来源：{article['source']}</p>"""

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
            if content.strip().upper().startswith("SKIP"):
                print(f"  [DeepSeek] 内容不合规，跳过")
                return None
            FAIL_PHRASES = ["未能取得", "无法逐句", "正文内容缺失", "未能获取", "无法翻译", "抓取失败"]
            if any(p in content for p in FAIL_PHRASES):
                print(f"  [DeepSeek] 承认无正文，跳过")
                return None
            print(f"  [DeepSeek·中文] 完成 {len(content)} 字")
            return content
        except Exception as e:
            print(f"  [DeepSeek] 失败: {e}")
            return None

    # ── 英文源：翻译 + 编者按 + FAQ ──────────────────────────────────────────────
    prompt = f"""以下是一篇英文资讯：
标题：{article['title']}
来源：{article['source']}
正文内容：{body}
原文链接：{article['url']}

【重要】请先判断这篇文章是否适合翻译发布：
- 如果内容涉及政治、军事、地缘冲突、政府批评、敏感社会议题，请直接回复"SKIP"，不要翻译
- 只翻译科技、商业、副业、赚钱、工具、创业类内容

如果内容合适，请做三件事：
1. 把原文内容忠实翻译成中文（保留原文的结构和细节，不要删减主要内容）
2. 在翻译正文后加一小段编者点评（2-3句你的看法）
3. 最后加3个FAQ问答，用中国读者会搜索的问题，格式如下：

<h2>常见问题</h2>
<h3>Q：[问题]</h3>
<p>A：[回答，2-3句]</p>
（重复3次）

格式要求：
- HTML格式，用<h2><p><ul><li>
- 不要写文章大标题（标题单独处理）
- 不要```html 代码块标记
- 结尾加：<p style="color:#999;font-size:13px">资讯来源：{article['source']}</p>"""

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
        if content.strip().upper().startswith("SKIP"):
            print(f"  [DeepSeek] 内容不合规，跳过")
            return None
        FAIL_PHRASES = ["未能取得", "无法逐句", "正文内容缺失", "未能获取", "无法翻译", "抓取失败"]
        if any(p in content for p in FAIL_PHRASES):
            print(f"  [DeepSeek] 承认无正文，跳过")
            return None
        print(f"  [DeepSeek] 完成 {len(content)} 字")
        return content
    except Exception as e:
        print(f"  [DeepSeek] 失败: {e}")
        return None


def wrap_with_lock(content, post_url=""):
    """把文章内容包裹进分享锁，post_url已知时直接嵌入静态二维码"""
    import re
    plain = re.sub(r'<[^>]+>', '', content)
    preview = plain[:200].strip() + '……'

    unlock_url = (post_url.rstrip('/') + '?su=1') if post_url else '#'
    qr_url = ('https://api.qrserver.com/v1/create-qr-code/?size=160x160&data='
               + requests.utils.quote(unlock_url, safe=''))

    return f"""
<div id="su-preview-block">
<p style="color:#666;font-size:14px;line-height:1.8">{preview}</p>
</div>

<div id="su-lock-gate" style="border:2px solid #f0a500;border-radius:12px;padding:28px 20px;
  text-align:center;background:#fffbf0;margin:24px 0;">
  <div style="font-size:34px;margin-bottom:6px">📲</div>
  <h3 style="margin:0 0 6px;color:#333;font-size:18px">本文为精华内容</h3>
  <p style="color:#666;margin:0 0 4px;font-size:14px">本站所有内容永久免费，没有任何收费项目。</p>
  <p style="color:#666;margin:0 0 16px;font-size:14px">希望你能把本文分享给有需要的朋友——这是对我们最好的支持。</p>
  <div style="display:inline-block;padding:10px;background:#fff;border-radius:8px;
    border:1px solid #eee;margin-bottom:12px">
    <img src="{qr_url}" width="160" height="160" alt="扫码解锁"/>
  </div>
  <p style="color:#aaa;font-size:12px;margin:0 0 12px">手机微信扫码 · 扫后即解锁全文</p>
  <a id="su-unlock-btn" href="{unlock_url}"
    style="display:inline-block;background:#f0a500;color:#fff;padding:10px 28px;
    border-radius:8px;text-decoration:none;font-size:14px;font-weight:bold">
    已扫码，解锁全文 →
  </a>
</div>

<div id="su-full-content" style="display:none">
{content}
</div>

<script type="text/javascript">
(function(){{
  var key = 'su_' + window.location.pathname;
  if(localStorage.getItem(key)==='1' || window.location.search.indexOf('su=1')!==-1){{
    suReveal();
  }}
  document.getElementById('su-unlock-btn').addEventListener('click', function(e){{
    if(window.location.search.indexOf('su=1')!==-1) return;
    e.preventDefault();
    suCountdown();
  }});
}})();
function suCountdown(){{
  var btn=document.getElementById('su-unlock-btn');
  btn.textContent='顺手转发给朋友，8秒后解锁…';
  btn.style.background='#888';
  var n=8;
  var t=setInterval(function(){{
    n--; btn.textContent='顺手转发给朋友，'+n+'秒后解锁…';
    if(n<=0){{clearInterval(t);suReveal();}}
  }},1000);
}}
function suReveal(){{
  localStorage.setItem('su_'+window.location.pathname,'1');
  var gate=document.getElementById('su-lock-gate');
  var pre=document.getElementById('su-preview-block');
  var full=document.getElementById('su-full-content');
  if(gate)gate.style.display='none';
  if(pre)pre.style.display='none';
  if(full)full.style.display='block';
}}
</script>
"""


def gen_cn_title(article):
    if not DEEPSEEK_KEY:
        return article["title"]
    # 中文源标题已是中文，直接返回
    if article.get("lang") == "zh":
        return article["title"]
    try:
        r = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}",
                     "Content-Type": "application/json"},
            json={
                "model": "deepseek-v4-flash",
                "messages": [{"role": "user", "content":
                    f"""把这个英文标题改写成中文搜索词风格的标题：
- 用中国人会在搜索框输入的词，不要直译
- 带具体数字（金额/时间/步骤数）优先
- 10-18字，口语化
- 人名/品牌名换成"一个美国人""一位创业者"等
- 例子风格："月入5万的副业怎么做""美国人靠租厕所年赚300万""3步建一个自动赚钱网站"
只输出标题，不加引号

英文标题：{article['title']}"""}],
                "temperature": 0.6
            },
            timeout=60,
        )
        title = r.json()["choices"][0]["message"]["content"].strip()
        cn_chars = sum(1 for c in title if '一' <= c <= '鿿')
        if cn_chars < 3:
            print(f"  [标题翻译] 返回英文，重试…")
            raise ValueError("non-chinese title")
        print(f"  [标题翻译] {title}")
        return title
    except Exception as e:
        print(f"  [标题翻译] 失败: {e}，使用原英文标题")
        return article["title"]


# ── WordPress发布 ─────────────────────────────────────────────────────────────
CAT_CN = {
    "AI副业": "AI副业", "海外接单": "海外接单", "信息差": "信息差",
    "被动收入": "被动收入", "跨境电商": "跨境电商",
}

def get_related_posts(cat_name, exclude_id):
    """抓同分类最近3篇文章，返回推荐HTML"""
    try:
        cred   = b64encode(f"{WP_USER}:{WP_APP_PASS}".encode()).decode()
        auth_h = {"Authorization": f"Basic {cred}"}
        # 先拿分类ID
        r = requests.get(f"{WP_BASE}/categories?search={cat_name}&per_page=5",
                         headers=auth_h, timeout=8)
        cats = [c for c in r.json() if c["name"] == cat_name]
        if not cats:
            return ""
        cat_id = cats[0]["id"]
        r2 = requests.get(
            f"{WP_BASE}/posts?categories={cat_id}&exclude={exclude_id}&per_page=3&orderby=date&order=desc",
            headers=auth_h, timeout=8
        )
        posts = r2.json()
        if not posts:
            return ""
        items = "".join(
            f'<li><a href="{p["link"]}">{p["title"]["rendered"]}</a></li>'
            for p in posts
        )
        return f"""
<hr style="margin:32px 0 16px;border:none;border-top:1px solid #eee">
<div style="background:#f5f5f5;border-radius:8px;padding:16px 20px;font-size:14px">
  <p style="margin:0 0 10px;font-weight:bold;color:#333">📖 相关阅读</p>
  <ul style="margin:0;padding-left:18px;line-height:2;color:#555">{items}</ul>
</div>"""
    except Exception as e:
        print(f"  [相关文章] 失败: {e}")
        return ""


def build_faq_schema(content, title):
    """从文章内容提取FAQ，生成JSON-LD schema"""
    import json as _json
    # 从内容里提取 Q/A 对
    qs = re.findall(r'<h3>Q[：:]\s*(.+?)</h3>\s*<p>A[：:]\s*(.+?)</p>', content, re.S)
    if not qs:
        return ""
    entities = [{"@type": "Question", "name": q.strip(),
                 "acceptedAnswer": {"@type": "Answer", "text": re.sub(r'<[^>]+>', '', a).strip()}}
                for q, a in qs[:5]]
    schema = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": entities}
    return f'\n<script type="application/ld+json">{_json.dumps(schema, ensure_ascii=False)}</script>\n'


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


def publish_post(title_cn, raw_content, article):
    cred   = b64encode(f"{WP_USER}:{WP_APP_PASS}".encode()).decode()
    auth_h = {"Authorization": f"Basic {cred}"}
    cat_id = get_or_create_category(CAT_CN.get(article["cat"], article["cat"]), auth_h)

    payload = {
        "title":   {"raw": title_cn},
        "content": {"raw": raw_content},   # raw 格式绕过 wp_kses 过滤，保留 script 标签
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
            post_id   = data["id"]
            post_link = data["link"]
            print(f"  ✅ 发布成功: {post_link}")
            return post_id, post_link
        else:
            print(f"  ❌ 发布失败: {data}")
            return None, None
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        return None, None


def update_post_content(post_id, raw_content):
    """第二步：用已知 URL 更新内容（静态二维码）"""
    cred   = b64encode(f"{WP_USER}:{WP_APP_PASS}".encode()).decode()
    auth_h = {"Authorization": f"Basic {cred}", "Content-Type": "application/json"}
    try:
        requests.post(f"{WP_BASE}/posts/{post_id}",
                      headers=auth_h,
                      json={"content": {"raw": raw_content}},
                      timeout=20)
        print(f"  ✅ 二维码已更新")
    except Exception as e:
        print(f"  ⚠️ 更新二维码失败: {e}")


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
        print("  ⚠️ 内容生成失败或内容不合规，跳过发布")
        return
    if len(content) < 300:
        print(f"  ⚠️ 内容过短（{len(content)}字），跳过发布")
        return

    content += """
<hr style="margin:40px 0 24px;border:none;border-top:1px solid #eee">
<div style="border:2px solid #f0a500;border-radius:10px;background:#fffbf0;padding:20px 24px;font-size:14px;line-height:1.9">
  <p style="margin:0 0 4px;font-size:13px;color:#c47f00;font-weight:bold;letter-spacing:1px">🏷️ 限时推荐</p>
  <p style="margin:0 0 12px;font-weight:bold;font-size:16px;color:#333">📌 关于本站</p>
  <p style="margin:0 0 14px;color:#555">内容自动翻译自海外科技媒体，仅供个人学习参考。</p>
  <p style="margin:0 0 8px;font-weight:bold;color:#333">🛠️ 站长的同款工具</p>
  <ul style="margin:0 0 16px;padding-left:20px;color:#555">
    <li>主机：<a href="https://zfuye.org/3528.html" target="_blank" rel="nofollow" style="color:#c47f00;font-weight:bold">Hostinger</a>（$2.99/月起）</li>
    <li>域名：<a href="https://www.namecheap.com" target="_blank" rel="nofollow" style="color:#c47f00;font-weight:bold">Namecheap</a></li>
    <li>AI工具：GitHub Copilot（<a href="https://zfuye.org/3528.html" target="_blank" rel="nofollow" style="color:#c47f00;font-weight:bold">操作方法：在这里</a>）</li>
  </ul>
  <p style="margin:0;color:#c47f00;font-weight:bold">你也可以做一台自动赚钱的网站机器 🚀</p>
</div>"""

    post_id, link = publish_post(title_cn, content, article)

    if post_id and link:
        # 发布成功后追加：相关文章 + FAQ JSON-LD
        related_html = get_related_posts(article["cat"], post_id)
        faq_schema   = build_faq_schema(content, title_cn)
        if related_html or faq_schema:
            update_post_content(post_id, content + faq_schema + related_html)

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
