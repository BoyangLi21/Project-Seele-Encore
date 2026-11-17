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
    '站前喫茶': '駅前喫茶', '登山缆车': '登山ケーブルカー', '温泉案内': '温泉案内', '名产': '名産品',
    '湖畔餐厅': '湖畔レストラン', '湖畔茶屋': '湖畔茶屋', '箱根索道': '箱根ロープウェイ', '芦之湖游船': '芦ノ湖遊覧船',
    '芦之湖 · 桃源台港': '芦ノ湖 桃源台港', '桃源台站': '桃源台駅', '桃源台 公交': '桃源台 バスのりば',
    '强罗站 公交': '強羅駅 バスのりば', '姥子 · 票务': '姥子 きっぷ売り場', '大涌谷 · 票务': '大涌谷 きっぷ売り場',
    '早云山 · 换乘票务': '早雲山 乗換きっぷ売り場', '强罗 · 乘车服务': '強羅 乗車案内', '强罗接驳线': '強羅連絡線',
    '新箱根机场 · 管制塔': '新箱根飛行場 管制塔', '箱根湾机场 · 管制塔': '箱根湾空港 管制塔',
    '北町公民会馆': '北町公民館', '北町诊所': '北町診療所', '团地诊疗所': '団地診療所', '団地診疗所': '団地診療所',
    '学校体育馆': '学校体育館', '第三新东京市立': '第3新東京市立', '社区商住': '商店併用住宅',
    '航空维修库': '航空整備庫', '整备补给中心': '整備補給センター', 'NERV 总部': 'NERV 本部',
    '西町生活店': '西町生活店', '霧里食料品店': '霧里食料品店',
}

# generator lines that carry no meaning on a shop or house front
DROP_LINES = ('入口', '出口', '入口 / 出口', '人员通行', '住宅入口', '办公楼入口')

# Chinese characters that also appear inside otherwise Japanese names
CHAR_JA = {'站': '駅', '馆': '館', '诊': '診', '疗': '療', '务': '務', '产': '産', '铺': '舗', '杂': '雑', '书': '書',
           '东': '東', '机': '機', '场': '場', '维': '維', '车': '車', '电': '電', '层': '層', '侧': '側', '发': '発',
           '挥': '揮', '处': '処', '贯': '貫', '线': '線', '广': '広', '门': '門'}

# names for house entrances and office entrances, picked by position so neighbours differ
APARTMENT_JA = ['コーポ若葉', 'ハイツ山手', '第二松風荘', 'メゾン桜台', 'コーポ朝日', 'ハイツ緑ヶ丘', '清風荘', 'グリーンハイツ',
                'コーポ富士見', '曙荘', 'ハイツ箱根', 'みどり荘', 'コーポ青葉', 'ハイツ白樺', '松葉荘', 'サンハイツ']
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
    """A street sign line in Japanese: known names first, then character fixes."""
    if text in SHOP_JA:
        return SHOP_JA[text]
    for zh, ja in SHOP_JA.items():
        if len(zh) > 2 and zh in text:
            text = text.replace(zh, ja)
    return ''.join(CHAR_JA.get(c, c) for c in text)


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
        ['GeoFront 湖畔', '↓ 本部交通フロア', '总部交通层 · Transit Level', 'ケイジ・発令所へ乗換'],
}
NERV_PHRASES = {}


def ja_to_zh(text):
    if text.startswith('当直'):
        text = '值班' + text[2:]
    return ''.join(JA2ZH.get(c, c) for c in text if True).replace('值班', '值班')
