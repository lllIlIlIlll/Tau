# 日报参考源清单（reference 层 · 非每日爬虫）

> 这些源**不进每日自动采集**（`daily_report_fetch.py` 不抓）。它们是**按需核对工具**：整编日报时，按领域来这里查具体数字、做深挖（如核对 FAO 粮价指数、IAEA 反应堆数据）。
> 两类：**数据/统计平台**（数据库、数据浏览器、注册库——无每日新闻流）+ **智库**（有 RSS 的可填入 `daily_report_sources.json` 的 `analysis.think_tanks_rss` 转为低频分析源；feed 地址需逐源核实，勿臆造）。
> 高价值定期发布（FAO 月度粮价指数、USDA WASDE、IEA 月报）本身是新闻，由 daily_news 的 Bing site: 通道覆盖，无需直爬。

## 一、稀土矿产 · 数据/信息系统
- 欧盟原材料信息系统 RMIS — https://rmis.jrc.ec.europa.eu/
- 国际能源署 关键矿产数据浏览器 — https://www.iea.org/data-and-statistics/data-tools/critical-minerals-data-explorer
- 世界银行 气候智能型采矿倡议 — https://www.worldbank.org/en/programs/climate-smart-mining
- 中国有色金属标准质量信息网 — http://www.cnsmq.com/

## 二、生物医药 · 数据库/注册库
- 美国临床试验注册数据库 ClinicalTrials.gov — https://clinicaltrials.gov/
- PubMed 美国医学文献数据库 — https://pubmed.ncbi.nlm.nih.gov/
- 美国国家生物技术信息中心 NCBI — https://www.ncbi.nlm.nih.gov/
- 美国国家医学图书馆 — https://www.nlm.nih.gov/
- WHO 全球卫生观察站 GHO — https://www.who.int/data/gho
- 欧盟官方临床试验信息平台 — https://euclinicaltrials.eu/
- 欧盟临床试验注册库 — https://www.clinicaltrialsregister.eu/
- EudraCT 欧盟临床试验数据库 — https://eudract.ema.europa.eu/
- 欧盟药物警戒系统 EudraVigilance — https://www.ema.europa.eu/en/human-regulatory-overview/research-development/pharmacovigilance-research-development/eudravigilance
- 欧洲疑似药品不良反应报告数据库 — https://www.adrreports.eu/
- WHO 医疗产品预认证 — https://extranet.who.int/prequal/
- WHO 疫苗预认证平台 — https://extranet.who.int/prequal/vaccines
- 美国 NIH 科研项目数据库 RePORTER — https://reporter.nih.gov/
- 加拿大药品数据库 — https://health-products.canada.ca/dpd-bdpp/index-eng.jsp

## 三、粮食农业 · 数据/监测平台
- 粮农组织统计数据库 FAOSTAT — https://www.fao.org/faostat/en/
- 农业市场信息系统 AMIS — https://www.amis-outlook.org/
- 全球农业监测组织作物监测系统 — https://www.cropmonitor.org/
- 全球农业监测组织 GEOGLAM — https://geoglam.org/
- USDA 海外农业局数据与分析平台 — https://apps.fas.usda.gov/psdonline/app/index.html
- FAO 食品价格指数 — https://www.fao.org/worldfoodsituation/foodpricesindex/en/
- FAO 全球信息与预警系统 GIEWS — https://www.fao.org/giews/en/
- AGRI4CAST 农业预测与监测 — https://agri4cast.jrc.ec.europa.eu/
- 东盟粮食安全信息系统 — https://www.aptfsis.org/
- 美国农业部 WASDE 报告 — https://www.usda.gov/oce/commodity/wasde
- 经合组织—粮农组织农业展望 — https://www.oecd.org/en/publications/oecd-fao-agricultural-outlook_19991142.html

## 四、气候 · 数据/监测平台
- 美国国家环境信息中心 NCEI — https://www.ncei.noaa.gov/
- NASA 地球观测数据 EarthData — https://www.earthdata.nasa.gov/
- 哥白尼气候数据存储 CDS — https://cds.climate.copernicus.eu/
- 欧盟 EDGAR 全球大气排放数据库 — https://edgar.jrc.ec.europa.eu/
- 全球监测实验室 GML — https://gml.noaa.gov/
- WMO 全球温室气体监测 G3W — https://wmo.int/activities/global-greenhouse-gas-watch-g3w
- UNFCCC 国家自主贡献注册平台 NDC — https://unfccc.int/NDCREG
- UNEP 排放差距报告 — https://www.unep.org/resources/emissions-gap-report
- 哥白尼大气监测服务 CAMS — https://atmosphere.copernicus.eu/

## 五、跨界水资源 · 数据平台
- 粮农组织全球水与农业信息系统 AQUASTAT — https://www.fao.org/aquastat/en/
- 国际地下水资源评估中心 IGRAC — https://www.un-igrac.org/

## 六、深海、极地、太空 · 数据平台
- NASA EarthData 门户 — https://www.earthdata.nasa.gov/
- 全球海洋测深图 GEBCO — https://www.gebco.net/
- 海洋生物多样性信息系统 OBIS — https://obis.org/
- 全球海洋观测系统 GOOS — https://goosocean.org/
- Argo 全球海洋浮标 — https://argo.ucsd.edu/
- 美国 Space-Track 空间目标数据平台 — https://www.space-track.org/

## 七、人口问题 · 数据平台
- 世界银行开放数据（人口） — https://data.worldbank.org/indicator/SP.POP.TOTL
- WorldPop 开放空间人口数据 — https://www.worldpop.org/
- UNFPA 人口数据门户 — https://pdp.unfpa.org/
- 国际劳工组织劳工统计 ILOSTAT — https://ilostat.ilo.org/

## 八、资源能源 · 数据平台
- JODI 油气数据 — https://www.jodidata.org/
- IEF 石油和天然气数据回顾 — https://www.ief.org/data/oil-gas-data-review
- IAEA 核电反应堆数据库 PRIS — https://pris.iaea.org/PRIS/home.aspx
- 全球太阳能地图集 — https://globalsolaratlas.info/
- 全球风能地图集 — https://globalwindatlas.info/
- APEC 能源数据库 — https://www.egeda.ewg.apec.org/
- IEA 光伏技术合作 — https://iea-pvps.org/
- IEA 风能技术合作 — https://iea-wind.org/
- IEA 氢能技术合作 — https://www.ieahydrogen.org/
- IEA 生物质能技术合作 — https://www.ieabioenergy.com/
- 全球生物能源伙伴关系 GBEP — https://www.globalbioenergy.org/

## 九、智库 / 长期浏览（候选 analysis 源 · 有 RSS 可转低频分析）
> 逐源核实 RSS feed 后，填入 `daily_report_sources.json` 的 `analysis.think_tanks_rss`，即转为低频分析源喂 S4/S5。无 RSS 者保留为按需深读。
- 美国战略与国际问题研究中心 CSIS — https://www.csis.org/
- 美国布鲁金斯学会 — https://www.brookings.edu/
- 美国卡内基国际和平基金会 — https://carnegieendowment.org/
- 美国兰德公司 — https://www.rand.org/
- 美国大西洋理事会 — https://www.atlanticcouncil.org/
- 美国新美国安全中心 CNAS — https://www.cnas.org/
- 威尔逊中心 — https://www.wilsoncenter.org/
- 欧洲对外关系委员会 ECFR — https://ecfr.eu/
- 查塔姆研究所 — https://www.chathamhouse.org/
- 国际战略研究所 IISS — https://www.iiss.org/
- 澳大利亚战略政策研究所 ASPI — https://www.aspi.org.au/
- 日本国际问题研究所 JIIA — https://www.jiia.or.jp/en/
- 印度观察家研究基金会 ORF — https://www.orfonline.org/
- 尤索夫伊萨东南亚研究院 ISEAS — https://www.iseas.edu.sg/
- 世界经济论坛 — https://www.weforum.org/

## 综合数据/机构（跨领域按需）
- 世界银行 — https://www.worldbank.org/
- 国际货币基金组织 IMF — https://www.imf.org/
- 经济合作与发展组织 OECD — https://www.oecd.org/
- 联合国数据服务平台 — https://data.un.org/
- 能源基金会 — https://www.efchina.org/
- 全球能源监测 — https://globalenergymonitor.org/
- Our World in Data — https://ourworldindata.org/
