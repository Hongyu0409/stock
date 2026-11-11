"""Curated company industry and business descriptions for US Stock symbols."""

from __future__ import annotations

from typing import Dict

COMPANY_PROFILES: Dict[str, str] = {
    # 科技與半導體 (XLK)
    "NVDA": "輝達，全球 AI 算力加速晶片與 GPU 霸主",
    "AAPL": "蘋果，iPhone、Mac 與全球消費電子生態龍頭",
    "MSFT": "微軟，Windows、Office 與 Azure 雲端/AI 巨頭",
    "AVGO": "博通，全球通訊網路與客製化 AI ASIC 晶片大廠",
    "AMD": "超微半導體，全球 CPU、GPU 與資料中心 AI 處理器大廠",
    "TSM": "台積電，全球最大先進製程半導體晶圓代工龍頭",
    "MU": "美光科技，全球高頻寬記憶體 (HBM) 與記憶體晶片大廠",
    "ASML": "艾司摩爾，全球獨家 EUV 極紫外光晶圓微影設備霸主",
    "QCOM": "高通，全球智慧型手機晶片與 5G 通訊專利巨頭",
    "ARM": "安謀，全球行動裝置架構設計與晶片 IP 授權霸主",
    "MRVL": "邁威爾，資料中心高速光通訊與客製化 AI 晶片大廠",
    "SMCI": "美超微，高階 AI 伺服器與液冷散熱機櫃系統整合廠",
    "CRM": "Salesforce，全球客戶關係管理 (CRM) 雲端平台龍頭",
    "ORCL": "甲骨文，全球關聯式資料庫與企業雲端基礎設施大廠",
    "ADBE": "Adobe，全球數位創意軟體 (Photoshop) 與多媒體龍頭",
    "NOW": "ServiceNow，企業數位工作流程與 IT 服務管理軟體龍頭",
    "PLTR": "Palantir，大數據國防情報與企業級 AI 決策分析平台",
    "PANW": "Palo Alto Networks，全球次世代網路防火牆與雲端資安巨頭",
    "CRWD": "CrowdStrike，全球雲端端點資安與威脅防禦軟體龍頭",
    "SNOW": "Snowflake，企業雲端資料倉儲與數據共享分析平台",
    "ANET": "Arista Networks，AI 資料中心高速乙太網路交換器龍頭",
    "DELL": "戴爾，全球個人電腦與企業 AI 伺服器硬體大廠",
    # 通訊與網路平台 (XLC)
    "META": "Meta，Facebook、Instagram、WhatsApp 社群平台與 AI 龍頭",
    "GOOGL": "Alphabet，Google 搜尋引擎、YouTube 與雲端/AI 巨頭",
    "NFLX": "網飛 (Netflix)，全球串流影音訂閱平台霸主",
    "DIS": "迪士尼，全球主題樂園、電影 IP 版權與娛樂王國",
    "SPOT": "Spotify，全球最大音樂與 Podcast 串流訂閱平台",
    "TMUS": "T-Mobile，美國大型 5G 無線電信通訊服務商",
    "RDDT": "Reddit，美國最大論壇社群平台與 AI 訓練語料供應商",
    # 非必需消費與電動車/電商 (XLY)
    "AMZN": "亞馬遜，全球最大雲端運算 (AWS) 與電子商務巨頭",
    "TSLA": "特斯拉，全球電動車、自動駕駛 (FSD) 與儲能科技先驅",
    "COST": "好市多，全球會員制大型連鎖量販批發龍頭",
    "HD": "家得寶 (Home Depot)，美國最大居家修繕與建材零售連鎖商",
    "MCD": "麥當勞，全球最大連鎖速食餐飲龍頭",
    "NKE": "耐吉 (Nike)，全球最大運動鞋、服飾與體育用品品牌",
    "SBUX": "星巴克，全球最大精品連鎖咖啡烘焙與零售品牌",
    "BKNG": "Booking Holdings，全球最大線上旅遊與飯店訂房平台",
    "UBER": "優步，全球網約叫車、外送 (Uber Eats) 與貨運平台",
    "ABNB": "Airbnb，全球民宿與特色短租旅遊住宿預訂平台",
    "MELI": "MercadoLibre，拉丁美洲最大電子商務與數位金融平台",
    # 金融與支付 (XLF)
    "JPM": "摩根大通，全美資產規模最大的跨國綜合型第一大銀行",
    "GS": "高盛，華爾街頂級投資銀行與機構證券交易巨頭",
    "MS": "摩根士丹利，全球頂尖財富管理與大型投資銀行",
    "BAC": "美國銀行，全美第二大資產規模零售與商業銀行",
    "V": "Visa，全球最大信用卡與跨國數位支付結算網絡",
    "MA": "Mastercard，全球第二大信用卡與跨國數位支付網絡",
    "AXP": "美國運通，全球高端消費信用卡與商務支付服務商",
    "BRK-B": "波克夏，巴菲特掌舵的多元保險、鐵路與能源控股集團",
    "BLK": "貝萊德，全球最大資產管理機構 (iShares ETF 發行商)",
    "COIN": "Coinbase，美國最大合規加密貨幣與數位資產交易所",
    "HOOD": "Robinhood，美國年輕世代主流免佣金股票與加密交易券商",
    # 醫療與生技 (XLV)
    "LLY": "禮來製藥，全球減肥藥 (GLP-1) 與糖尿病/阿茲海默藥物龍頭",
    "UNH": "聯合健康，全美最大健康醫療保險與醫療照護服務巨頭",
    "NVO": "諾和諾德，全球胰島素與瘦瘦針減肥藥龍頭",
    "JNJ": "嬌生，百年跨國生技製藥與醫療器材大廠",
    "ABBV": "艾伯維，全球自體免疫疾病藥物與生技製藥巨頭",
    "MRK": "默沙東，全球腫瘤免疫療法 (Keytruda) 與生技製藥巨頭",
    "ISRG": "直覺手術，達文西機器人微創手術系統全球霸主",
    "AMGN": "安進，全球生技製藥先驅，聚焦癌症與心血管療法",
    "VRTX": "福泰製藥，囊狀纖維化罕見疾病基因療法龍頭",
    # 工業、航太與電力基建 (XLI)
    "CAT": "開拓重工 (Caterpillar)，全球最大工程建築與採礦重型機械商",
    "GE": "奇異航太 (GE Aerospace)，全球商用與軍用飛機噴射發動機霸主",
    "VRT": "維諦 (Vertiv)，全球資料中心電源管理與液冷散熱系統領導者",
    "ETN": "伊頓 (Eaton)，全球電力管理、配電設備與電網基建巨頭",
    "RTX": "雷神技術，全球國防飛彈雷達與航太防衛系統巨頭",
    "BA": "波音，全球大型民航客機與軍用航太製造大廠",
    "LMT": "洛克希德·馬丁，全球最大軍火承包商 (F-35 戰鬥機製造商)",
    "UNP": "聯合太平洋，美國最大橫貫西部的跨國一級貨運鐵路公司",
    "DE": "強鹿 (John Deere)，全球最大智慧農業機械與曳引機製造商",
    # 能源 (XLE)
    "XOM": "埃克森美孚，美國最大跨國石油、天然氣與石化能源巨頭",
    "CVX": "雪佛龍，全美第二大綜合型能源與石油勘探跨國巨頭",
    "COP": "康菲石油，全球最大獨立石油與天然氣勘探生產商",
    "SLB": "斯倫貝謝，全球最大油田工程技術與鑽井服務商",
    # 公用事業 (XLU)
    "NEE": "新紀元能源，全美最大綠能風電/太陽能與公用電力事業",
    "CEG": "星座能源 (Constellation)，全美最大核電營運商 (AI 資料中心電廠)",
    "VST": "Vistra，德州最大獨立發電商與核能/天然氣 AI 電網供應商",
    # 必需消費 (XLP)
    "WMT": "沃爾瑪，全球營業額最高的跨國超級市場零售霸主",
    "PG": "寶僑 (P&G)，全球最大日用消費品巨頭 (幫寶適、海倫仙度絲)",
    "KO": "可口可樂，全球最大無酒精飲料與軟性汽水品牌",
    "PEP": "百事公司，全球知名飲料與休閒零食食品巨頭 (樂事、百事)",
    # 原物料 (XLB)
    "LIN": "林德，全球最大工業氣體與醫療氣體供應商",
    "FCX": "自由港麥克墨倫，全球最大銅礦開採商 (受惠電網AI電力擴建)",
    "NEM": "紐蒙特礦業，全球最大黃金開採與貴金屬礦業公司",
}


def get_company_profile(symbol: str, sector_name: str = "") -> str:
    """Return a concise 1-sentence Chinese business description for a symbol."""
    if symbol in COMPANY_PROFILES:
        return COMPANY_PROFILES[symbol]
    if sector_name:
        return f"{symbol}（{sector_name}產業代表企業）"
    return f"{symbol} 美股上市公司"
