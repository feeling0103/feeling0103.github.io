#!/usr/bin/env python3
"""
内容聚合器 v2 — 每日自动从多平台抓取高质量内容
平台: B站 (搜索+每周必看), GitHub Trending, 掘金推荐, 精选轮换
分类: 大数据技术, 编程开发, AI/机器学习, 基金理财, 健身健康, 大学生成长, 形象管理
输出: knowledge.json
"""

import json
import os
import re
import time
import random
from datetime import datetime

import requests

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}
BILIBILI_HEADERS = {**HEADERS, "Referer": "https://www.bilibili.com/"}


# ═══════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════

def _fmt(n) -> str:
    """12345 → 1.2万"""
    try:
        n = int(str(n).replace(",", "").replace("万", "0000").replace("亿", "00000000"))
    except (ValueError, TypeError):
        return str(n)
    if n >= 1_0000_0000:
        return f"{n/1_0000_0000:.1f}亿"
    if n >= 1_0000:
        return f"{n/1_0000:.1f}万"
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)


def _clean_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def _strip(s: str, n: int = 80) -> str:
    s = (s or "").strip()
    return s[:n] + ("…" if len(s) > n else "")


# ═══════════════════════════════════════════
#  1. B站 — 搜索 API
# ═══════════════════════════════════════════

BILIBILI_QUERIES = [
    ("大数据 Hadoop Spark", "大数据技术"),
    ("Python 数据分析", "编程开发"),
    ("SQL 数据库 教程", "编程开发"),
    ("机器学习 入门 深度学习", "AI/机器学习"),
    ("基金 定投 理财 入门", "基金理财"),
    ("大学生 健身 增肌 减脂", "健身健康"),
    ("大学生 学习方法 自律", "大学生成长"),
    ("大学生 穿搭 化妆 护肤", "形象管理"),
    ("数据分析师 就业", "职业发展"),
    ("Tableau PowerBI 可视化", "大数据技术"),
    ("LeetCode 算法 刷题", "编程开发"),
]


def fetch_bilibili(query: str, category: str, count: int = 5) -> list:
    for attempt in range(2):
        try:
            r = requests.get(
                "https://api.bilibili.com/x/web-interface/search/type",
                params={"search_type": "video", "keyword": query, "order": "click", "page": 1, "page_size": count},
                headers=BILIBILI_HEADERS, timeout=15,
            )
            if r.status_code == 412:
                time.sleep(1)
                continue
            # Some responses may be HTML on error, skip
            if not r.text or r.text[0] != "{":
                time.sleep(1)
                continue
            data = r.json()
            if data.get("code") != 0:
                return []
            return [
                {
                    "title": _clean_html(v.get("title", "")),
                    "url": f"https://www.bilibili.com/video/{v.get('bvid','')}",
                    "desc": _strip(v.get("description", "")) or "B站热门教程",
                    "source": "B站",
                    "category": category,
                    "author": v.get("author", ""),
                    "stats": f"{_fmt(v.get('play', 0))} 播放",
                    "type": "video",
                    "ts": int(time.time()),
                }
                for v in data.get("data", {}).get("result", [])[:count]
            ]
        except Exception as e:
            if attempt == 1:
                print(f"  ⚠ B站 [{query[:20]}]: {e}")
            time.sleep(1)
    return []


# ═══════════════════════════════════════════
#  2. B站 — 每周必看 (热门筛选)
# ═══════════════════════════════════════════

BILIBILI_CANDIDATES = [
    ("大数据", "大数据技术"),
    ("数据科学", "大数据技术"),
    ("数据分析", "大数据技术"),
    ("Python", "编程开发"),
    ("编程", "编程开发"),
    ("程序员", "编程开发"),
    ("SQL", "编程开发"),
    ("AI", "AI/机器学习"),
    ("人工智能", "AI/机器学习"),
    ("深度学习", "AI/机器学习"),
    ("大模型", "AI/机器学习"),
    ("机器学习", "AI/机器学习"),
    ("算法", "编程开发"),
    ("理财", "基金理财"),
    ("基金", "基金理财"),
    ("投资", "基金理财"),
    ("健身", "健身健康"),
    ("减脂", "健身健康"),
    ("增肌", "健身健康"),
    ("自律", "大学生成长"),
    ("考研", "大学生成长"),
    ("大学生", "大学生成长"),
    ("面试", "职业发展"),
    ("求职", "职业发展"),
]


def fetch_bilibili_weekly() -> list:
    try:
        # 获取最新一期编号
        r = requests.get(
            "https://api.bilibili.com/x/web-interface/popular/series/list",
            headers=BILIBILI_HEADERS, timeout=15,
        )
        series_list = r.json().get("data", {}).get("list", [])
        if not series_list:
            return []
        number = series_list[-1].get("number", 0)

        # 获取内容
        r2 = requests.get(
            f"https://api.bilibili.com/x/web-interface/popular/series/one?number={number}",
            headers=BILIBILI_HEADERS, timeout=15,
        )
        videos = r2.json().get("data", {}).get("list", [])

        results = []
        for v in videos:
            title = v.get("title", "")
            desc = v.get("rcmd_reason", {}).get("content", "")
            for kw, cat in BILIBILI_CANDIDATES:
                if kw.lower() in title.lower() or kw.lower() in (desc or "").lower():
                    results.append({
                        "title": title,
                        "url": f"https://www.bilibili.com/video/{v.get('bvid','')}",
                        "desc": desc or "B站每周必看热门",
                        "source": "B站·每周必看",
                        "category": cat,
                        "author": v.get("owner", {}).get("name", ""),
                        "stats": f"{_fmt(v.get('stat',{}).get('view',0))} 播放",
                        "type": "video",
                        "ts": int(time.time()),
                    })
                    break
            if len(results) >= 12:
                break
        return results
    except Exception as e:
        print(f"  ⚠ B站每周必看: {e}")
        return []


# ═══════════════════════════════════════════
#  3. GitHub — Search API
# ═══════════════════════════════════════════

GITHUB_QUERIES = [
    ("data-science+language:python+stars:>500", "大数据技术"),
    ("machine-learning+stars:>1000", "AI/机器学习"),
    ("data-engineering+stars:>100", "大数据技术"),
    ("llm+stars:>500", "AI/机器学习"),
]


def fetch_github() -> list:
    results = []
    for query, cat in GITHUB_QUERIES:
        try:
            r = requests.get(
                "https://api.github.com/search/repositories",
                params={"q": query, "sort": "stars", "order": "desc", "per_page": 3},
                headers=HEADERS, timeout=15,
            )
            if r.status_code in (403, 429):
                print(f"  ⚠ GitHub rate limited")
                break
            if r.status_code != 200:
                time.sleep(2)
                continue
            data = r.json()
            for repo in data.get("items", [])[:3]:
                results.append({
                    "title": f"{repo.get('full_name', '')}",
                    "url": repo.get("html_url", ""),
                    "desc": _strip(repo.get("description") or f"{repo.get('language','')} 开源项目"),
                    "source": "GitHub Trending",
                    "category": cat,
                    "author": "",
                    "stats": f"⭐ {_fmt(repo.get('stargazers_count', 0))} · {repo.get('language','')}",
                    "type": "repo",
                    "ts": int(time.time()),
                })
            time.sleep(3)  # Be gentle with GitHub API
        except Exception as e:
            print(f"  ⚠ GitHub [{query[:30]}]: {e}")
    return results


# ═══════════════════════════════════════════
#  4. 掘金 — 推荐流 API
# ═══════════════════════════════════════════

JUEJIN_TAG_MAP = {
    "后端": "编程开发", "前端": "编程开发", "Android": "编程开发",
    "iOS": "编程开发", "Go": "编程开发", "Rust": "编程开发",
    "人工智能": "AI/机器学习", "算法": "编程开发",
    "大数据": "大数据技术", "数据库": "大数据技术",
    "架构": "编程开发", "Python": "编程开发",
    "机器学习": "AI/机器学习", "深度学习": "AI/机器学习",
    "LLM": "AI/机器学习", "NLP": "AI/机器学习",
    "数据科学": "大数据技术", "数据分析": "大数据技术",
    "程序员": "编程开发", "面试": "职业发展",
    "GitHub": "编程开发", "Linux": "编程开发",
    "设计模式": "编程开发", "微服务": "编程开发",
    "Docker": "编程开发", "Kubernetes": "编程开发",
}


def fetch_juejin() -> list:
    results = []
    try:
        r = requests.post(
            "https://api.juejin.cn/recommend_api/v1/article/recommend_all_feed",
            json={"id_type": 2, "sort_type": 200, "cursor": "0", "limit": 40},
            headers={**HEADERS, "Content-Type": "application/json"},
            timeout=15,
        )
        d = r.json()
        if d.get("err_no") != 0:
            return []
        for item in d.get("data", [])[:40]:
            info = item.get("item_info", {})
            article = info.get("article_info", {})
            title = article.get("title", "")
            brief = article.get("brief_content", "")[:100]
            if not title:
                continue
            # Use tags to categorize
            tags = info.get("tags", [])
            our_cat = None
            tag_names = []
            for t in tags:
                tn = t.get("tag_name", "")
                tag_names.append(tn)
                if not our_cat:
                    our_cat = JUEJIN_TAG_MAP.get(tn)
            if not our_cat:
                continue  # Skip if no matching tag category
            results.append({
                "title": title,
                "url": f"https://juejin.cn/post/{info.get('article_id','')}",
                "desc": brief or "掘金热门技术文章",
                "source": "掘金推荐",
                "category": our_cat,
                "author": info.get("author_user_info", {}).get("user_name", ""),
                "stats": f"{_fmt(article.get('view_count',0))} 阅读 · {_fmt(article.get('digg_count',0))} 赞 · {' '.join(tag_names[:2])}",
                "type": "article",
                "ts": int(time.time()),
            })
    except Exception as e:
        print(f"  ⚠ 掘金: {e}")
    return results


# ═══════════════════════════════════════════
#  5. 精选轮换 — 固定优质资源 + 每日新鲜推荐
# ═══════════════════════════════════════════

FIXED_TOP = [
    {"title": "🏆 B站·尚硅谷 大数据全套教程", "url": "https://www.bilibili.com/video/BV1W44y1B7GL", "desc": "Hadoop/Hive/Spark/Flink 从入门到实战，B站播放量最高的大数据教程", "source": "精选推荐", "category": "大数据技术", "type": "video", "ts": 0},
    {"title": "🏆 Kaggle 数据科学竞赛平台", "url": "https://www.kaggle.com/", "desc": "实战数据集+竞赛+在线Notebook，练习数据分析的最佳平台", "source": "精选推荐", "category": "大数据技术", "type": "tool", "ts": 0},
    {"title": "🏆 LeetCode 算法刷题平台", "url": "https://leetcode.cn/", "desc": "2000+算法题+面试题库，程序员求职必备", "source": "精选推荐", "category": "编程开发", "type": "tool", "ts": 0},
    {"title": "🏆 且慢 — 基金定投分析与组合", "url": "https://qieman.com/", "desc": "基金筛选、定投回测、资产配置，学生党入门友好", "source": "精选推荐", "category": "基金理财", "type": "tool", "ts": 0},
    {"title": "🏆 Keep — 健身训练计划", "url": "https://www.keep.com/", "desc": "免费居家/宿舍训练课程，增肌减脂瑜伽全覆盖", "source": "精选推荐", "category": "健身健康", "type": "tool", "ts": 0},
    {"title": "🏆 中国大学MOOC", "url": "https://www.icourse163.org/", "desc": "985高校公开课：大数据、统计学、机器学习、Python", "source": "精选推荐", "category": "大学生成长", "type": "course", "ts": 0},
]

# 每日轮换 — CSDN/博客园/B站专栏/GitHub 优质文章（按主题分组）
# 注意：不使用知乎链接，因为知乎外链经常打不开
WISDOM_ROTATION = [
    # ── 大数据技术 ──
    [
        {"title": "📖 大数据学习路线图（全网最全）", "url": "https://blog.csdn.net/weixin_42350212/article/details/126454338", "desc": "从零基础到就业，完整的大数据技术栈学习路径（CSDN）", "source": "精选·CSDN", "category": "大数据技术", "type": "article"},
        {"title": "📖 Hadoop、Spark、Flink 三大框架对比", "url": "https://blog.csdn.net/qq_27634797/article/details/115243628", "desc": "三大计算引擎的定位、优缺点和适用场景对比（CSDN）", "source": "精选·CSDN", "category": "大数据技术", "type": "article"},
        {"title": "📖 数据仓库分层设计（ODS/DWD/DWS/ADS）", "url": "https://blog.csdn.net/weixin_43930641/article/details/123999888", "desc": "数仓建模方法论与分层实践（CSDN）", "source": "精选·CSDN", "category": "大数据技术", "type": "article"},
        {"title": "📖 SQL 窗口函数完全指南", "url": "https://blog.csdn.net/qq_27634797/article/details/113814329", "desc": "ROW_NUMBER/RANK/LAG/LEAD 实战详解（CSDN）", "source": "精选·CSDN", "category": "大数据技术", "type": "article"},
        {"title": "📖 数据分析与统计学基础", "url": "https://blog.csdn.net/qq_35866846/article/details/103052604", "desc": "描述统计、推断统计、假设检验入门（CSDN）", "source": "精选·CSDN", "category": "大数据技术", "type": "article"},
        {"title": "📖 Pandas 数据清洗实战指南", "url": "https://blog.csdn.net/qq_27634797/article/details/113385932", "desc": "缺失值、异常值、重复数据处理全流程（CSDN）", "source": "精选·CSDN", "category": "大数据技术", "type": "article"},
    ],
    # ── 编程开发 ──
    [
        {"title": "📖 Python 从入门到数据分析全路线", "url": "https://blog.csdn.net/weixin_43930641/article/details/123603158", "desc": "基础语法→爬虫→Web→数据分析完整路径（CSDN）", "source": "精选·CSDN", "category": "编程开发", "type": "article"},
        {"title": "📖 Git & GitHub 从入门到团队协作", "url": "https://blog.csdn.net/qq_27634797/article/details/113532902", "desc": "版本控制+分支管理+PR流程实战（CSDN）", "source": "精选·CSDN", "category": "编程开发", "type": "article"},
        {"title": "📖 Docker 从入门到部署实战", "url": "https://blog.csdn.net/qq_27634797/article/details/113798443", "desc": "容器化部署，开发环境一键搭建（CSDN）", "source": "精选·CSDN", "category": "编程开发", "type": "article"},
        {"title": "📖 Linux 常用命令速查手册", "url": "https://blog.csdn.net/qq_27634797/article/details/112770805", "desc": "大数据开发必备的Linux操作和Shell基础（CSDN）", "source": "精选·CSDN", "category": "编程开发", "type": "article"},
        {"title": "📖 算法与数据结构面试高频题", "url": "https://leetcode.cn/studyplan/top-interview-150/", "desc": "LeetCode 面试经典150题，含解题思路详解", "source": "精选·LeetCode", "category": "编程开发", "type": "tool"},
    ],
    # ── AI/机器学习 ──
    [
        {"title": "📖 机器学习入门路线图", "url": "https://blog.csdn.net/qq_27634797/article/details/113385932", "desc": "吴恩达课程+西瓜书+实战项目路线（CSDN）", "source": "精选·CSDN", "category": "AI/机器学习", "type": "article"},
        {"title": "📖 PyTorch vs TensorFlow 框架对比", "url": "https://blog.csdn.net/qq_27634797/article/details/113843522", "desc": "两大深度学习框架优劣对比及选型建议（CSDN）", "source": "精选·CSDN", "category": "AI/机器学习", "type": "article"},
        {"title": "📖 NLP 自然语言处理入门指南", "url": "https://blog.csdn.net/qq_27634797/article/details/113385932", "desc": "分词、词向量、文本分类基础概念（CSDN）", "source": "精选·CSDN", "category": "AI/机器学习", "type": "article"},
        {"title": "📖 大模型（LLM）学习资源汇总", "url": "https://github.com/Hannibal046/Awesome-LLM", "desc": "Awesome-LLM: 大模型论文/工具/教程一站式导航（GitHub）", "source": "精选·GitHub", "category": "AI/机器学习", "type": "repo"},
    ],
    # ── 基金理财 ──
    [
        {"title": "📖 大学生基金定投入门指南", "url": "https://www.bilibili.com/video/BV1Ba4y1f7Ej", "desc": "每月500起投、选基方法、止盈策略（B站视频）", "source": "精选·B站", "category": "基金理财", "type": "video"},
        {"title": "📖 指数基金定投：懒人投资法", "url": "https://www.bilibili.com/video/BV1kA41187jF", "desc": "沪深300+中证500 定投策略详解（B站视频）", "source": "精选·B站", "category": "基金理财", "type": "video"},
        {"title": "📖 投资理财入门书单推荐", "url": "https://www.bilibili.com/video/BV1x5411j7qK", "desc": "《富爸爸穷爸爸》《小狗钱钱》《指数基金投资指南》（B站视频）", "source": "精选·B站", "category": "基金理财", "type": "video"},
        {"title": "📖 学生党理财避坑指南", "url": "https://www.bilibili.com/video/BV1Y24y1Y7Jk", "desc": "消费贷、杀猪盘、盲目追涨的教训（B站视频）", "source": "精选·B站", "category": "基金理财", "type": "video"},
    ],
    # ── 健身健康 ──
    [
        {"title": "📖 宿舍/居家徒手健身方案", "url": "https://www.bilibili.com/video/BV1fJ411U7y1", "desc": "无需器械，宿舍就能练的全身训练方案（B站视频）", "source": "精选·B站", "category": "健身健康", "type": "video"},
        {"title": "📖 科学饮食：增肌减脂怎么吃", "url": "https://www.bilibili.com/video/BV1rJ411q71L", "desc": "蛋白质/碳水/脂肪配比+食堂实操指南（B站视频）", "source": "精选·B站", "category": "健身健康", "type": "video"},
        {"title": "📖 体态矫正：驼背/圆肩/骨盆前倾", "url": "https://www.bilibili.com/video/BV1PA411b7WT", "desc": "久坐学生必看的体态改善跟练（B站视频）", "source": "精选·B站", "category": "健身健康", "type": "video"},
        {"title": "📖 高质量睡眠改善指南", "url": "https://www.bilibili.com/video/BV1gK4y1a7GJ", "desc": "作息调整+睡前习惯+睡眠环境优化（B站视频）", "source": "精选·B站", "category": "健身健康", "type": "video"},
    ],
    # ── 大学生成长 ──
    [
        {"title": "📖 大学四年如何高效规划", "url": "https://www.bilibili.com/video/BV1Cg4y1q7tS", "desc": "大一到大四每个阶段的重点和避坑指南（B站视频）", "source": "精选·B站", "category": "大学生成长", "type": "video"},
        {"title": "📖 给大学生的实用成长建议", "url": "https://www.bilibili.com/video/BV1dZ4y1p7tM", "desc": "来自学长学姐的大学经验分享（B站视频）", "source": "精选·B站", "category": "大学生成长", "type": "video"},
        {"title": "📖 费曼学习法：最有效的学习方法", "url": "https://www.bilibili.com/video/BV1ra4y1H7ih", "desc": "用教别人的方式学知识，理解率大幅提升（B站视频）", "source": "精选·B站", "category": "大学生成长", "type": "video"},
        {"title": "📖 番茄工作法高效学习实战", "url": "https://www.bilibili.com/video/BV1CA41187Kx", "desc": "25分钟专注+5分钟休息的时间管理法（B站视频）", "source": "精选·B站", "category": "大学生成长", "type": "video"},
        {"title": "📖 信息时代如何独立思考", "url": "https://www.bilibili.com/video/BV1AK4y1a7q3", "desc": "批判性思维训练：辨别信息真伪的方法（B站视频）", "source": "精选·B站", "category": "大学生成长", "type": "video"},
        {"title": "📖 如何写出高质量技术博客", "url": "https://blog.csdn.net/qq_27634797/article/details/113385932", "desc": "从选题、结构到排版的技术写作指南（CSDN）", "source": "精选·CSDN", "category": "大学生成长", "type": "article"},
    ],
    # ── 职业发展 ──
    [
        {"title": "📖 大数据专业就业方向与薪资", "url": "https://www.bilibili.com/video/BV1Rm421j7r9", "desc": "数据分析师/大数据工程师/算法工程师岗位拆解（B站视频）", "source": "精选·B站", "category": "职业发展", "type": "video"},
        {"title": "📖 数据分析面试高频真题解析", "url": "https://www.bilibili.com/video/BV1jZ4y1p7rq", "desc": "SQL/统计学/业务分析 面试真题讲解（B站视频）", "source": "精选·B站", "category": "职业发展", "type": "video"},
        {"title": "📖 简历这样写，面试邀约多3倍", "url": "https://www.bilibili.com/video/BV12a41187r2", "desc": "STAR法则+项目包装+量化成果详解（B站视频）", "source": "精选·B站", "category": "职业发展", "type": "video"},
        {"title": "📖 大学生实习避坑指南", "url": "https://www.bilibili.com/video/BV1Hv4y1H7eN", "desc": "如何辨别好实习、保护权益、最大化收获（B站视频）", "source": "精选·B站", "category": "职业发展", "type": "video"},
    ],
    # ── 形象管理（女生专区）──
    [
        {"title": "📖 女生胶囊衣橱穿搭法", "url": "https://www.bilibili.com/video/BV1b64y1U7TG", "desc": "用最少的衣服搭出100种风格（B站视频）", "source": "精选·B站", "category": "形象管理", "type": "video"},
        {"title": "📖 新手化妆入门：全套流程", "url": "https://www.bilibili.com/video/BV16u411z7Kj", "desc": "从护肤到定妆，学生党友好化妆教程（B站视频）", "source": "精选·B站", "category": "形象管理", "type": "video"},
        {"title": "📖 学生党平价化妆品推荐", "url": "https://www.bilibili.com/video/BV1D4411U7yX", "desc": "百元以内好用的化妆品合集，学生友好（B站视频）", "source": "精选·B站", "category": "形象管理", "type": "video"},
        {"title": "📖 根据脸型选发型全攻略", "url": "https://www.bilibili.com/video/BV1Rk4y1q7Ui", "desc": "圆脸/方脸/长脸适合的发型推荐（B站视频）", "source": "精选·B站", "category": "形象管理", "type": "video"},
        {"title": "📖 体态决定气质：矫正训练", "url": "https://www.bilibili.com/video/BV15x411U7vR", "desc": "站姿/走姿/坐姿改善，提升整体形象（B站视频）", "source": "精选·B站", "category": "形象管理", "type": "video"},
        {"title": "📖 科学护肤入门指南", "url": "https://www.bilibili.com/video/BV1SJ411x7Sj", "desc": "分辨肤质+基础流程，告别盲目护肤（B站视频）", "source": "精选·B站", "category": "形象管理", "type": "video"},
        {"title": "📖 小红书穿搭美妆灵感", "url": "https://www.xiaohongshu.com/", "desc": "搜索#学生穿搭 #平价化妆品 获取海量灵感", "source": "精选推荐", "category": "形象管理", "type": "tool"},
    ],
]


def fetch_wisdom_rotation() -> list:
    """按日期轮换精选资源，每天每类出2-3条"""
    day_of_year = datetime.now().timetuple().tm_yday
    results = list(FIXED_TOP)  # 固定精选始终保留
    for group in WISDOM_ROTATION:
        n = min(3, len(group))
        start = (day_of_year * 3) % len(group)
        picked = []
        for i in range(n):
            idx = (start + i) % len(group)
            item = dict(group[idx])
            item["ts"] = int(time.time())
            picked.append(item)
        results.extend(picked)
    return results


# ═══════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════

def deduplicate(items: list) -> list:
    seen = set()
    result = []
    for item in items:
        key = item["url"]
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def main():
    print("=" * 60)
    print(f"📡 内容聚合器 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_items = []

    # 1. B站搜索
    print("\n🎬 [1/4] B站搜索...")
    bili_count = 0
    for query, cat in BILIBILI_QUERIES:
        items = fetch_bilibili(query, cat, count=4)
        all_items.extend(items)
        if items:
            bili_count += len(items)
            print(f"  ✓ {query[:25]:25s} → {len(items)} 条")
        time.sleep(0.4)
    print(f"  → B站搜索共 {bili_count} 条")

    # 2. B站每周必看
    print("\n🎬 [2/4] B站每周必看...")
    weekly = fetch_bilibili_weekly()
    all_items.extend(weekly)
    print(f"  → {len(weekly)} 条")

    # 3. GitHub Trending
    print("\n🐙 [3/4] GitHub Trending...")
    gh = fetch_github()
    all_items.extend(gh)
    print(f"  → {len(gh)} 条")

    # 4. 掘金推荐
    print("\n📝 [4/4] 掘金推荐...")
    jj = fetch_juejin()
    all_items.extend(jj)
    print(f"  → {len(jj)} 条")

    # 5. 精选轮换
    wisdom = fetch_wisdom_rotation()
    all_items.extend(wisdom)
    print(f"\n📚 精选轮换: {len(wisdom)} 条")

    # 去重
    all_items = deduplicate(all_items)

    # 按分类分组
    categories = {}
    for item in all_items:
        cat = item.get("category", "其他")
        categories.setdefault(cat, []).append(item)

    # 每类最多 20 条
    for cat in categories:
        categories[cat] = sorted(
            categories[cat],
            key=lambda x: (x.get("ts", 0) if x.get("source") != "精选推荐" else 0),
            reverse=True,
        )[:20]

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "updated_ts": int(time.time()),
        "total_items": sum(len(v) for v in categories.values()),
        "sources": {
            "B站": bili_count + len(weekly),
            "GitHub": len(gh),
            "掘金": len(jj),
            "精选": len(wisdom),
        },
        "categories": categories,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"✅ 聚合完成! 共 {output['total_items']} 条 → {OUTPUT_PATH}")
    for cat, items in categories.items():
        print(f"   {cat}: {len(items)} 条")
    print("=" * 60)


if __name__ == "__main__":
    main()
