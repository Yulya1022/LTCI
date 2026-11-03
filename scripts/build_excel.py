# -*- coding: utf-8 -*-
"""
输出层：清洗、去重、分类，生成最终Excel
主表：政策标题 / 文号 / 发表时间 / 发表主体 / 来源链接 / 政策原文 / 文件层级 / 所属地区 / 文件类型 / 备注
副表：数据说明 + 去重记录
"""
import os, sys, json, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from urllib.parse import urlparse
import config

KEYWORD_RE = re.compile(r'长期护理|长护险|照护保险')

def load_docs():
    with open(config.DOCS_JSON, encoding='utf-8') as f:
        return json.load(f)

def title_clean(t):
    if not t:
        return ''
    t = re.sub(r'[\s　]+', '', t)
    t = re.sub(r'[_|｜—\-–]+(?:中国政府网|.*?政府网|.*?政务网|.*?医保局|.*?门户网站)$', '', t)
    t = re.sub(r'[_|｜—\-–]+(?:其他|首页|网站首页|默认分类|无)$', '', t)
    t = t.replace('：', ':').replace('（', '(').replace('）', ')').replace('《', '').replace('》', '')
    return t

def classify(t):
    """按标题/正文关键词粗分类"""
    if not t:
        return '其他'
    if re.search(r'解读|一问一答|图解|答记者问|新闻发布会', t):
        return '政策解读'
    if re.search(r'名单|公示|拟纳入|定点.*公布|评估结果|鉴定结论|评定结果', t):
        return '公示公告'
    if re.search(r'新闻|动态|会议|调研|讲话|工作进展|试点成效|经验交流|报道', t):
        return '新闻动态'
    if re.search(r'办法|方案|意见|通知|细则|规程|标准|目录|规范|指引|规定|规划|条例|决定|答复|函', t):
        return '政策文件'
    return '其他'

NATIONAL_HOSTS = ('www.gov.cn', 'gov.cn')
NATIONAL_SUFFIX = ('.nhsa.gov.cn', '.mohrss.gov.cn', '.mca.gov.cn', '.nhc.gov.cn',
                   '.mof.gov.cn', '.npc.gov.cn', '.ndrc.gov.cn')
# 试点城市清单之外、但语料中出现的地区域名
REGION_HINT = {'ks.gov.cn': '昆山', 'sz.gov.cn': '深圳', 'snj.gov.cn': '神农架'}

ORG_TAIL = r'(?:人民政府|政府办公厅|人民政府办公室|医疗保障局|医保局|财政局|民政局|卫生健康委员会|卫生和计划生育委员会|人力资源和社会保障局|人社局|发展改革委员会|发展和改革委员会|残疾人联合会|市场监督管理局|委员会|办公室|政府|中心|厅|局|部|处|科|办|室|所|队)'

LABEL_WORDS = ('成文日期', '发文日期', '发布日期', '生成日期', '发布时间', '公开日期', '索引号',
               '主题分类', '有效性', '来源', '作者', '编辑', '责任编辑', '浏览次数', '字号')
NOISE_SUFFIX = re.compile(r'(?:微信公众号|微信|公众号|官网|官方网站|门户网站|人民政府网|政府网|网站|网)$')

def norm_issuer(s):
    """规范主体值：去标签词、去网站后缀、去尾部数字"""
    if not isinstance(s, str):
        return ''
    s = s.strip().strip(' \t:：,，;；|、-—【】[]()（）《》')
    s = re.sub(r'[,\s]*版权所有.*$', '', s)
    s = re.sub(r'\d+$', '', s)
    s = NOISE_SUFFIX.sub('', s).strip()
    if s in LABEL_WORDS or len(s) < 2:
        return ''
    return s

def valid_issuer(s):
    """校验主体值：必须是机构名，排除整句正文被误抓的情况"""
    s = norm_issuer(s)
    if not s or len(s) > 80:
        return False
    if re.search(r'[？。！；，,：:]', s):  # 含句读标点，说明抓到了正文
        return False
    return bool(re.search(ORG_TAIL + r'$', s))

def joint_issuer(title):
    """从标题识别多部门联合发文（如“A局 B局 C委关于印发…的通知”）"""
    if not title:
        return ''
    t = re.sub(r'[\s　]+', ' ', title).strip().lstrip('《〈（(【[')
    head = re.split(r'(?:关于|转发|印发|制定)', t)[0].strip()
    parts = [p for p in re.split(r'[ 　、]+', head) if p]
    if len(parts) < 2:
        return ''
    if not all(re.search(ORG_TAIL + '$', p) for p in parts):
        return ''
    return ' '.join(parts)

def guess_region(rec):
    """从发现层单位或域名推断所属地区"""
    unit = rec.get('discover_unit', '')
    if unit and unit not in ('国家层面',):
        return unit
    host = urlparse(rec['url']).netloc.lower()
    # 国家部委域名 -> 国家层面
    if host in NATIONAL_HOSTS or host.endswith(NATIONAL_SUFFIX):
        return '国家层面'
    for frag, region in sorted(REGION_HINT.items(), key=lambda x: -len(x[0])):
        if frag in host:
            return region
    for city, frag in config.CITY_DOMAIN.items():
        if frag and frag in host:
            return city
    for prov, frag in config.PROV_DOMAIN.items():
        if frag and frag in host:
            return prov
    return '待识别'

def level_of(rec):
    ut = rec.get('discover_utype', '')
    host = urlparse(rec['url']).netloc.lower()
    if ut == 'national':
        return '国家级'
    if host in ('www.gov.cn', 'gov.cn') or host.endswith('.nhsa.gov.cn') or host.endswith('.mohrss.gov.cn') \
            or host.endswith('.mca.gov.cn') or host.endswith('.nhc.gov.cn') or host.endswith('.mof.gov.cn') \
            or host.endswith('.npc.gov.cn') or host.endswith('.ndrc.gov.cn'):
        return '国家级'
    region = guess_region(rec)
    if ut == 'city' or (region and region not in ('待识别',) and region not in config.PROVINCES):
        return '市级'
    if ut == 'province':
        return '省级'
    return '省级'

def main():
    docs = load_docs()
    print(f'载入 {len(docs)} 条抓取记录')
    ok = [d for d in docs if d.get('status') == 'ok']
    fail = [d for d in docs if d.get('status') != 'ok']
    print(f'成功 {len(ok)} 条，失败 {len(fail)} 条')

    # ---- 相关性过滤：标题或正文必须包含关键词 ----
    kept, dropped_irr = [], []
    for d in ok:
        blob = (d.get('title', '') or '') + (d.get('body', '') or '')[:20000] \
               + (d.get('discover_title', '') or '')
        if KEYWORD_RE.search(blob):
            kept.append(d)
        else:
            dropped_irr.append(d)

    # ---- 去重：先URL精确（规范化），再同标题同单位 ----
    seen_url, seen_title = set(), {}
    final, dups = [], []
    for d in kept:
        u = d['url']
        if u in seen_url:
            dups.append((u, d.get('title', ''), 'URL重复'))
            continue
        seen_url.add(u)
        tc = title_clean(d.get('title') or d.get('discover_title') or '')
        if tc and tc in seen_title:
            dups.append((u, d.get('title', ''), '标题重复于 ' + seen_title[tc]))
            continue
        if tc:
            seen_title[tc] = u
        final.append(d)

    # ---- 组装行 ----
    rows = []
    for d in final:
        title = d.get('title') or d.get('discover_title') or ''
        region = guess_region(d)
        lvl = level_of(d)
        doc_type = classify(title + ' ' + (d.get('body') or '')[:2000])
        # 附件内容合并进原文
        body = d.get('body') or ''
        for att in d.get('attachments', []):
            body += f'\n【附件：{att["name"]}（{att["ext"]}，链接见备注）】'
        if len(body) > 32000:
            body = body[:32000] + '\n...[原文过长，已截断，完整内容见来源链接]'
        remark = ''
        if d.get('pdf_error') or d.get('doc_error'):
            remark = '附件解析失败，仅保留链接'
        elif d.get('file_type') in ('PDF', 'DOC') and not body.strip():
            remark = '原文为附件格式，无法解析文本，请打开链接查看'
        elif d.get('file_type') == 'HTML' and not body.strip():
            remark = '页面未提取到正文（动态渲染或栏目列表页），请打开链接查看'
        rows.append({
            '政策标题': title,
            '文号': d.get('doc_no') or '',
            '发表时间': d.get('pub_date') or '',
            '发表主体': max([norm_issuer(x) for x in (d.get('issuer') or '', joint_issuer(title)) if valid_issuer(x)] or [''], key=len),
            '来源链接': d['url'],
            '政策原文': body,
            '文件层级': lvl,
            '所属地区': region,
            '文件类型': doc_type,
            '备注': remark,
        })
    # 排序：层级 -> 地区 -> 时间
    order = {'国家级': 0, '省级': 1, '市级': 2}
    rows.sort(key=lambda r: (order.get(r['文件层级'], 9), r['所属地区'], r['发表时间'] or '9999'))
    print(f'最终 {len(rows)} 条：剔除无关 {len(dropped_irr)}，去重 {len(dups)}')

    # ---- 写Excel ----
    import pandas as pd
    df = pd.DataFrame(rows)
    cols = ['政策标题', '文号', '发表时间', '发表主体', '来源链接', '政策原文', '文件层级', '所属地区', '文件类型', '备注']
    df = df[cols]
    with pd.ExcelWriter(config.OUT_EXCEL, engine='openpyxl') as w:
        df.to_excel(w, sheet_name='政策文本', index=False)
        # 说明页
        info = [
            ['数据名称', '长期护理保险（长护险）政策文本汇总'],
            ['生成时间', time.strftime('%Y-%m-%d %H:%M')],
            ['数据来源', '全部为政府官方网站（*.gov.cn 域名），经搜狗/必应检索发现、国家医保局长护险专栏及中国政府网政策库直爬确认'],
            ['覆盖范围', '国家级文件 + 31省/兵团文件 + 49个试点城市（含两批试点）+ 其它已实施长护险的重点城市'],
            ['时间范围', '2016年试点启动至今（以各网站公开发布为准）'],
            ['抓取状态', f'共抓取 {len(docs)} 个链接，成功 {len(ok)} 条，通过相关性过滤后 {len(kept)} 条，去重后 {len(rows)} 条'],
            ['字段说明', '发表时间优先取页面"发布日期"，其次"成文日期"；发表主体优先取页面"发文单位"标注，其次从标题或域名推断；政策原文为页面正文（含可解析的PDF/Word附件内容）'],
            ['注意1', '部分城市在政府网站"信息公开"栏目公开文件，若正文通过附件（PDF/Word）发布且无法解析，备注栏已注明，请打开链接查看'],
            ['注意2', '个别政策文件可能存在多个官方转载版本，已按标题去重保留一条；同一政策修订前后的多个版本均保留（PMC评价可能需要历年版本对比）'],
            ['注意3', '新闻动态、政策解读类文本也已收录（文件类型列可区分），做PMC评价时建议仅使用"政策文件"类型'],
        ]
        pd.DataFrame(info, columns=['项目', '内容']).to_excel(w, sheet_name='数据说明', index=False)
        if dups:
            pd.DataFrame(dups, columns=['链接', '标题', '去重原因']).to_excel(w, sheet_name='去重记录', index=False)
        if fail:
            pd.DataFrame([{'链接': d['url'], '状态': d.get('status'), '发现标题': d.get('discover_title', '')} for d in fail],
                         columns=['链接', '状态', '发现标题']).to_excel(w, sheet_name='抓取失败记录', index=False)

    # ---- 美化主表 ----
    from openpyxl import load_workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    wb = load_workbook(config.OUT_EXCEL)
    ws = wb['政策文本']
    widths = {'A': 42, 'B': 16, 'C': 12, 'D': 20, 'E': 46, 'F': 90, 'G': 9, 'H': 10, 'I': 10, 'J': 24}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='4472C4')
        cell.alignment = Alignment(horizontal='center', vertical='center')
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical='top', wrap_text=(cell.column_letter in ('A', 'F', 'J')))
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = ws.dimensions
    wb.save(config.OUT_EXCEL)
    print(f'Excel已生成：{config.OUT_EXCEL}')

if __name__ == '__main__':
    main()
