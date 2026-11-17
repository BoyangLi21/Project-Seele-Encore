"""Naming rules for signs (R64): Japanese first, then Chinese, then English, one name per place.

Used by plan_sign_texts.py. Shop and house names on street signs are Japanese only (Hakone, Odawara and the outer
ring are in Japan); NERV room plates and wayfinding carry three languages.
"""

# Chinese (or Chinese-spelt) shop and facility names on street signs -> Japanese as used in Japan.
SHOP_JA = {
    '街角书店': 'まちかど書店', '街角商店': 'かどや商店', '日用品商店': '日用品店', '温泉旅馆': '温泉旅館',
    '生活杂货': '生活雑貨', '街角喫茶': '喫茶 まちかど', '町内事务所': '町内会事務所', '土产': '土産物',
    '湖畔商店': '湖畔の店', '沿街食堂': '街道食堂', '街角食堂': 'まちかど食堂', '小商铺': 'よろず屋',
    '土产商店': '土産物店', '土产店': '土産物店', '社区诊所': '地域診療所', '旅行书店': '旅行書店',
    '站前喫茶': '駅前喫茶', '登山缆车': '登山ケーブルカー', '温泉案内': '温泉案内', '名产': '名物',
    '湖畔餐厅': '湖畔レストラン', '湖畔茶屋': '湖畔茶屋', '箱根索道': '箱根ロープウェイ', '芦之湖游船': '芦ノ湖遊覧船',
    '芦之湖 · 桃源台港': '芦ノ湖 桃源台港', '桃源台站': '桃源台駅', '桃源台 公交': '桃源台 バスのりば',
    '强罗站 公交': '強羅駅 バスのりば', '早云山': '早雲山', '姥子 · 票务': '姥子 きっぷ売り場', '大涌谷 · 票务': '大涌谷 きっぷ売り場',
    '早云山 · 换乘票务': '早雲山 乗換きっぷ売り場', '强罗 · 乘车服务': '強羅 乗車案内', '强罗接驳线': '強羅連絡線',
    '新箱根机场 · 管制塔': '新箱根飛行場 管制塔', '箱根湾机场 · 管制塔': '箱根湾空港 管制塔',
    '北町公民会馆': '北町公民館', '北町诊所': '北町診療所', '团地诊疗所': '団地診療所', '団地診疗所': '団地診療所',
    '学校体育馆': '学校体育館', '第三新东京市立': '第3新東京市立', '社区商住': '商店併用住宅',
    '航空维修库': '航空整備庫', '整备补给中心': '整備補給センター', 'NERV 总部': 'NERV 本部',
    '西町生活店': '西町生活店', '霧里食料品店': '霧里食料品店',
    # other lines on street signs
    '工作人员入口': '関係者入口', '货运 · 检修': '貨物・整備', '禁止穿越滑行道': '誘導路横断禁止',
    '业务入口 / ENTRY': '業務用入口 / ENTRY', '航空管制 · 人员通行': '航空管制 関係者通路', '请保持入口净空': '入口前 駐停車禁止',
    '泳池・操场：北侧': 'プール・校庭：北側', '事务所': '事務所', '票务服务': 'きっぷ売り場', '候船大厅 / B2F': '乗船待合室 / B2F',
    '教学楼：左侧': '校舎：左側', '请沿校园通路进入': '入口は校内通路から', '教学楼・保健室': '校舎・保健室',
    '贯通线 · 雾里线': '貫通線・霧里線', '沿街向东约150格': '東へ約600m', '贯通线2楼': '貫通線 2階', '雾里线1楼': '霧里線 1階',
    'S2 駅前': '新箱根中央 駅前',  # no S2 line exists; both signs stand 63 blocks south of 新箱根中央 station
    '強羅接驳线': '強羅連絡線', '强罗接驳线': '強羅連絡線', '土产': '土産', '黑鸡蛋': '黒たまご', '登山电车': '登山電車',
    '公交': 'バス', '餐厅': 'レストラン', '便利店': 'コンビニ', '机务检修': '機体整備', '航空整备库': '航空整備庫',
    '联合国防卫部': '国連防衛部', 'UN · 战备设施': 'UN · 戦備施設', '身份卡': 'IDカード', '舱门 GATE': 'ハッチ GATE',
    '供电 POWER': '給電 POWER', '基地・港区': '基地・港区',
    '周边步道': '周辺散策路', '索道': 'ロープウェイ', '箱根山谷站': '箱根山谷駅', '螺旋线换乘': '螺旋線 乗換', '登山电车 / 登山ケーブルカー': '登山電車 / 登山ケーブルカー',
}

# place names inside longer lines, simplified -> Japanese
PLACE_JA = {'强罗': '強羅', '箱根汤本': '箱根湯本', '汤本': '湯本', '早云山': '早雲山', '湾岸防卫区': '湾岸防衛区',
            '小涌谷': '小涌谷', '大涌谷': '大涌谷', '芦之湖': '芦ノ湖', '仙石原': '仙石原', '宫之下': '宮ノ下', '宫ノ下': '宮ノ下',
            '小田原站': '小田原駅', 'UN 航空库': 'UN 格納庫', '螺旋线': '螺旋線', '总部人员出口': '本部職員出口', '雾里': '霧里', '桃源台站': '桃源台駅', '姥子站': '姥子駅'}

# generator lines that carry no meaning on a shop or house front
DROP_LINES = ('入口', '出口', '入口 / 出口', '人员通行', '住宅入口', '办公楼入口')
# Odawara generator lines naming the block and the use ("沼田至饭田冈与穴部西侧街区 住居"): the plate's first line says it
DROP_PATTERN = r'^.+街区 (住居|商店|旅館|喫茶|事務所)$'

# Chinese characters that also appear inside otherwise Japanese names
CHAR_JA = {'站': '駅', '馆': '館', '诊': '診', '疗': '療', '务': '務', '产': '産', '铺': '舗', '杂': '雑', '书': '書',
           '东': '東', '机': '機', '场': '場', '维': '維', '车': '車', '电': '電', '层': '層', '侧': '側', '发': '発',
           '挥': '揮', '处': '処', '贯': '貫', '线': '線', '广': '広', '门': '門'}

# names for house entrances and office entrances, picked by position so neighbours differ
APARTMENT_JA = ['コーポ若葉', 'ハイツ山手', '第二松風荘', 'メゾン桜台', 'コーポ朝日', 'ハイツ緑ヶ丘', '清風荘', 'グリーンハイツ',
                'コーポ富士見', '曙荘', 'ハイツ箱根', 'みどり荘', 'コーポ青葉', 'ハイツ白樺', '松葉荘', 'サンハイツ']
# "<place> <use>" generator plates (小田原駅西 住居) get a name like their neighbours
GENERIC_USE = r'^\S+ (住居|商店|旅館|事務所|喫茶)$'
USE_NAMES = {'商店': ['栄屋商店', 'まるや商店', 'さがみ屋', '小田原屋', 'ふじや商店', '丸十商店'],
             '旅館': ['旅館 浜風', '旅館 さくら', '宿 しおさい', '旅館 小松'],
             '喫茶': ['喫茶 しおさい', '喫茶 ポプラ', '珈琲 はまかぜ', '喫茶 こみち'],
             '事務所': ['西口不動産', '相模測量事務所', '山手司法書士事務所', '小田原保険事務所']}
MINSHUKU_JA = ['民宿 みなと', '民宿 山百合', '民宿 湖畔荘', '民宿 かもめ', '民宿 白樺', '民宿 あしのこ']
OFFICE_JA = ['第一ビル', '山手ビル', '中央ビル', '駅前ビル', '箱根ビル', '富士見ビル', '明和ビル', '朝日ビル']

# One name per NERV place: Japanese, Chinese, English. Every variant on boards, plates and the route graph maps here.
NERV_PLACES = [
    (('指挥室', '指挥区', '第一発令所', '第一发令所'), ('第一発令所', '第一发令所', 'Command Center')),
    (('总部车站', '总部站', '总部火车站', '金字塔总部站', 'NERV 总部站', '本部駅'), ('本部駅', '本部站', 'HQ Station')),
    (('东侧主电梯',), ('A号エレベーター', 'A号电梯', 'Lift A')),
    (('西侧主电梯',), ('B号エレベーター', 'B号电梯', 'Lift B')),
    (('总指挥办公电梯',), ('司令直通エレベーター', '司令直达电梯', "Commander's Lift")),
    (('本层电梯', '本层直梯', '主梯'), ('エレベーター', '电梯', 'Lift')),
    (('EVA 机库', '机库', 'EVA ケイジ'), ('EVA ケイジ', 'EVA 机库', 'EVA Cage')),
    (('LCL 实验室',), ('LCL 実験室', 'LCL 实验室', 'LCL Lab')),
]

# floors of the pyramid and the levels under it: header "nF name"
FLOORS = {
    'B1 · 交通接驳层': ('B1 交通連絡フロア', '交通接驳层', 'Transit Level'),
    'NERV 金字塔 · B1': ('B1 交通連絡フロア', '交通接驳层', 'Transit Level'),
    '1F · 总部门厅': ('1F 本部ロビー', '总部门厅', 'HQ Lobby'),
    'NERV 金字塔 · 1F': ('1F 本部ロビー', '总部门厅', 'HQ Lobby'),
    '2F · 勤务联络层': ('2F 勤務連絡フロア', '勤务联络层', 'Duty Level'),
    '3F · 科研联络层': ('3F 研究連絡フロア', '科研联络层', 'Research Level'),
    '4F · 作战指挥层': ('4F 作戦指揮フロア', '作战指挥层', 'Operations Level'),
    '5F · 指挥室上层': ('5F 発令所上階', '发令所上层', 'Command Upper Level'),
    '6F · 上部办公层': ('6F 上部執務フロア', '上部办公层', 'Upper Offices'),
    '7F · 上部观察层': ('7F 上部観測フロア', '上部观察层', 'Upper Observation'),
    '机库观景层': ('ケイジ展望フロア', '机库观景层', 'Cage Gallery'),
    '机库登机层': ('ケイジ搭乗フロア', '机库登机层', 'Cage Boarding Level'),
}
GUIDE_TITLE = {'通行指引': ('案内', '通行指引', 'Directions'), '本层通行指引': ('このフロアの案内', '本层通行指引', 'Floor Guide')}


def place(name):
    """(ja, zh, en) for a NERV place name or None."""
    for variants, names in NERV_PLACES:
        if name in variants:
            return names
    return None


def to_ja(text):
    """A street sign line in Japanese from the tables only. Character-by-character conversion half-converts Chinese
    phrases (機務检修), so it is used only for the station suffix (小田原站西 -> 小田原駅西); any other Chinese line
    is reported by unknown_chinese() for the table."""
    if text in SHOP_JA:
        return SHOP_JA[text]
    if '每分钟一班' in text:
        return text
    if ' / ' in text:
        return ' / '.join(to_ja(part) for part in text.split(' / '))
    for zh, ja in SHOP_JA.items():
        if len(zh) > 2 and zh in text:
            text = text.replace(zh, ja)
    for zh, ja in PLACE_JA.items():
        text = text.replace(zh, ja)
    text = text.replace('站西', '駅西').replace('站前', '駅前').replace('站东', '駅東')
    return text[:-1] + '駅' if text.endswith('站') and len(text) > 2 else text


SIMPLIFIED_ONLY = set('书馆诊疗务产铺杂东机场维车电层侧发挥处贯线广门们这个为从与时间办楼厅园码观营业员货检穿越滑请沿进键')


def unknown_chinese(text):
    """True when a line still holds a Chinese-only character: simplified forms are missing from cp932 (Japanese
    Shift-JIS), so any CJK character it cannot encode is not Japanese."""
    def not_ja(c):
        if not ('一' <= c <= '鿿'):
            return False
        try:
            c.encode('cp932')
            return c in SIMPLIFIED_ONLY
        except UnicodeEncodeError:
            return True
    return any(not_ja(c) for c in text)


# Japanese kanji -> simplified Chinese, for the Chinese line of room plates
JA2ZH = {'監': '监', '視': '视', '関': '关', '機': '机', '継': '继', '準': '准', '備': '备', '資': '资', '庫': '库', '電': '电',
         '験': '验', '術': '术', '記': '记', '録': '录', '総': '总', '計': '计', '算': '算', '運': '运', '療': '疗', '診': '诊',
         '離': '离', '察': '察', '料': '料', '材': '材', '整': '整', '解': '解', '析': '析', '期': '期', '絡': '络', '戦': '战',
         '報': '报', '達': '达', '測': '测', '気': '气', '動': '动', '発': '发', '揮': '挥', '処': '处', '画': '画', '館': '馆',
         '書': '书', '員': '员', '務': '务', '駅': '站', '層': '层', '階': '阶', '廊': '廊', '験': '验', '製': '制', '収': '收',
         '納': '纳', '験': '验', '試': '试', '制': '制', '御': '御', '液': '液', '排': '排', '隊': '队', '宿': '宿', '舎': '舍',
         '医': '医', '支': '支', '援': '援', '衛': '卫', '防': '防', '設': '设', '消': '消', '更': '更', '衣': '衣', '交': '交',
         '替': '替', '勤': '勤', '当': '值', '直': '班'}
# NERV guide phrases on plain signs (lift landings and corridors)
# NERV guide signs on plain signs (lift landings): whole-sign rewrites, four lines: place, direction in Japanese,
# the same in Chinese and English, then the transfer note in Japanese
NERV_GUIDE_SIGNS = {
    ('GeoFront 湖畔', '↓ 总部交通层', '换乘机库 / 指挥区', '呼梯按钮在下方'):
        ['GeoFront 湖畔', '↓ 本部交通フロア', '总部交通层 Transit', 'ケイジ・発令所へ乗換'],
}
NERV_PHRASES = {}


def ja_to_zh(text):
    if text.startswith('当直'):
        text = '值班' + text[2:]
    return ''.join(JA2ZH.get(c, c) for c in text if True).replace('值班', '值班')


# Minecraft default font advances in pixels (glyph + 1 spacing); characters outside ASCII come from unifont at 9 px.
_NARROW = {' ': 4, '!': 2, '"': 4, "'": 2, '(': 4, ')': 4, '*': 4, ',': 2, '.': 2, ':': 2, ';': 2, '<': 5, '>': 5,
           '@': 7, 'I': 4, '[': 4, ']': 4, '`': 3, 'f': 5, 'i': 2, 'k': 5, 'l': 3, 't': 4, '{': 4, '}': 4, '|': 2,
           '~': 7, '·': 2}
SIGN_WIDTH = 90


def text_width(text):
    return sum(_NARROW.get(c, 6) if ord(c) < 0x2000 or c == '·' else 9 for c in text)


# --- P batch: NERV signs outside the place table ------------------------------------------------------------------
# launch-area observation rooms under the cages: "3号发射区 / 轨道观察室 / 入口 → / 主梯沿廊道向南"
LAUNCH_ROOMS = {'轨道观察室': '軌道観測室', '发射装置观察室': '射出装置観測室', '夹具检修观察室': '拘束具点検観測室'}
for _n in (1, 2, 3):
    for _zh, _ja in LAUNCH_ROOMS.items():
        NERV_GUIDE_SIGNS[(f'{_n}号发射区', _zh, '入口 →', '主梯沿廊道向南')] = \
            [f'第{_n}射出区 {_n}号发射区', f'{_ja} →', _zh, 'エレベーター 南']
NERV_GUIDE_SIGNS.update({
    ('NERV / A', 'DUTY', '值班准备', 'TO COMMAND >'): ['NERV / A', 'DUTY 当直準備', '值班准备', 'TO COMMAND >'],
    ('NERV / A', 'BRIEFING', '作战简报', 'STAIRS SOUTH'): ['NERV / A', 'BRIEFING 作戦説明', '作战简报', 'STAIRS SOUTH'],
    ('明日香待命室', 'NERV 02', '原登栓口同层直达', '待命 / 警卫值守'): ['アスカ待機室', '明日香待命室', 'NERV 02 搭乗口同階', '待機 / 警備員常駐'],
    ('碇真嗣待命室', 'NERV 01', '原登栓口同层直达', '待命 / 警卫值守'): ['碇シンジ待機室', '碇真嗣待命室', 'NERV 01 搭乗口同階', '待機 / 警備員常駐'],
    ('绫波丽待命室', 'NERV 00', '原登栓口同层直达', '待命 / 警卫值守'): ['綾波レイ待機室', '绫波丽待命室', 'NERV 00 搭乗口同階', '待機 / 警備員常駐'],
    ('登机整备层 ↑', '双向扶梯 / 步梯', '下层：发射区检修廊', '上层：三机插入栓入口'):
        ['搭乗整備フロア ↑', 'エスカレーター・階段', '下：射出区点検通路', '上：3機プラグ搭乗口'],
    ('NERV 医疗翼', '101  102  103', '独立静养病房', '前方 / AHEAD'): ['NERV 医療棟', '101  102  103', '個室 独立静养病房', '前方 / AHEAD'],
    ('实验区电梯', '原机库站接驳层', 'LCL 同步实验层', '原机库站接驳层'): ['実験区エレベーター', '旧ケイジ駅連絡階', 'LCL 同調実験フロア', '实验区电梯'],
    ('', '高级指挥台', '', ''): ['', '上級指揮台', '高级指挥台', ''],
    ('TECH / 01', 'DATA SERVICE', '数据链路维护', '< WEST STAIR'): ['TECH / 01', 'DATA SERVICE', 'データ回線保守', '< WEST STAIR'],
    ('TECH / 01', 'DATA SERVICE', '数据链路维护', 'EAST STAIR >'): ['TECH / 01', 'DATA SERVICE', 'データ回線保守', 'EAST STAIR >'],
    ('东侧主电梯 →', '指挥区 / 科研区', '机库整备层', '沿廊道右转'): ['A号エレベーター →', '第一発令所 / 研究区', 'ケイジ整備フロア', 'A号电梯'],
})
for _n in (101, 102, 103):
    NERV_GUIDE_SIGNS[(f'病房 {_n}', 'NERV 医疗翼', '静养 / RECOVERY', '')] = [f'病室 {_n}', 'NERV 医療棟', '回復 / RECOVERY', f'病房 {_n}']

# board headings beyond the floor table: (heading on the old board) -> (ja, zh, en)
BOARD_HEADS = {
    'NERV · LCL 同步实验层': ('LCL 同調実験フロア', 'LCL 同步实验层', 'LCL Sync Lab Level'),
    '地面出口 · 大直梯': ('地上出口 大型エレベーター', '地面出口 · 大直梯', 'Surface Lift'),
    '光学监视室': ('光学監視室', '光学监视室', 'Optical Monitoring'),
}
GUIDE_TITLE['房间入口'] = ('入口', '房间入口', 'Entrance')
# board rows outside the place table: Chinese row -> (ja, zh[, en]); the arrow is kept from the row
BOARD_PHRASES = {
    '地面接待层': ('地上受付フロア', '地面接待层', 'Surface Reception'),
    '门外呼叫 · 轿厢内选层': ('外で呼出・かご内で階選択', '门外呼叫 · 轿厢内选层'),
    '请保持门口净空': ('ドア前で立ち止まらないでください', '请保持门口净空'),
    '大直梯 · 地面入口': ('地上行エレベーター', '大直梯 · 地面入口', 'Surface Lift'),
    '车站 · 地下铁路': ('駅・地下鉄道', '车站 · 地下铁路', 'Station'),
    '请沿东侧主廊进入候车区': ('東側通路から待合へ', '请沿东侧主廊进入候车区'),
    '光学监视室': ('光学監視室', '光学监视室', 'Optical Monitoring'),
    '本层直梯': ('エレベーター', '电梯', 'Lift'),
    '指挥室／车站 · 经直梯': ('発令所・本部駅 EV経由', '指挥室／车站 · 经直梯', 'Command / Station by lift'),
}


# --- S-4: station names from map-roads' R-4 table (kind, old name, "日文|中文|English") ------------------------------
def _load_r4():
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'r4_station_names.tsv')
    stations, routes = {}, {}
    for row in open(path, encoding='utf8'):
        if row.startswith('#') or '\t' not in row:
            continue
        kind, old, new = row.rstrip('\n').split('\t')
        names = tuple(new.split('|'))
        (stations if kind == 'stations' else routes)[old] = names
        if kind == 'stations' and old.endswith('駅'):
            stations[old[:-1]] = names
    return stations, routes


STATIONS, ROUTES = _load_r4()
TRACK_SIDE = {'北侧轨道': ('北側のりば', '北侧轨道', 'North Track'), '南侧轨道': ('南側のりば', '南侧轨道', 'South Track'),
              '东侧轨道': ('東側のりば', '东侧轨道', 'East Track'), '西侧轨道': ('西側のりば', '西侧轨道', 'West Track')}
# station board rows: Chinese -> (ja, zh[, en]); "每分钟一班" rows stay as they are (owner's decision)
STATION_PHRASES = {
    '消防设备': ('消火設備', '消防设备', 'Fire Equipment'),
    '请勿遮挡': ('物を置かないでください', '请勿遮挡', 'Keep Clear'),
    '紧急情况联系站务': ('非常時は駅係員へ', '紧急情况联系站务', 'Emergency: Station Staff'),
    '候车室 / 优先席': ('待合室・優先席', '候车室 / 优先席', 'Waiting Room · Priority Seats'),
    '请先下后上': ('降りる方が先です', '请先下后上', 'Let Passengers Off First'),
    '乘车方向见站台信息牌': ('乗車方向はホームの案内で', '乘车方向见站台信息牌', 'Direction: See Platform Signs'),
    '双向扶梯 · 站台': ('エスカレーター・ホーム', '双向扶梯 · 站台', 'Escalator · Platforms'),
    '双向联络扶梯': ('連絡エスカレーター', '双向联络扶梯', 'Link Escalator'),
    '下层站台': ('下りホーム階', '下层站台', 'Lower Platforms'),
    '上层站台': ('上りホーム階', '上层站台', 'Upper Platforms'),
    '职员服务 · 通行协助': ('職員サービス・通行案内', '职员服务 · 通行协助', 'Staff Service'),
    '换乘／出口见南侧导向牌': ('乗換・出口は南側の案内で', '换乘／出口见南侧导向牌', 'Transfer / Exit: South Signs'),
    '请保留通行证': ('通行証はお持ちください', '请保留通行证', 'Keep Your Pass'),
    'U1 · 总部／研究模拟区': ('U1 NERV本部・研究シミュレーション区', 'U1 · 总部／研究模拟区', 'U1 HQ / Research'),
    '大直梯 · 地面出口': ('大型エレベーター 地上出口', '大直梯 · 地面出口', 'Surface Lift'),
    '服务台在大厅西侧': ('案内所はホール西側', '服务台在大厅西侧', 'Information: West Hall'),
    '站台 · 双向自动步道': ('ホーム・動く歩道', '站台 · 双向自动步道', 'Platforms · Moving Walkway'),
    '乘车前请确认方向和站序': ('乗車前に方向と停車駅を確認', '乘车前请确认方向和站序', 'Check Direction and Stops'),
    '登机楼梯': ('搭乗階段', '登机楼梯', 'Boarding Stairs'),
    '人员出口 · 双向步道': ('職員出口・歩道', '人员出口 · 双向步道', 'Staff Exit'),
    '湿舱不作人员通道': ('ウェットデッキは通行不可', '湿舱不作人员通道', 'Wet Deck: No Passage'),
    '北侧联络厅': ('北側連絡ホール', '北侧联络厅', 'North Link Hall'),
    '登机请循楼梯标识': ('搭乗は階段の案内に従って', '登机请循楼梯标识', 'Board via the Stairs'),
    '注液期间禁止进入': ('注水中は立入禁止', '注液期间禁止进入', 'No Entry While Flooding'),
    '站前导览': ('駅前案内', '站前导览', 'Station Guide'),
    '到达／换乘指引': ('到着・乗換案内', '到达／换乘指引', 'Arrivals / Transfers'),
    '到达服务 · 通行咨询': ('到着案内所', '到达服务 · 通行咨询', 'Arrivals Desk'),
    'U1 · 自动步道接驳': ('U1 動く歩道連絡', 'U1 · 自动步道接驳', 'U1 Walkway Link'),
    '联合国试验机库': ('国連試験格納庫', '联合国试验机库', 'UN Test Hangar'),
    '湿舱区域': ('ウェットデッキ', '湿舱区域', 'Wet Deck'),
}
# diagram footers
MAP_FOOTERS = {
    '发车时间见本侧实时板': '発車時刻はこちら側の発車標で|发车时间见本侧实时板',
    '出口与楼梯 · 按本侧导向': '出口・階段はこちら側の案内で|出口与楼梯 · 按本侧导向',
}


def station(name):
    """(ja, zh, en) for an old station name, with an optional " · 北侧轨道" platform side, or None."""
    base, _, side = name.partition(' · ')
    names = STATIONS.get(base.strip())
    if not names:
        return None
    if side in TRACK_SIDE:
        s = TRACK_SIDE[side]
        return (f'{names[0]} {s[0]}', f'{names[1]} · {s[1]}', f'{names[2]} {s[2]}')
    return names if not side else None
