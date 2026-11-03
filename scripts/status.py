# -*- coding: utf-8 -*-
"""进度查询：发现层链接/任务断点 + 抓取层文档状态"""
import os, sys, json, re
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

def load(p):
    if os.path.exists(p):
        try:
            with open(p, encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            # 文件损坏（如休眠中断写入）：尝试恢复第一段完整JSON
            with open(p, encoding='utf-8') as f:
                text = f.read()
            try:
                data, _ = json.JSONDecoder().raw_decode(text)
                print(f'[warn] {p} 文件不完整，已恢复前 {len(data)} 条记录')
                return data
            except Exception:
                print(f'[error] {p} 无法解析')
                return []
    return []

def main():
    urls = load(config.URLS_JSON)
    docs = load(config.DOCS_JSON)
    print('--- 发现层 ---')
    print(f'链接总数: {len(urls)}')
    if urls:
        print('按渠道:', dict(Counter(x.get('engine') for x in urls)))
        print('按层级:', dict(Counter(x.get('utype') for x in urls)))
        uts = Counter(x.get('unit') for x in urls if x.get('utype') != 'national')
        print(f'覆盖单位数: {len(uts)}')
    st = load(config.STATE_JSON)
    if st:
        print(f'检索任务断点: 已完成 {len(st.get("done_ids", []) or [])} 个')
    print('--- 抓取层 ---')
    if docs:
        ok = sum(1 for d in docs if d.get('status') == 'ok')
        ab = sum(1 for d in docs if d.get('status') == 'abandoned')
        wait = len(docs) - ok - ab
        kw = sum(1 for d in docs if d.get('status') == 'ok' and re.search(r'长期护理|长护险', (d.get('title') or '') + (d.get('body') or '')[:10000]))
        print(f'已处理: {len(docs)} | 成功: {ok} | 待重试: {wait} | 放弃: {ab} | 成功中含关键词: {kw}')
    else:
        print('尚未开始')
    print('--- 输出层 ---')
    if os.path.exists(config.OUT_EXCEL):
        print('Excel已生成:', config.OUT_EXCEL, '|', time_str(config.OUT_EXCEL))
    else:
        print('尚未生成（抓取完成后运行 build_excel.py）')

def time_str(p):
    import datetime
    t = os.path.getmtime(p)
    return datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M')

if __name__ == '__main__':
    main()
