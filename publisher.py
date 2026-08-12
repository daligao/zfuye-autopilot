#!/usr/bin/env python3
"""
zfuye.org 自动发布机器人
每次运行：选题 → DeepSeek写文章 → WordPress发布
"""

import os, json, random, datetime, requests
from base64 import b64encode

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_KEY", "")
WP_USER      = os.environ.get("WP_USER", "")
WP_APP_PASS  = os.environ.get("WP_APP_PASS", "")
WP_BASE      = "https://www.zfuye.org/wp-json/wp/v2"

TODAY = datetime.date.today().isoformat()
NOW_H = datetime.datetime.utcnow().hour  # 0=早, 6=午, 12=晚

# ── 选题库 ────────────────────────────────────────────────────────────────────
TOPICS = [
    # AI副业
    {"title": "用ChatGPT接单月入3000美元的5种方法", "cat": "AI副业"},
    {"title": "Midjourney帮人设计Logo，海外Fiverr接单实操", "cat": "AI副业"},
    {"title": "AI写作工具副业：每天2小时，一个月能赚多少", "cat": "AI副业"},
    {"title": "用Claude帮外国人写商业计划书，客单价500美元", "cat": "AI副业"},
    {"title": "AI翻译副业：不需要会外语也能接国际翻译订单", "cat": "AI副业"},
    {"title": "用AI做YouTube字幕，海外博主愿意付多少钱", "cat": "AI副业"},
    {"title": "NoCode工具+AI，帮小企业建站月入1万的路径", "cat": "AI副业"},
    {"title": "AI配音副业：ElevenLabs接单，定价策略全解", "cat": "AI副业"},

    # 海外接单平台
    {"title": "Fiverr新手开店：从0到第一单的完整操作", "cat": "海外接单"},
    {"title": "Upwork vs Fiverr：2026年哪个平台更容易接到单", "cat": "海外接单"},
    {"title": "Toptal门槛这么高，真的值得申请吗", "cat": "海外接单"},
    {"title": "海外客户为什么愿意付高价：定价心理学实战", "cat": "海外接单"},
    {"title": "从Freelancer到自建客户群：海外接单进阶路径", "cat": "海外接单"},
    {"title": "99designs接单实操：设计师海外变现第一步", "cat": "海外接单"},
    {"title": "Contra平台详解：不收佣金的海外接单新选择", "cat": "海外接单"},

    # 信息差套利
    {"title": "国内外信息差：这5个领域现在还有巨大套利空间", "cat": "信息差"},
    {"title": "海外SaaS工具搬运，如何合法赚取差价", "cat": "信息差"},
    {"title": "跨境知识付费：把国内经验卖给海外华人", "cat": "信息差"},
    {"title": "亚马逊热销品回流国内，信息差套利实操", "cat": "信息差"},
    {"title": "国外便宜订阅合租：Spotify/Netflix拼车站月入分析", "cat": "信息差"},
    {"title": "海外问卷调研平台：信息差变现最简单的方式", "cat": "信息差"},

    # 被动收入
    {"title": "数字产品被动收入：Gumroad/Lemon Squeezy卖什么最好", "cat": "被动收入"},
    {"title": "Notion模板卖钱：月入几千的人都在做什么", "cat": "被动收入"},
    {"title": "联盟营销入门：0粉丝也能开始的推广赚钱方法", "cat": "被动收入"},
    {"title": "Medium付费会员分成：写英文文章能赚多少", "cat": "被动收入"},
    {"title": "博客Hostinger联盟佣金：一次推荐能赚多少钱", "cat": "被动收入"},
    {"title": "股权分红+海外股市：普通人被动收入组合方案", "cat": "被动收入"},
    {"title": "Printful/Printify按需印刷：不囤货的副业生意", "cat": "被动收入"},

    # 跨境电商
    {"title": "2026年速卖通还值得做吗：真实数据分析", "cat": "跨境电商"},
    {"title": "亚马逊FBA新手指南：选品到发货全流程", "cat": "跨境电商"},
    {"title": "独立站vs平台店：跨境电商新手怎么选", "cat": "跨境电商"},
    {"title": "TikTok Shop海外小店：流量红利还剩多少", "cat": "跨境电商"},
    {"title": "代购副业2026：还有没有利润空间详解", "cat": "跨境电商"},

    # 数字游民
    {"title": "数字游民真实收入：他们靠什么养活自己", "cat": "数字游民"},
    {"title": "远程工作平台Top10：找到第一份远程工作", "cat": "数字游民"},
    {"title": "一边旅行一边赚钱：数字游民入门路径", "cat": "数字游民"},
]

CAT_CN = {
    "AI副业": "AI副业",
    "海外接单": "海外接单",
    "信息差": "信息差套利",
    "被动收入": "被动收入",
    "跨境电商": "跨境电商",
    "数字游民": "数字游民",
}

LOG_PATH = "data/log.json"


def load_log():
    try:
        with open(LOG_PATH) as f:
            return json.load(f)
    except:
        return {"published": []}


def save_log(log):
    os.makedirs("data", exist_ok=True)
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def pick_topic(log):
    used = set(log.get("published", []))
    available = [t for t in TOPICS if t["title"] not in used]
    if not available:
        log["published"] = []
        available = TOPICS[:]
    topic = random.choice(available)
    return topic


def write_article(topic):
    if not DEEPSEEK_KEY:
        return f"<p>测试内容：{topic['title']}</p>", []

    slot = ["早上8点", "下午2点", "晚上8点"][min(NOW_H // 6, 2)]
    prompt = f"""你是一个专注副业赚钱的中文博客作者，读者是25-40岁想要增加收入的普通人。

请写一篇关于「{topic['title']}」的实用文章。

要求：
- 800-1000字
- 口语化、有干货，不要空话
- 结构：开头（痛点/钩子）+ 正文3-4个要点 + 结尾行动建议
- 每个要点给出具体可操作的步骤或数字
- 输出HTML格式（用<h2><p><ul><li>标签），不要输出```html标记
- 不要写文章标题（标题单独处理）
- 在结尾自然提到：如果要搭建自己的副业网站，Hostinger是性价比最高的选择之一（用普通文字提及，不要做广告感太强）"""

    try:
        r = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}",
                     "Content-Type": "application/json"},
            json={"model": "deepseek-v3-0324",
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.8},
            timeout=90,
        )
        content = r.json()["choices"][0]["message"]["content"].strip()
        tags = [topic["cat"], "副业", "赚钱", "2026"]
        print(f"  [DeepSeek] 写完 {len(content)} 字")
        return content, tags
    except Exception as e:
        print(f"  [DeepSeek] 失败: {e}")
        return f"<p>{topic['title']}：内容生成失败，请稍后重试。</p>", []


def get_or_create_category(name, auth_header):
    try:
        r = requests.get(f"{WP_BASE}/categories?search={name}&per_page=5",
                         headers=auth_header, timeout=10)
        cats = r.json()
        for c in cats:
            if c["name"] == name:
                return c["id"]
        r2 = requests.post(f"{WP_BASE}/categories",
                           headers={**auth_header, "Content-Type": "application/json"},
                           json={"name": name}, timeout=10)
        return r2.json().get("id")
    except:
        return None


def publish_post(topic, content, tags):
    cred = b64encode(f"{WP_USER}:{WP_APP_PASS}".encode()).decode()
    auth = {"Authorization": f"Basic {cred}"}

    cat_name = CAT_CN.get(topic["cat"], topic["cat"])
    cat_id = get_or_create_category(cat_name, auth)

    payload = {
        "title":   topic["title"],
        "content": content,
        "status":  "publish",
        "format":  "standard",
    }
    if cat_id:
        payload["categories"] = [cat_id]

    try:
        r = requests.post(
            f"{WP_BASE}/posts",
            headers={**auth, "Content-Type": "application/json"},
            json=payload,
            timeout=20,
        )
        data = r.json()
        if "id" in data:
            print(f"  ✅ 发布成功: {data['link']}")
            return data["link"]
        else:
            print(f"  ❌ 发布失败: {data}")
            return None
    except Exception as e:
        print(f"  ❌ 发布异常: {e}")
        return None


def main():
    print(f"🚀 zfuye.org 自动发布 — {TODAY}")
    log = load_log()
    topic = pick_topic(log)
    print(f"  选题: {topic['title']} [{topic['cat']}]")

    content, tags = write_article(topic)
    link = publish_post(topic, content, tags)

    if link:
        log.setdefault("published", []).append(topic["title"])
        log[TODAY] = log.get(TODAY, [])
        log[TODAY].append({"title": topic["title"], "url": link, "cat": topic["cat"]})
        save_log(log)

    print(f"✅ 完成")


if __name__ == "__main__":
    main()
