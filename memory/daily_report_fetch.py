"""daily_report_fetch.py — 日报分层多源采集 (取代 fetch_bing_news.py)
config 驱动 memory/daily_report_sources.json:
  - 双引擎 Bing site: 通道 (R15: TMWebDriver + Playwright) 绕开 .gov Cloudflare 403 (SOP pit #2)
      默认 both: TMWebDriver 优先(保留用户登录态/Cookie) → 失败/数据稀薄回退 Playwright
  - Google News 通道 (R16: Playwright) 覆盖 Bing 漏采的中长尾/学术/小语种
      默认启用, --no-google-news 跳过, fail-soft 不影响 Bing
  - RSS 通道 (stdlib, 无新依赖) 直拉有 feed 的源
  - 多路归一化 + 按真实 URL 去重 -> temp/bing_raw_<YYYYMMDD>.json {_meta, records}
入口零编辑: python memory/daily_report_fetch.py [--date YYYY-MM-DD] [--out PATH] [--min N] [--engine both]
纯函数 unwrap_bing_url / rel_to_abs / dedup_records 可单测 (见 scripts/smoke_daily_report_fetch.py)。
R15 (2026-06-27): 引入 TMWebDriver (../TMWebDriver.py) 作为首选 Bing 采集引擎;
  保留 Playwright 作为降级;TMWebDriver 走 18766 WS 接管用户浏览器避免每次开新 Context。
"""
import argparse, base64, json, os, re, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

BJT = timezone(timedelta(hours=8))
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_PATH = os.path.join(_SCRIPT_DIR, 'daily_report_sources.json')
SITES_PER_QUERY = 4        # 每条 Bing 查询的 OR'd site: 上限 (Bing OR 限制, 见 spec 待验证假设)
MIN_RECORDS = 20           # 低于此值视为数据稀薄 -> exit 3, 触发 SOP pit #12 B 路
RSS_TIMEOUT = 20


# ─── 纯函数 (可单测) ──────────────────────────────────────────

def unwrap_bing_url(href: str) -> str:
    """Bing ck/a 跳转链 -> 真实 URL; 非跳转链或解码失败原样返回。
    形态: .../ck/a?...&u=a1<base64url(真实URL)>"""
    if not href or 'bing.com/ck/a' not in href:
        return href
    u = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get('u', [''])[0]
    if not u.startswith('a1'):
        return href
    raw = u[2:]
    try:
        pad = '=' * (-len(raw) % 4)
        decoded = base64.urlsafe_b64decode(raw + pad).decode('utf-8', 'strict')
    except (ValueError, UnicodeDecodeError):
        return href
    return decoded if decoded.startswith('http') else href


_REL_RE = re.compile(r'(\d+)\s*(minute|min|hour|hr|day|week)s?\s*ago'
                     r'|(\d+)\s*(h|d|w)\b', re.I)
_ABS_RE = re.compile(r'\b([A-Z][a-z]{2})\s+(\d{1,2}),?\s+(\d{4})\b')
_MONTHS = {m: i for i, m in enumerate(
    ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 1)}


def rel_to_abs(rel_time: str, scraped_at: datetime):
    """'1 day ago' / '3h' / 'Jun 19, 2026' -> 'YYYY-MM-DD'; 无法解析返回 None。"""
    if not rel_time:
        return None
    m = _REL_RE.search(rel_time)
    if m:
        # group(1)+group(2) = long form "1 day ago"; group(3)+group(4) = short form "3h"
        if m.group(1) is not None:
            n, unit = int(m.group(1)), m.group(2).lower()
        else:
            n, unit = int(m.group(3)), m.group(4).lower()
        if unit in ('minute', 'min', 'hour', 'hr', 'h'):
            dt = scraped_at
        elif unit in ('day', 'd'):
            dt = scraped_at - timedelta(days=n)
        else:  # week / w
            dt = scraped_at - timedelta(weeks=n)
        return dt.date().isoformat()
    a = _ABS_RE.search(rel_time)
    if a and a.group(1) in _MONTHS:
        try:
            return datetime(int(a.group(3)), _MONTHS[a.group(1)], int(a.group(2))).date().isoformat()
        except ValueError:
            return None
    return None


def dedup_records(records: list) -> list:
    """按真实 URL 去重, 保留首次出现 (跨通道/跨领域)。"""
    seen, out = set(), []
    for r in records:
        key = (r.get('url') or '').rstrip('/')
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def build_bing_url(keywords: list, sites: list) -> str:
    """OR'd 关键词 + OR'd site: 域约束 (前 SITES_PER_QUERY 个); locale 锁 en-US + 7 天窗。
    sites 为空 -> 不限域兜底查询。"""
    if len(keywords) == 1:
        q = keywords[0]
    else:
        q = ' OR '.join(f'"{kw}"' for kw in keywords)
    if sites:
        q += ' (' + ' OR '.join(f'site:{s}' for s in sites[:SITES_PER_QUERY]) + ')'
    params = urllib.parse.urlencode({'q': q, 'qft': 'interval="7"', 'setmkt': 'en-US', 'setlang': 'en'})
    return 'https://www.bing.com/news/search?' + params


def category_queries(conf: dict) -> list:
    """每领域查询: 优先域受限 + 一条不限域兜底 (sites 为空时仅兜底)。"""
    kw, sites = conf.get('keywords', []), conf.get('bing_sites', [])
    qs = [build_bing_url(kw, [])]
    if sites:
        qs.insert(0, build_bing_url(kw, sites))
    return qs


# ─── Bing 通道 (Playwright, 惰性导入) ─────────────────────────

CARD_JS = r"""
() => {
  const seen = new Set(), out = [];
  for (const c of document.querySelectorAll('div.news-card')) {
    const url = c.getAttribute('data-url') || c.getAttribute('url') || '';
    if (!url || !/^https?:/.test(url) || seen.has(url)) continue;
    seen.add(url);
    const title = c.getAttribute('data-title') || (c.querySelector('a.title h2,a.title') || {}).innerText || '';
    const srcEl = c.querySelector('.source a[aria-label*="Search news from"]');
    let source = srcEl ? srcEl.innerText.trim() : '';
    const timeEl = c.querySelector('[aria-label*="ago" i], span[tabindex][aria-label]');
    let rel = timeEl ? (timeEl.getAttribute('aria-label') || timeEl.innerText).trim() : '';
    if (!rel) { const m = (c.innerText||'').match(/\d+\s*(?:h|d|w)\b|\d+\s*(?:minute|hour|day|week)s?\s+ago/i); rel = m ? m[0] : ''; }
    const snippet = (c.querySelector('.snippet') || {}).innerText || (c.innerText||'').slice(0, 800);
    out.push({title: title.trim().slice(0, 300), url, snippet: snippet.slice(0, 800), source, rel_time: rel});
  }
  return out;
}
"""


def fetch_bing(categories: dict, scraped_at: datetime) -> list:
    from playwright.sync_api import sync_playwright  # 惰性: 单测/RSS-only 无需 playwright
    records = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel='chrome',
                                    args=['--no-sandbox', '--disable-blink-features=AutomationControlled'])
        ctx = browser.new_context(locale='en-US',
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/120 Safari/537.36')
        page = ctx.new_page()
        for cat, conf in categories.items():
            got = 0
            for url in category_queries(conf):
                try:
                    page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    page.wait_for_timeout(3000)          # 等 JS 渲染完成
                    cards = page.evaluate(CARD_JS)
                except Exception as e:                   # fail-soft: 单查询失败不中断
                    print(f'[bing:{cat}] FAIL {e}', file=sys.stderr)
                    continue
                for c in cards:
                    c['url'] = unwrap_bing_url(c['url'])
                    records.append(_norm(c, cat, 'news', 'bing', scraped_at))
                got += len(cards)
            print(f'[bing:{cat}] {got} cards', file=sys.stderr)
        browser.close()
    return records


# ─── Bing 通道 (TMWebDriver, R15 2026-06-27 新增, 首选引擎) ───
#
# 通过 ../TMWebDriver.py 接入用户浏览器(保留登录态/Cookie); 无需每次开新 Context。
# 适合 15 查询量级; 不适合高频/并发。
# API 摘要 (见 memory/tmwebdriver_sop.md):
#   d = TMWebDriver()                    # 启动/接入 18766 WS master
#   d.set_session('www.bing.com')        # 锁定域名 (会切到该域名 tab 或新建)
#   d.goto(url)                          # 同步跳 URL
#   d.execute_js(js) -> {'data': value}  # 取 .data 字段才是真实返回
#   d.close()                            # 释放会话
def fetch_bing_tmwebdriver(categories: dict, scraped_at: datetime) -> list:
    import sys as _sys
    _tmwd_path = os.path.join(_SCRIPT_DIR, '..')
    if _tmwd_path not in _sys.path:
        _sys.path.insert(0, _tmwd_path)
    from TMWebDriver import TMWebDriver  # 惰性: master 未启时让上层捕获 ImportError/连接错误
    records = []
    d = None
    try:
        d = TMWebDriver()
        d.set_session('www.bing.com')
        for cat, conf in categories.items():
            got = 0
            for url in category_queries(conf):
                try:
                    d.goto(url)
                    d.execute_js('new Promise(r => setTimeout(r, 3000))')  # 等 JS 渲染
                    cards = d.execute_js(CARD_JS).get('data', []) or []
                except Exception as e:
                    print(f'[bing-tmwd:{cat}] FAIL {e}', file=sys.stderr)
                    continue
                for c in cards:
                    c['url'] = unwrap_bing_url(c['url'])
                    records.append(_norm(c, cat, 'news', 'bing-tmwd', scraped_at))
                got += len(cards)
            print(f'[bing-tmwd:{cat}] {got} cards', file=sys.stderr)
    finally:
        if d is not None:
            try:
                d.close()
            except Exception:
                pass
    return records


# ─── urllib 直连通道 (R8 2026-06-20 新增) ──────────────────────
#
# 复用并整合 temp/_bing_urllib_fetch.py 经验 (2026-06-20 验证: 8 类目 60 条)。
# 关键: URL 仅传 q/qft/setmkt/setlang;不要 form=QBNT/sp/lq/pq/sc/cvid
#      (后者触发 Bing 切换到 JS 动态 SPA, SSR 卡片消失)。
def fetch_bing_urllib(categories: dict, scraped_at: datetime) -> list:
    """不依赖 Playwright 的 urllib 直连通道 (fast-path)。

    适用: 容器/headless 环境 Playwright 启动慢或挂起; CI 只装 stdlib;
          Playwright fetch 抛 TimeoutError/Exception 时由 run() 自动 fallback。
    URL 构造: 仅传 q + qft=interval="7" + setmkt=en-US + setlang=en;
              form/sp/lq/pq/sc/cvid 会触发 SPA, SSR 卡片消失。
    """
    import re as _re
    import html as _html
    _HDR = {
        'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'),
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    _CARD = _re.compile(
        r'<div[^>]*\bdata-url="(?P<url>[^"]+)"[^>]*\bdata-title="(?P<title>[^"]+)"'
        r'[^>]*\bdata-author="(?P<author>[^"]*)"[^>]*>(?P<rest>.*?)</div>\s*</div>',
        _re.S | _re.I)
    _REL = _re.compile(r'(\d+\s*(?:hour|day|min)s?\s*ago|\d+[hd]\s*ago)',
                       _re.I)
    _SNIP = _re.compile(r'<div[^>]*class="snippet"[^>]*>(.*?)</div>', _re.S | _re.I)
    _TAG = _re.compile(r'<[^>]+>')
    records = []
    for cat, conf in (categories or {}).items():
        if cat == 'rss':
            continue
        keywords = conf.get('keywords', []) or []
        if not keywords: continue
        q = ' OR '.join(f'"{k}"' for k in keywords)
        params = {'q': q, 'qft': 'interval="7"', 'setmkt': 'en-US', 'setlang': 'en'}
        url = 'https://www.bing.com/news/search?' + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url, headers=_HDR)
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw = resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            print(f'[bing-urllib:{cat}] FAIL {e}', file=sys.stderr)
            continue
        n = 0
        for m in _CARD.finditer(raw):
            href = m.group('url')
            if not href or 'bing.com/ck/' in href:
                href = unwrap_bing_url(href)
            title = _html.unescape(m.group('title')).strip()
            if not href or not title: continue
            rest = m.group('rest')
            author = m.group('author')
            sm = _re.search(r'<div[^>]*>([^<]+)</div>', rest)
            rel = _REL.search(rest)
            nm = _SNIP.search(rest)
            snippet = _html.unescape(_TAG.sub(' ', nm.group(1))).strip() if nm else ''
            rec = _norm({
                'title': title, 'url': href,
                'source': (author or (sm.group(1).strip() if sm else '')),
                'rel_time': rel.group(1) if rel else '',
                'snippet': snippet,
            }, cat, 'news', 'bing-urllib', scraped_at)
            if rec:
                records.append(rec); n += 1
        print(f'[bing-urllib:{cat}] {n} cards', file=sys.stderr)
    return records


# ─── RSS 通道 (stdlib, 无新依赖) ──────────────────────────────

def parse_rss(xml_bytes: bytes) -> list:
    """解析 RSS 2.0 / Atom -> [{title,url,source,rel_time}] (rel_time=发布日期文本)。"""
    out = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return out
    ns = {'a': 'http://www.w3.org/2005/Atom'}
    for it in root.iter():
        tag = it.tag.split('}')[-1]
        if tag not in ('item', 'entry'):
            continue
        title = link = pub = ''
        for ch in it:
            t = ch.tag.split('}')[-1]
            if t == 'title':
                title = (ch.text or '').strip()
            elif t == 'link':
                link = (ch.get('href') or ch.text or '').strip()
            elif t in ('pubDate', 'published', 'updated'):
                pub = (ch.text or '').strip()
        if link:
            out.append({'title': title, 'url': link, 'source': '', 'rel_time': pub})
    return out


def _rss_date_to_abs(pub: str):
    if not pub:
        return None
    try:
        return parsedate_to_datetime(pub).date().isoformat()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(pub.replace('Z', '+00:00')).date().isoformat()
    except ValueError:
        return None


def fetch_rss(feeds: list, category: str, tier: str, scraped_at: datetime, window_days: int = 7) -> list:
    records, lo = [], (scraped_at - timedelta(days=window_days)).date().isoformat()
    # R8 (2026-06-20): 补 UA/Accept/Referer 头; 部分智库源(CSIS/Critical Threats 等)对裸 urllib 403
    _rss_req = urllib.request.Request
    _UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Chrome/120 Safari/537.36')
    for feed in feeds:
        try:
            req = _rss_req(feed, headers={
                'User-Agent': _UA,
                'Accept': 'application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.google.com/',
            })
            with urllib.request.urlopen(req, timeout=RSS_TIMEOUT) as resp:
                items = parse_rss(resp.read())
        except urllib.error.HTTPError as e:             # R8: 403/401 仅 warn, 不计硬失败
            print(f'[rss:{category}] SKIP {feed} HTTP {e.code} (源对裸请求拒绝)', file=sys.stderr)
            continue
        except Exception as e:                          # fail-soft: 单 feed 失败不中断
            print(f'[rss:{category}] FAIL {feed} {e}', file=sys.stderr)
            continue
        kept = 0
        for it in items:
            abs_d = _rss_date_to_abs(it['rel_time'])
            if abs_d and abs_d < lo:                     # 越窗丢弃; 无日期保留待整编标注
                continue
            rec = _norm(it, category, tier, 'rss', scraped_at)
            rec['pub_date_abs'] = abs_d
            records.append(rec)
            kept += 1
        print(f'[rss:{category}] {kept}/{len(items)} <- {feed}', file=sys.stderr)
    return records


# ─── 归一化 / 编排 ───────────────────────────────────────────

def _norm(raw: dict, category: str, tier: str, channel: str, scraped_at: datetime) -> dict:
    return {
        'title': raw.get('title', ''),
        'url': raw.get('url', ''),
        'source': raw.get('source', ''),
        'pub_date_abs': rel_to_abs(raw.get('rel_time', ''), scraped_at),
        'pub_date':     rel_to_abs(raw.get('rel_time', ''), scraped_at) or scraped_at.date().isoformat(),
        'rel_time': raw.get('rel_time', ''),
        'snippet': raw.get('snippet', ''),
        'category': category,
        'tier': tier,
        'channel': channel,
    }


def load_sources(path: str = SOURCES_PATH) -> dict:
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _fetch_bing_dispatch(categories: dict, scraped_at: datetime,
                         engine: str = 'both') -> tuple[list, list]:
    """R15 双引擎调度: 返回 (records, channels_used)。

    engine ∈ {tmwebdriver, playwright, urllib, both}
      - tmwebdriver: 仅 TMWD; 失败抛错
      - playwright: 仅 Playwright; 失败回退 urllib
      - urllib: 直接 urllib (R8 fast-path)
      - both (默认): TMWD 优先 → 数据稀薄(<5)回退 Playwright → 仍失败回退 urllib
    """
    channels = []
    if engine == 'urllib':
        return fetch_bing_urllib(categories, scraped_at), ['urllib']
    if engine == 'tmwebdriver':
        return fetch_bing_tmwebdriver(categories, scraped_at), ['tmwebdriver']
    if engine == 'playwright':
        try:
            return fetch_bing(categories, scraped_at), ['playwright']
        except Exception as e:
            print(f'[bing:fallback] Playwright fetch 失败 ({e}); 切换 urllib 直连', file=sys.stderr)
            return fetch_bing_urllib(categories, scraped_at), ['playwright', 'urllib']
    # engine == 'both' (默认)
    try:
        recs = fetch_bing_tmwebdriver(categories, scraped_at)
        channels.append('tmwebdriver')
        if len(recs) >= 5:                                  # 数据足够就收手
            return recs, channels
        print(f'[bing:both] TMWD 数据稀薄 ({len(recs)} 张); 回退 Playwright', file=sys.stderr)
    except Exception as e:
        print(f'[bing:both] TMWD 失败 ({e}); 回退 Playwright', file=sys.stderr)
        recs = []
    try:
        recs = fetch_bing(categories, scraped_at)
        channels.append('playwright')
        return recs, channels
    except Exception as e:
        print(f'[bing:both] Playwright 失败 ({e}); 回退 urllib 直连', file=sys.stderr)
        return fetch_bing_urllib(categories, scraped_at), channels + ['urllib']


def run(date: str = None, out: str = None, min_records: int = MIN_RECORDS,
        sources_path: str = SOURCES_PATH, no_playwright: bool = False,
        engine: str = 'both', emit_template: str = None,
        no_google_news: bool = False) -> dict:
    scraped_at = datetime.now(BJT)
    if date:
        scraped_at = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=BJT, hour=18)
    out = out or os.path.join(_SCRIPT_DIR, '..', 'temp', f'bing_raw_{scraped_at:%Y%m%d}.json')
    src = load_sources(sources_path)

    # R8 (2026-06-20) 向后兼容: --no-playwright 隐含 engine='urllib'
    if no_playwright and engine == 'both':
        engine = 'urllib'

    records, bing_channels = _fetch_bing_dispatch(
        src.get('daily_news', {}), scraped_at, engine=engine)
    channels = list(bing_channels) + ['rss']
    # R16 (2026-06-27) Google News 通道: 走 Playwright, 默认启用; --no-google-news 跳过
    if not no_google_news and not no_playwright:
        try:
            gnews_records = fetch_google_news(src.get('daily_news', {}), scraped_at)
            records += gnews_records
            channels.append('google-news')
        except Exception as e:
            print(f'[gnews] channel fail-soft: {e}', file=sys.stderr)
    for cat, conf in src.get('daily_news', {}).items():
        records += fetch_rss(conf.get('rss', []), cat, 'news', scraped_at)
    records += fetch_rss(src.get('analysis', {}).get('think_tanks_rss', []),
                         'analysis', 'analysis', scraped_at)
    records = dedup_records(records)

    by_cat = {}
    for r in records:
        by_cat[r['category']] = by_cat.get(r['category'], 0) + 1
    payload = {'_meta': {'scraped_at': scraped_at.isoformat(), 'channels': channels,
                         'total': len(records), 'by_category': by_cat},
               'records': records}
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'TOTAL {len(records)} records -> {out}', file=sys.stderr)

    if len(records) < min_records:                       # 数据稀薄: 显式失败让 scheduler 捕获
        print(f'[WARN] total {len(records)} < min {min_records}: 数据稀薄, 触发 B 路手工兜底',
              file=sys.stderr)
        sys.exit(3)
    return payload


def main():
    ap = argparse.ArgumentParser(description='日报分层多源采集')
    ap.add_argument('--date', help='报告日期 YYYY-MM-DD (默认: 北京时间今天)')
    ap.add_argument('--out', help='输出路径 (默认: ../temp/bing_raw_<YYYYMMDD>.json)')
    ap.add_argument('--min', type=int, default=MIN_RECORDS, help=f'数据稀薄阈值 (默认 {MIN_RECORDS})')
    ap.add_argument('--no-playwright', action='store_true',
                    help='跳过 Chromium, 走 urllib 直连通道 (R8 fast-path, 隐含 --engine urllib)')
    ap.add_argument('--engine', choices=['tmwebdriver', 'playwright', 'urllib', 'both'],
                    default='both',
                    help='Bing 采集引擎 (R15 默认 both: TMWD 优先 → Playwright → urllib)')
    ap.add_argument('--no-google-news', dest='no_google_news', action='store_true',
                    help='跳过 Google News 通道 (R16 默认启用, 走 Playwright 抓 search?q=...)')
    ap.add_argument('--emit-template', metavar='PATH',
                    help='仅生成 report_data.json stub (B 路手工兜底起步), 不执行采集')
    args = ap.parse_args()
    if args.emit_template:
        emit_template(args.emit_template, args.date)
        return
    run(date=args.date, out=args.out, min_records=args.min,
        no_playwright=args.no_playwright, engine=args.engine,
        no_google_news=args.no_google_news)


def emit_template(out: str, date: str = None) -> None:
    """R8 (2026-06-20) B 路手工兜底起步: 生成含 date / window / 空白板块 / labels 的 stub。

    使用场景: fetch.py 数据稀薄 sys.exit(3) 后, LLM 据此模板填充, 再走 render+validate。
    字段对齐 Appendix D + render.is_*
    """
    scraped_at = datetime.now(BJT)
    if date:
        scraped_at = datetime.strptime(date, '%Y-%m-%d').replace(tzinfo=BJT, hour=18)
    stub = {
        "date": scraped_at.strftime("%Y-%m-%d"),
        "window": f"{(scraped_at - timedelta(days=7)).strftime('%Y-%m-%d')} ~ {scraped_at.strftime('%Y-%m-%d')}",
        "s1_overview": "",
        "s2_risk": [],
        "s3_hot": [],
        "s3_clues": [],
        "s4_trends": [],
        "s5_signals": [],
        "labels": {
            "project": "非传统安全领域动态日报",
            "version": "v1.8",
            "classification": "内部资料"
        }
    }
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(stub, f, ensure_ascii=False, indent=2)
    print(f'[template] stub written -> {out}', file=sys.stderr)


if __name__ == '__main__':
    main()


# ─── Google News 通道 (Playwright, R16 2026-06-27 新增) ─────────
#
# 覆盖 Bing 漏采的中长尾 / 学术 / 小语种; 默认启用, 走 Playwright (urllib 会被 403)。
# 失败/稀薄不影响 Bing 通道; 单 cat 失败 fail-soft。
# 输出 schema 与 Bing 一致, channel='google-news', dedup 走 url 字段。
# 注意: Google News 链接是其内部聚合跳转 (https://news.google.com/articles/CAI...),
#       原始媒体写在 source 字段, 整编阶段 LLM 据此二次搜索原始链接。

GNEWS_CARD_JS = r"""
() => {
  const seen = new Set(), out = [];
  // 2024+ 容器: article (优先) / c-wiz article / main article
  const articles = document.querySelectorAll(
    'article, c-wiz article, main article, div.UW0SDc article'
  );
  for (const a of articles) {
    // 标题链接: JtKRv/VDXfz (2024) 或 data-n-st + /articles/ href
    const aEl = a.querySelector(
      'a.JtKRv, a.VDXfz, a[data-n-st][href*="/articles/"], a[href*="/articles/"]'
    );
    if (!aEl) continue;
    const href = aEl.getAttribute('href') || '';
    if (!href || seen.has(href)) continue;
    // Google News 内部跳转是相对路径, 补前缀
    const url = href.startsWith('http') ? href : 'https://news.google.com' + href;
    seen.add(href);
    // 标题: aEl 内 h3 / h4
    const h3 = aEl.querySelector('h3, h4') || a.querySelector('h3, h4');
    const title = (h3 ? h3.textContent : aEl.textContent || '').trim().slice(0, 300);
    if (!title) continue;
    // 源媒体: div.vr1PYe / data-n-st 内子 div
    const srcEl = a.querySelector(
      'div.vr1PYe, div[data-n-st] > div, a[data-n-st] > div'
    );
    let source = srcEl ? (srcEl.textContent || '').trim() : '';
    // 时间: time[datetime] / UOVeFe / WW6dff / aria-label *ago
    const tEl = a.querySelector(
      'time, div.UOVeFe, div.WW6dff, div[aria-label*="ago" i], ' +
      'div[aria-label*="hours" i], div[aria-label*="days" i]'
    );
    let rel = tEl ? (
      tEl.getAttribute('datetime') ||
      tEl.getAttribute('aria-label') ||
      tEl.textContent || ''
    ).trim() : '';
    if (!rel) {
      const m = (a.textContent || '').match(
        /\d+\s*(?:h|d|w)\b|\d+\s*(?:minute|hour|day|week)s?\s+ago/i
      );
      rel = m ? m[0] : '';
    }
    // snippet: Y3v8qd / xBxb9 / GMF0Mc
    let snip = '';
    const snipEl = a.querySelector('div.Y3v8qd, div.xBxb9, div.GMF0Mc');
    if (snipEl) snip = (snipEl.textContent || '').trim();
    if (!snip) snip = (a.textContent || '').slice(0, 600);
    out.push({
      title, url,
      snippet: snip.slice(0, 600),
      source, rel_time: rel
    });
  }
  return out;
}
"""


def fetch_google_news(categories: dict, scraped_at: datetime,
                      limit_per_cat: int = 15) -> list:
    """R16 (2026-06-27) Google News 通道: 走 Playwright 抓搜索结果页。

    Args:
        categories: 同 fetch_bing, {cat: {keywords, ...}}
        scraped_at: 锚点 (用于 rel_time 换算)
        limit_per_cat: 每领域最多卡片数 (防单 cat 拉太多)

    Returns:
        records list, channel='google-news', 复用 _norm schema。
    """
    from playwright.sync_api import sync_playwright
    records = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel='chrome',
                                    args=['--no-sandbox',
                                          '--disable-blink-features=AutomationControlled'])
        ctx = browser.new_context(
            locale='en-US',
            user_agent=('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'),
        )
        page = ctx.new_page()
        for cat, conf in categories.items():
            keywords = conf.get('keywords', [])
            if not keywords:
                continue
            got = 0
            # Google News 单查询即可 (聚合度高), 不需要 site: 限定
            q = '+'.join(keywords)
            url = f'https://news.google.com/search?q={q}&hl=en-US&gl=US&ceid=US:en'
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=30000)
                # R16 经验: Google News JS 渲染较慢, 给 4s; 触发 "Show more" 不做
                page.wait_for_timeout(4000)
                cards = page.evaluate(GNEWS_CARD_JS) or []
            except Exception as e:
                print(f'[gnews:{cat}] FAIL {e}', file=sys.stderr)
                continue
            for c in cards[:limit_per_cat]:
                records.append(_norm(c, cat, 'news', 'google-news', scraped_at))
            got = min(len(cards), limit_per_cat)
            print(f'[gnews:{cat}] {got}/{len(cards)} cards', file=sys.stderr)
        browser.close()
    return records
