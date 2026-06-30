"""Smoke test for memory/daily_report_fetch.py. 纯脚本式, 无 pytest, 无网络/playwright。
覆盖纯函数 unwrap_bing_url / rel_to_abs / dedup_records / build_bing_url / category_queries /
parse_rss, 以及 run() 编排 (monkeypatch fetch_bing/fetch_rss 注入离线 fixture)。"""
import base64, json, os, tempfile, urllib.parse
from datetime import datetime, timezone, timedelta

import memory.daily_report_fetch as f

_AT = datetime(2026, 6, 20, 18, 0, tzinfo=timezone(timedelta(hours=8)))


def _ck(real_url):
    b = base64.urlsafe_b64encode(real_url.encode()).decode().rstrip('=')
    return 'https://www.bing.com/ck/a?' + urllib.parse.urlencode({'u': 'a1' + b, 'p': 'x'})


def test_unwrap_bing_url():
    assert f.unwrap_bing_url(_ck('https://reuters.com/article/x')) == 'https://reuters.com/article/x'
    direct = 'https://apnews.com/y'
    assert f.unwrap_bing_url(direct) == direct                      # 非跳转链原样
    assert f.unwrap_bing_url('https://www.bing.com/ck/a?u=a1@@bad') .startswith('https://www.bing.com')  # 坏 base64 回退
    assert f.unwrap_bing_url('') == ''
    print('[SMOKE-OK] unwrap_bing_url')


def test_rel_to_abs():
    assert f.rel_to_abs('3 hours ago', _AT) == '2026-06-20'
    assert f.rel_to_abs('1 day ago', _AT) == '2026-06-19'
    assert f.rel_to_abs('2 days ago', _AT) == '2026-06-18'
    assert f.rel_to_abs('1 week ago', _AT) == '2026-06-13'
    assert f.rel_to_abs('Jun 19, 2026', _AT) == '2026-06-19'
    # Bing 短形式 (aria-label fallback): "7h" "3d" "2w"
    assert f.rel_to_abs('7h', _AT) == '2026-06-20'
    assert f.rel_to_abs('3d', _AT) == '2026-06-17'
    assert f.rel_to_abs('2w', _AT) == '2026-06-06'
    assert f.rel_to_abs('', _AT) is None
    assert f.rel_to_abs('昨天', _AT) is None                         # 不可解析返回 None, 不臆造
    print('[SMOKE-OK] rel_to_abs')


def test_dedup_records():
    recs = [{'url': 'https://a.com/1'}, {'url': 'https://a.com/1/'}, {'url': 'https://b.com'}, {'url': ''}]
    out = f.dedup_records(recs)
    assert len(out) == 2, out                                       # 尾斜杠等价合并 + 空 URL 丢弃
    print('[SMOKE-OK] dedup_records')


def test_build_bing_url_and_queries():
    # 多关键词 → OR 逻辑
    url = f.build_bing_url(['rare earth', 'critical minerals'], ['usgs.gov', 'iea.org', 'a.org', 'b.org', 'c.org'])
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)['q'][0]
    assert '"rare earth" OR "critical minerals"' in q, q             # OR 语法
    assert 'site:usgs.gov' in q and 'site:c.org' not in q, q        # 仅取前 SITES_PER_QUERY=4
    assert 'setmkt=en-US' in url and 'interval' in url, url
    # 单关键词 → 直接使用, 无引号
    url2 = f.build_bing_url(['oil gas OPEC'], [])
    q2 = urllib.parse.parse_qs(urllib.parse.urlparse(url2).query)['q'][0]
    assert q2 == 'oil gas OPEC', q2
    qs = f.category_queries({'keywords': ['x'], 'bing_sites': ['s1.gov']})
    assert len(qs) == 2, qs                                          # 受限 + 不限域兜底
    qs2 = f.category_queries({'keywords': ['x'], 'bing_sites': []})
    assert len(qs2) == 1, qs2                                        # 无域仅兜底
    print('[SMOKE-OK] build_bing_url / category_queries')


def test_parse_rss():
    rss = b'''<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>A</title><link>https://x.com/a</link><pubDate>Fri, 19 Jun 2026 10:00:00 GMT</pubDate></item>
      <item><title>B</title><link>https://x.com/b</link></item></channel></rss>'''
    items = f.parse_rss(rss)
    assert len(items) == 2 and items[0]['url'] == 'https://x.com/a', items
    atom = b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>C</title><link href="https://y.com/c"/><updated>2026-06-18T08:00:00Z</updated></entry></feed>'''
    aitems = f.parse_rss(atom)
    assert aitems[0]['url'] == 'https://y.com/c', aitems
    assert f.parse_rss(b'not xml') == []                            # 坏 XML 容错
    print('[SMOKE-OK] parse_rss')


def test_run_orchestration():
    # monkeypatch 两个通道, 注入离线 records, 验证 _meta/去重/输出 schema
    f.fetch_bing = lambda cats, at: [
        {'url': 'https://a.com/1', 'category': 'energy', 'tier': 'news', 'channel': 'bing'},
        {'url': 'https://a.com/1', 'category': 'energy', 'tier': 'news', 'channel': 'bing'},  # 重复
    ]
    f.fetch_rss = lambda feeds, cat, tier, at, **k: (
        [{'url': 'https://b.com', 'category': cat, 'tier': tier, 'channel': 'rss'}] if feeds else [])
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, 'src.json')
        json.dump({'daily_news': {'energy': {'keywords': ['oil'], 'bing_sites': [], 'rss': ['http://feed']}},
                   'analysis': {'think_tanks_rss': []}}, open(src, 'w'))
        out = os.path.join(d, 'raw.json')
        payload = f.run(date='2026-06-20', out=out, min_records=1, sources_path=src)
        assert payload['_meta']['total'] == 2, payload['_meta']     # a.com 去重后 + b.com
        assert os.path.exists(out)
        disk = json.load(open(out, encoding='utf-8'))
        assert disk['_meta']['scraped_at'].startswith('2026-06-20'), disk['_meta']
        assert disk['_meta']['by_category']['energy'] == 2, disk['_meta']
    print('[SMOKE-OK] run_orchestration')


def test_run_thin_data_exits():
    # 数据稀薄 -> exit 3
    f.fetch_bing = lambda cats, at: []
    f.fetch_rss = lambda feeds, cat, tier, at, **k: []
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, 'src.json')
        json.dump({'daily_news': {}, 'analysis': {'think_tanks_rss': []}}, open(src, 'w'))
        try:
            f.run(date='2026-06-20', out=os.path.join(d, 'o.json'), min_records=5, sources_path=src)
            assert False, 'should sys.exit(3)'
        except SystemExit as e:
            assert e.code == 3, e.code
    print('[SMOKE-OK] run_thin_data_exits')


if __name__ == '__main__':
    test_unwrap_bing_url()
    test_rel_to_abs()
    test_dedup_records()
    test_build_bing_url_and_queries()
    test_parse_rss()
    test_run_orchestration()
    test_run_thin_data_exits()
    print('\nALL SMOKE PASS')
