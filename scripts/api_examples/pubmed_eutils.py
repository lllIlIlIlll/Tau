#!/usr/bin/env python3
"""
pubmed_eutils.py — PubMed E-utilities 零依赖最小封装
测试日期: 2026-06-24 R6
用法:
  python pubmed_eutils.py search "machine learning" 2024     # esearch → PMID list
  python pubmed_eutils.py fetch 32483381                      # efetch → abstract text
  python pubmed_eutils.py summary 32483381                    # esummary → JSON metadata
零依赖: 仅用 urllib + json (Python stdlib)
"""
import sys, json, urllib.request, urllib.parse, time

BASE = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'
UA   = 'pubmed_eutils/1.0 (research; mailto:tau@example.com)'  # 建议加 mailto 字段
TIMEOUT = 15

def http_get(url: str) -> bytes:
    """GET 请求, 带 UA + 重试 1 次"""
    last = None
    for i in range(2):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(0.5)
    raise last

def esearch(term: str, retmax: int = 5) -> list:
    """esearch: 关键词 → PMID 列表"""
    q = urllib.parse.quote(term)
    url = f'{BASE}/esearch.fcgi?db=pubmed&term={q}&retmax={retmax}&retmode=json'
    data = json.loads(http_get(url))
    return data.get('esearchresult', {}).get('idlist', [])

def efetch(pmid: str) -> str:
    """efetch: PMID → abstract 全文"""
    url = f'{BASE}/efetch.fcgi?db=pubmed&id={pmid}&retmode=text&rettype=abstract'
    return http_get(url).decode('utf-8', errors='ignore')

def esummary(pmid: str) -> dict:
    """esummary: PMID → JSON 元数据 (Title/Authors/Year/Journal)"""
    url = f'{BASE}/esummary.fcgi?db=pubmed&id={pmid}&retmode=json'
    return json.loads(http_get(url))

def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'search':
        if len(sys.argv) < 3:
            print('用法: search <term> [year]'); sys.exit(1)
        term = sys.argv[2]
        if len(sys.argv) >= 4:
            term += f' AND {sys.argv[3]}[dp]'
        ids = esearch(term)
        print(f'找到 {len(ids)} 个 PMID: {ids}')
    elif cmd == 'fetch':
        pmid = sys.argv[2]
        print(efetch(pmid))
    elif cmd == 'summary':
        pmid = sys.argv[2]
        print(json.dumps(esummary(pmid), ensure_ascii=False, indent=2)[:1500])
    else:
        print(f'未知命令: {cmd}'); sys.exit(1)

if __name__ == '__main__':
    main()
