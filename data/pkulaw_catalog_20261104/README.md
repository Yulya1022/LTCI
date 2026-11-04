# 北大法宝长护险目录 + 政府官网公开全文快照

**快照时间**：约 2026-11-04（Asia/Shanghai）  
**来源**：北大法宝公开目录检索 + 各级政府官网公开全文（非 VIP / 非付费库正文）

本目录按三张目录打包，**未**与仓库既有 `data/processed` 或 PMC/977 语料做合并对照；仅为独立检索快照。

## 目录对照统计

| 目录 | 条目 | ok | pending | partial | not_found | 备注 |
|------|------|----|---------|---------|-----------|------|
| 中央（`index.csv`） | 22 | 20 | 0 | 1 | 1 | |
| 地方（`local_index.csv`） | 925 | 651 | 234 | 40 | 0 | pending 中有文号约 102 |
| 其他（`other_index.csv`） | 72 | 65 | 2 | 0 | 5 | |
| **合计** | **1019** | **736** | **236** | **41** | **6** | |

## 内容说明

- `index.csv` / `local_index.csv` / `other_index.csv`：三张目录及抓取状态字段
- `progress.md`：抓取进度记录
- `*_listing_*.json`：北大法宝列表页原始摘录（可选辅助）
- `central/` `local/` `other/`：对应官网公开全文（多为 `official/` 下按条目存放的 html/txt/pdf）
- `supplemental/`：少量补充抓取材料

状态含义简述：`ok` 已抓到官网公开全文；`pending` 尚未搞定；`partial` 只找到一部分或对不上；`not_found` 公开渠道确认找不到。
