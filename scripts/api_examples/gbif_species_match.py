#!/usr/bin/env python3
"""
gbif_species_match.py — GBIF Species Match API 最小示例
用法: python gbif_species_match.py "Panthera leo"
返回: 学名、canonicalName、rank、匹配状态 (JSON)
零依赖: 仅用 urllib + json
"""
import sys, json, urllib.request, urllib.parse

BASE = 'https://api.gbif.org/v1/species/match'
UA   = 'gbif_examples/1.0'

def match(name: str) -> dict:
    url = f'{BASE}?name={urllib.parse.quote(name)}'
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def main():
    name = sys.argv[1] if len(sys.argv) > 1 else 'Panthera leo'
    data = match(name)
    print(json.dumps({
        'query': name,
        'usageKey': data.get('usageKey'),
        'scientificName': data.get('scientificName'),
        'canonicalName': data.get('canonicalName'),
        'rank': data.get('rank'),
        'matchType': data.get('matchType'),
        'status': data.get('status'),
    }, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
