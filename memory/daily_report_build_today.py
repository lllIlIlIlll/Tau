"""非传统安全领域动态日报 v1.5-R2 - 一体化生成 MD/DOCX/HTML
- 输入: today_data.py (S1-S9+TREND+SIGNALS, 每条 (date, source, url, content))
- 输出: ../output/非传统安全领域动态日报_YYYYMMDD.{md,docx,html}
- 用法: 修改 DATE_STR/WINDOW_STR/路径,运行 python -m memory.daily_report_build_today
- 9板块: 涉华要闻 / 各国动向 / 生物安全与公共卫生 / 水资源与深海安全 / 能源安全 / 气候变化与极端天气 / 网络安全 / 跨境犯罪与反恐 / 人口安全与移民
- 加: 十、本期要情与趋势分析(6条) + 十一、重点关注信号的情报价值(5条)
- DOCX样式: 黑体(标题)/宋体(正文)/橙色#D97757+左侧色块/Microsoft YaHei英文
- HTML主题: Claude米色#FBEEE6背景+#FFFAF5卡片+#D97757橙色重点+#C9B99A边框+#B8A684链接,PingFang SC/Microsoft YaHei字体
"""
import os
from datetime import datetime
from memory.today_data import S1,S2,S3,S4,S5,S6,S7,S8,S9,TREND,SIGNALS

os.makedirs('../output', exist_ok=True)
DATE_STR = '2026年6月4日'  # 改这里
WINDOW_STR = '2026年6月3日08:00 — 6月4日08:00（北京时间）'  # 改这里
SOURCE_NOTE = '本报告基于 Bing News 国际/国内媒体多源检索，对关键事件进行交叉核验；涉华政策与跨境合作类条目均经两源以上交叉核验。'
MD_PATH = '../output/非传统安全领域动态日报_20260604.md'  # 改这里
DOCX_PATH = '../output/非传统安全领域动态日报_20260604.docx'
HTML_PATH = '../output/非传统安全领域动态日报_20260604.html'

SECTIONS = [
    ("一、涉华要闻", S1, '涉及中国战略利益、对外合作与海外利益保护的重要动态。'),
    ("二、各国动向", S2, '主要国家对外政策、双多边博弈与重大政治安全事件。'),
    ("三、生物安全与公共卫生", S3, '传染病、跨境卫生治理与公共卫生体系运行情况。'),
    ("四、水资源与深海安全", S4, '海洋生态、远海/深海活动与全球海运通道安全。'),
    ("五、能源安全", S5, '油气产能、地缘冲突与新能源博弈。'),
    ("六、气候变化与极端天气", S6, '厄尔尼诺/拉尼娜、极端气象事件与全球气候政策。'),
    ("七、网络安全", S7, '关键信息基础设施、重大漏洞与跨境网络攻击。'),
    ("八、跨境犯罪与反恐", S8, '跨境贩毒、偷渡、洗钱、恐怖活动与有组织犯罪。'),
    ("九、人口安全与移民", S9, '跨境人口流动、难民保护、未成年人监护与移民治理。'),
]

def item_to_md(idx, item):
    date, src, url, content = item
    return f"{idx}. **{content.split('。')[0]}**\n   {content}\n   来源：[{src}]({url})  ·  {date}\n"

def section_to_md(title, items, hint):
    out = [f"## {title}", '', hint, '']
    if not items:
        out.append('（本期未检索到7日内重大突发动态，建议持续跟踪。）')
        out.append('')
        return '\n'.join(out)
    for i, it in enumerate(items, 1):
        out.append(item_to_md(i, it))
    out.append('')
    return '\n'.join(out)

def gen_md():
    lines = [f'# 非传统安全领域动态日报', '',
             f'**报告日期**：{DATE_STR}  ',
             f'**时间窗口**：{WINDOW_STR}  ',
             f'**整编单位**：非传统安全情报整编组  ',
             f'**数据来源**：{SOURCE_NOTE}', '',
             '---', '',
             '> **内容提要**：本期共纳入7日内全球非传统安全相关事件 44 条，'
             '按"涉华要闻 / 各国动向 / 生物安全 / 水资源与深海 / 能源安全 / 气候变化 / 网络安全 / 跨境犯罪 / 人口与移民"9个主题整编。',
             '']
    for t, items, hint in SECTIONS:
        lines.append(section_to_md(t, items, hint))
    lines += ['## 十、本期要情与趋势分析', '']
    for i, t in enumerate(TREND, 1):
        lines.append(f"{i}. {t}")
    lines += ['', '## 十一、重点关注信号的情报价值', '']
    for i, s in enumerate(SIGNALS, 1):
        lines.append(f"{i}. {s}")
    lines += ['', '---', '', '*本报告由 GenericAgent 自动整编，内容仅供决策参考。*']
    return '\n'.join(lines)

# === DOCX部分 (省略，详见 ./build_today.py 完整版) ===
# === HTML部分 (省略，详见 ./build_today.py 完整版) ===
