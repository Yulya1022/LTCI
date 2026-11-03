# -*- coding: utf-8 -*-
"""长期护理保险政策文本爬取 — 配置：检索范围、关键词、路径设置"""
import os, sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根目录
DATA_DIR = os.path.join(BASE_DIR, 'data')
RAW_DIR = os.path.join(DATA_DIR, 'raw')            # 原始抓取数据（逐URL记录）
PROCESSED_DIR = os.path.join(DATA_DIR, 'processed')  # 清洗后可供分析的数据
LOG_DIR = os.path.join(BASE_DIR, 'logs')
DL_DIR = os.path.join(BASE_DIR, 'downloads')
OUT_EXCEL = os.path.join(BASE_DIR, '长期护理保险政策文本汇总.xlsx')
URLS_JSON = os.path.join(RAW_DIR, 'urls_raw.json')
DOCS_JSON = os.path.join(RAW_DIR, 'docs_raw.json')
STATE_JSON = os.path.join(RAW_DIR, 'discovery_state.json')
LOG_FILE = os.path.join(LOG_DIR, 'crawl.log')

# ---------------- 检索单位 ----------------
# 第一批试点城市 (2016)
PILOT_BATCH1 = ['承德', '长春', '齐齐哈尔', '上海', '南通', '苏州', '宁波', '安庆',
                '上饶', '青岛', '荆门', '广州', '重庆', '成都', '石河子']
# 第二批试点地区 (2020)
PILOT_BATCH2 = ['北京市石景山区', '天津', '晋城', '呼和浩特', '盘锦', '福州', '开封',
                '湘潭', '南宁', '黔西南州', '昆明', '汉中', '甘南州', '乌鲁木齐']
# 已实际实施长护险的其它重点城市（非49试点但已发文）
EXTRA_CITIES = ['深圳', '珠海', '东莞', '佛山', '中山', '惠州', '江门', '肇庆', '汕头', '湛江', '梅州', '韶关',
                '南京', '无锡', '徐州', '常州', '连云港', '淮安', '盐城', '扬州', '镇江', '泰州', '宿迁',
                '杭州', '嘉兴', '湖州', '绍兴', '金华', '衢州', '舟山', '台州', '丽水', '温州',
                '合肥', '芜湖', '马鞍山', '蚌埠', '铜陵', '淮北', '池州', '宣城', '六安',
                '济南', '淄博', '枣庄', '东营', '烟台', '潍坊', '济宁', '泰安', '威海', '日照', '临沂', '德州', '聊城', '滨州', '菏泽',
                '武汉', '宜昌', '襄阳', '黄石', '十堰', '荆州', '孝感', '黄冈', '咸宁', '随州', '恩施',
                '长沙', '株洲', '衡阳', '岳阳', '常德', '益阳', '郴州', '永州', '怀化', '娄底', '湘西州',
                '贵阳', '遵义', '六盘水', '安顺', '毕节', '铜仁',
                '西安', '宝鸡', '咸阳', '渭南', '延安', '榆林', '安康', '商洛',
                '兰州', '天水', '平凉', '庆阳', '定西', '陇南', '临夏州',
                '西宁', '海东', '银川', '石嘴山', '吴忠', '固原', '中卫',
                '哈尔滨', '大庆', '沈阳', '大连', '丹东', '锦州', '营口', '吉林市', '四平', '辽源', '通化', '白山', '松原', '白城', '延边州',
                '太原', '大同', '长治', '运城', '临汾', '晋中', '石家庄', '唐山', '秦皇岛', '邯郸', '邢台', '保定', '张家口', '沧州', '廊坊', '衡水',
                '呼和浩特', '包头', '呼伦贝尔', '通辽', '赤峰', '鄂尔多斯',
                '厦门', '漳州', '泉州', '莆田', '三明', '南平', '龙岩', '宁德',
                '郑州', '洛阳', '平顶山', '安阳', '新乡', '焦作', '许昌', '漯河', '南阳', '商丘', '信阳', '周口', '驻马店',
                '海口', '三亚', '柳州', '桂林', '曲靖', '玉溪', '保山', '克拉玛依']

PROVINCES = ['北京', '天津', '河北', '山西', '内蒙古', '辽宁', '吉林', '黑龙江', '上海', '江苏', '浙江', '安徽',
             '福建', '江西', '山东', '河南', '湖北', '湖南', '广东', '广西', '海南', '重庆', '四川', '贵州',
             '云南', '西藏', '陕西', '甘肃', '青海', '宁夏', '新疆', '新疆生产建设兵团']

NATIONAL = ['国家层面']

# 城市名 -> 域名关键词（用于判断政策来源地区）
CITY_DOMAIN = {
    '承德': 'chengde', '长春': 'changchun', '齐齐哈尔': 'qqhr', '上海': 'shanghai', '南通': 'nantong',
    '苏州': 'suzhou', '宁波': 'ningbo', '安庆': 'anqing', '上饶': 'shangrao', '青岛': 'qingdao',
    '荆门': 'jingmen', '广州': 'guangzhou', '重庆': 'chongqing', '成都': 'chengdu', '石河子': 'shihezi',
    '北京': 'beijing', '天津': 'tj', '晋城': 'jincheng', '呼和浩特': 'hohhot', '盘锦': 'panjin',
    '福州': 'fuzhou', '开封': 'kaifeng', '湘潭': 'xiangtan', '南宁': 'nanning', '黔西南州': 'qxn',
    '昆明': 'kunming', '汉中': 'hanzhong', '甘南州': 'gn', '乌鲁木齐': 'urumqi',
    '深圳': 'shenzhen', '珠海': 'zhuhai', '东莞': 'dongguan', '佛山': 'foshan', '中山': 'zhongshan',
    '惠州': 'huizhou', '江门': 'jiangmen', '肇庆': 'zhaoqing', '汕头': 'shantou', '湛江': 'zhanjiang',
    '梅州': 'meizhou', '韶关': 'shaoguan', '南京': 'nanjing', '无锡': 'wuxi', '徐州': 'xuzhou',
    '常州': 'changzhou', '连云港': 'lyg', '淮安': 'huaian', '盐城': 'yancheng', '扬州': 'yangzhou',
    '镇江': 'zhenjiang', '泰州': 'taizhou', '宿迁': 'suqian', '杭州': 'hangzhou', '嘉兴': 'jiaxing',
    '湖州': 'huzhou', '绍兴': 'sx', '金华': 'jinhua', '衢州': 'quzhou', '舟山': 'zhoushan',
    '台州': 'zjtz', '丽水': 'lishui', '温州': 'wenzhou', '合肥': 'hefei', '芜湖': 'wuhu',
    '马鞍山': 'mas', '蚌埠': 'bengbu', '铜陵': 'tongling', '淮北': 'huaibei', '池州': 'chizhou',
    '宣城': 'xuancheng', '六安': 'luan', '济南': 'jinan', '淄博': 'zibo', '枣庄': 'zaozhuang',
    '东营': 'dongying', '烟台': 'yantai', '潍坊': 'weifang', '济宁': 'jining', '泰安': 'taian',
    '威海': 'weihai', '日照': 'rizhao', '临沂': 'linyi', '德州': 'dezhou', '聊城': 'liaocheng',
    '滨州': 'binzhou', '菏泽': 'heze', '武汉': 'wuhan', '宜昌': 'yichang', '襄阳': 'xiangyang',
    '黄石': 'huangshi', '十堰': 'shiyan', '荆州': 'jingzhou', '孝感': 'xiaogan', '黄冈': 'hg',
    '咸宁': 'xianning', '随州': 'suizhou', '恩施': 'enshi', '长沙': 'changsha', '株洲': 'zhuzhou',
    '衡阳': 'hengyang', '岳阳': 'yueyang', '常德': 'changde', '益阳': 'yiyang', '郴州': 'chenzhou',
    '永州': 'yongzhou', '怀化': 'huaihua', '娄底': 'loudi', '湘西州': 'xxz', '贵阳': 'guiyang',
    '遵义': 'zunyi', '六盘水': 'lps', '安顺': 'anshun', '毕节': 'bijie', '铜仁': 'trs',
    '西安': 'xian', '宝鸡': 'baoji', '咸阳': 'xianyang', '渭南': 'weinan', '延安': 'yanan',
    '榆林': 'yl', '安康': 'ankang', '商洛': 'shangluo', '兰州': 'lanzhou', '天水': 'tianshui',
    '平凉': 'pingliang', '庆阳': 'qingyang', '定西': 'dingxi', '陇南': 'longnan', '临夏州': 'linxia',
    '西宁': 'xining', '海东': 'haidong', '银川': 'yinchuan', '石嘴山': 'shizuishan', '吴忠': 'wuzhong',
    '固原': 'guyuan', '中卫': 'zhongwei', '哈尔滨': 'harbin', '大庆': 'daqing', '沈阳': 'shenyang',
    '大连': 'dalian', '丹东': 'dandong', '锦州': 'jinzhou', '营口': 'yingkou', '吉林市': 'jil',
    '四平': 'siping', '辽源': 'liaoyuan', '通化': 'tonghua', '白山': 'baishan', '松原': 'songyuan',
    '白城': 'baicheng', '延边州': 'yanbian', '太原': 'taiyuan', '大同': 'datong', '长治': 'changzhi',
    '运城': 'yuncheng', '临汾': 'linfen', '晋中': 'sxjz', '石家庄': 'sjz', '唐山': 'tangshan',
    '秦皇岛': 'qhd', '邯郸': 'handan', '邢台': 'xingtai', '保定': 'baoding', '张家口': 'zjk',
    '沧州': 'cangzhou', '廊坊': 'langfang', '衡水': 'hengshui', '包头': 'baotou', '呼伦贝尔': 'hlbe',
    '通辽': 'tongliao', '赤峰': 'chifeng', '鄂尔多斯': 'ordos', '厦门': 'xiamen', '漳州': 'zhangzhou',
    '泉州': 'quanzhou', '莆田': 'putian', '三明': 'sanming', '南平': 'nanping', '龙岩': 'longyan',
    '宁德': 'ningde', '郑州': 'zhengzhou', '洛阳': 'luoyang', '平顶山': 'pds', '安阳': 'anyang',
    '新乡': 'xinxiang', '焦作': 'jiaozuo', '许昌': 'xuchang', '漯河': 'luohe', '南阳': 'nanyang',
    '商丘': 'shangqiu', '信阳': 'xinyang', '周口': 'zhoukou', '驻马店': 'zhumadian', '海口': 'haikou',
    '三亚': 'sanya', '柳州': 'liuzhou', '桂林': 'guilin', '曲靖': 'qujing', '玉溪': 'yuxi',
    '保山': 'baoshan', '克拉玛依': 'klmy',
}
PROV_DOMAIN = {
    '北京': 'beijing', '天津': 'tj.gov', '河北': 'hebei', '山西': 'shanxi', '内蒙古': 'nmg',
    '辽宁': 'ln', '吉林': 'jl', '黑龙江': 'hlj', '上海': 'shanghai', '江苏': 'jiangsu',
    '浙江': 'zj', '安徽': 'ah', '福建': 'fujian', '江西': 'jiangxi', '山东': 'shandong',
    '河南': 'henan', '湖北': 'hubei', '湖南': 'hunan', '广东': 'gd', '广西': 'gxzf',
    '海南': 'hainan', '重庆': 'cq', '四川': 'sc', '贵州': 'guizhou', '云南': 'yn',
    '西藏': 'xizang', '陕西': 'shaanxi', '甘肃': 'gansu', '青海': 'qinghai', '宁夏': 'nx',
    '新疆': 'xinjiang', '新疆生产建设兵团': 'bingtuan',
}

def build_units():
    """返回 [(单位名, 类型, 优先级)]  类型: national/province/city"""
    units = []
    for c in PILOT_BATCH1 + PILOT_BATCH2:
        units.append((c, 'city', 1))
    for c in EXTRA_CITIES:
        units.append((c, 'city', 2))
    for p in PROVINCES:
        units.append((p, 'province', 1))
    for n in NATIONAL:
        units.append((n, 'national', 1))
    return units

# 特殊地名别名（用于扩大检索召回）
UNIT_ALIAS = {
    '北京市石景山区': ['石景山区', '北京石景山'],
    '黔西南州': ['黔西南'], '甘南州': ['甘南'], '湘西州': ['湘西'],
    '延边州': ['延边'], '临夏州': ['临夏'],
}

def build_queries(unit, utype):
    """为一个检索单位构造查询词列表"""
    if utype == 'national':
        return ['长期护理保险 试点 指导意见', '长期护理保险 扩大试点',
                '长期护理保险 失能等级评估 标准', '长期护理保险 经办服务 规程',
                '长期护理保险 服务项目 目录', '长期护理保险 定点机构 管理办法',
                '长期护理保险 制度 意见', '长护险 政策 文件']
    if utype == 'province':
        return [f'{unit} 长期护理保险 实施办法', f'{unit} 长期护理保险 试点 方案',
                f'{unit} 长护险 政策 文件']
    # city：主名+别名轮换组合
    names = [unit] + UNIT_ALIAS.get(unit, [])
    tmpl = ['{n} 长期护理保险 办法', '{n} 长期护理保险 试点 方案',
            '{n} 长期护理保险 服务项目 目录', '{n} 长期护理保险 失能评估',
            '{n} 长期护理保险 定点机构', '{n} 长护险']
    return [t.format(n=names[i % len(names)]) for i, t in enumerate(tmpl)]

# 每查询词最多翻页数（每页约10条）
SEARCH_PAGES_PER_QUERY = 2
# 搜索引擎请求间隔（秒）范围，降低反爬风险
DELAY_SEARCH = (6, 12)
DELAY_RESOLVE = (1.5, 3.5)
DELAY_FETCH = (1.5, 3.0)
TIMEOUT = 25
MAX_RETRY = 3
