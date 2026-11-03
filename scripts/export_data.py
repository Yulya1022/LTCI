# -*- coding: utf-8 -*-
"""
输出层（补充）：把最终 Excel 导出为便于程序读取的 CSV，并生成统计数据
- data/processed/ltci_policies_all.csv          全量 978 条
- data/processed/ltci_policy_documents.csv      仅“政策文件”类型（PMC 评价用）
- data/processed/ltci_statistics.csv            分年度/层级/地区/类型统计
编码统一 UTF-8 with BOM，Excel 双击可直接打开不乱码
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import pandas as pd

COLS = ['政策标题', '文号', '发表时间', '发表主体', '来源链接', '政策原文',
        '文件层级', '所属地区', '文件类型', '备注']


def main():
    os.makedirs(config.PROCESSED_DIR, exist_ok=True)
    df = pd.read_excel(config.OUT_EXCEL, sheet_name='政策文本')
    df = df[COLS]

    # 全量
    p_all = os.path.join(config.PROCESSED_DIR, 'ltci_policies_all.csv')
    df.to_csv(p_all, index=False, encoding='utf-8-sig')
    print(f'全量 {len(df)} 条 -> {p_all}')

    # PMC 评价子集：仅政策文件
    sub = df[df['文件类型'] == '政策文件'].copy()
    p_sub = os.path.join(config.PROCESSED_DIR, 'ltci_policy_documents.csv')
    sub.to_csv(p_sub, index=False, encoding='utf-8-sig')
    print(f'政策文件子集 {len(sub)} 条 -> {p_sub}')

    # 统计
    rows = []
    year = df['发表时间'].astype(str).str.slice(0, 4)
    for y, c in year[year.str.match(r'^20\d{2}$')].value_counts().sort_index().items():
        rows.append(['按发布年份', y, int(c)])
    for k, col in [('按文件层级', '文件层级'), ('按文件类型', '文件类型')]:
        for v, c in df[col].value_counts().items():
            rows.append([k, v, int(c)])
    for v, c in df['所属地区'].value_counts().head(30).items():
        rows.append(['按地区Top30', v, int(c)])
    rows.append(['字段覆盖度', '发表时间有值', int(df['发表时间'].notna().sum())])
    rows.append(['字段覆盖度', '发表主体有值', int(df['发表主体'].notna().sum())])
    rows.append(['字段覆盖度', '文号有值', int(df['文号'].notna().sum())])
    rows.append(['字段覆盖度', '政策原文>100字', int((df['政策原文'].fillna('').str.len() > 100).sum())])
    p_stat = os.path.join(config.PROCESSED_DIR, 'ltci_statistics.csv')
    pd.DataFrame(rows, columns=['统计维度', '取值', '条数']).to_csv(
        p_stat, index=False, encoding='utf-8-sig')
    print(f'统计 -> {p_stat}')
    print(f'覆盖地区 {df["所属地区"].nunique()} 个 | 时间范围 {df["发表时间"].dropna().astype(str).min()} ~ {df["发表时间"].dropna().astype(str).max()}')


if __name__ == '__main__':
    main()
