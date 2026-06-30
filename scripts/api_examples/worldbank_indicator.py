#!/usr/bin/env python3
"""
worldbank_indicator.py — World Bank Indicator API 最小示例
用法: python worldbank_indicator.py NY.GDP.MKTP.CD USA 2022
返回: 国家、指标、年份、数值 (JSON)
零依赖: 仅用 urllib + json
"""
import sys, json, urllib.request

BASE = 'https://api.worldbank.org/v2/country'
UA   = 'worldbank_examples/1.0'

def fetch(indicator: str, country: str, year: str) -> list:
    url = f'{BASE}/{country}/indicator/{indicator}?date={year}&format=json'
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    # data: [metadata, [{...}]]
    return data[1] if len(data) > 1 else []

def main():
    indicator = sys.argv[1] if len(sys.argv) > 1 else 'NY.GDP.MKTP.CD'
    country   = sys.argv[2] if len(sys.argv) > 2 else 'USA'
    year      = sys.argv[3] if len(sys.argv) > 3 else '2022'
    rows = fetch(indicator, country, year)
    if not rows:
        print('{}'); return
    row = rows[0]
    print(json.dumps({
        'indicator': indicator,
        'country': row.get('country', {}).get('value'),
        'countryiso3code': row.get('countryiso3code'),
        'year': row.get('date'),
        'value': row.get('value'),
        'unit': 'current US$' if indicator == 'NY.GDP.MKTP.CD' else 'see API docs',
    }, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
