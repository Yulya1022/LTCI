# -*- coding: utf-8 -*-
"""
抓取层 v2：对发现层得到的每个政府官网链接进行抓取解析（断点续爬）
- URL级断点：已成功(ok)或已放弃(abandoned)的URL自动跳过，失败URL重试
- 同一URL失败满3次标记为abandoned，不再浪费请求
- 每10条保存一次检查点，Ctrl+C安全退出
- 输出字段：标题、发表时间、发表主体、文号、政策原文、附件
"""
import os, sys, json, time, random, re, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, common

logger = logging.getLogger('crawl_fetch')
logger.setLevel(logging.INFO)
_fh = logging.FileHandler(config.LOG_FILE, encoding='utf-8')
_fh.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
logger.addHandler(_fh)
_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(_sh)

MAX_ATTEMPTS = 3
REDO_WEAK = '--redo-weak' in sys.argv


def log(msg):
    logger.info(msg)


def is_weak(rec):
    """判断已有成功记录是否需要补抓：正文过短/缺主体/缺时间/时间非法"""
    if (rec.get('text_len') or 0) < 120:
        return True
    if not rec.get('issuer') or not rec.get('pub_date'):
        return True
    pd = rec.get('pub_date', '')
    if not re.match(r'^(19|20)\d{2}-\d{2}-\d{2}$', pd):
        return True
    try:
        y, mo, d = map(int, pd.split('-'))
        if not (1990 <= y <= 2036 and 1 <= mo <= 12 and 1 <= d <= 31):
            return True
    except Exception:
        return True
    return False


def load_json(p):
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
                log(f'[warn] {p} 文件不完整，已恢复前 {len(data)} 条记录')
                return data
            except Exception:
                log(f'[error] {p} 无法解析')
                return []
    return []


def save_json(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)  # 原子替换，避免中断时写坏文件


def main():
    urls = load_json(config.URLS_JSON)
    # 载入既有抓取记录，按URL去重（保留最新一条）
    records = {}
    for d in load_json(config.DOCS_JSON):
        records[d['url']] = d
    if REDO_WEAK:
        todo = [x for x in urls if x['url'] in records
                and records[x['url']].get('status') == 'ok' and is_weak(records[x['url']])]
        log(f'补抓模式：重抓 {len(todo)} 条质量不足的记录（成功记录共 {sum(1 for d in records.values() if d.get("status") == "ok")} 条）')
    else:
        skip = {u for u, d in records.items() if d.get('status') in ('ok', 'abandoned')}
        todo = [x for x in urls if x['url'] not in skip]
        log(f'断点续爬：已完成/放弃 {len(skip)} 条，待抓取 {len(todo)} 条')

    sess = common.new_session()
    n_fail = 0
    try:
        for i, item in enumerate(todo):
            u = item['url']
            prev = records.get(u, {})
            attempts = 1 if REDO_WEAK else prev.get('attempts', 0) + 1
            log(f'[{i+1}/{len(todo)}] {"补抓" if REDO_WEAK else "第%d次尝试" % attempts} | {item.get("title","")[:34]} | {u[:72]}')
            rec = common.parse_policy_page(u, sess, config.DL_DIR)
            # 合并发现层元信息
            rec.update({'discover_title': item.get('title', ''),
                        'discover_snippet': item.get('snippet', ''),
                        'discover_engine': item.get('engine', ''),
                        'discover_query': item.get('query', ''),
                        'discover_unit': item.get('unit', ''),
                        'discover_utype': item.get('utype', ''),
                        'attempts': attempts,
                        'crawled_at': time.strftime('%Y-%m-%d %H:%M:%S')})
            if rec.get('status') == 'ok':
                n_fail = 0
            elif REDO_WEAK and prev.get('status') == 'ok':
                # 补抓失败不覆盖旧的好记录
                rec = dict(prev)
                rec['redo_note'] = f'{time.strftime("%m-%d %H:%M")} 补抓失败，保留原记录'
                log('  [keep-old] 补抓失败，保留原记录')
            else:
                n_fail += 1
                if attempts >= MAX_ATTEMPTS:
                    rec['status'] = 'abandoned'
                    rec['abandon_note'] = f'连续{attempts}次抓取失败，放弃重试'
                    log(f'  [abandon] {u[:70]}')
            records[u] = rec
            if (i + 1) % 10 == 0:
                save_json(config.DOCS_JSON, list(records.values()))
                ok_n = sum(1 for d in records.values() if d.get('status') == 'ok')
                log(f'  [checkpoint] 已保存 {len(records)} 条记录（成功 {ok_n}）')
            time.sleep(random.uniform(*config.DELAY_FETCH))
            if n_fail >= 20:
                log('[!] 连续20条失败，暂停300秒后继续')
                time.sleep(300)
                n_fail = 0
    except KeyboardInterrupt:
        log('[!] 收到中断信号，保存断点后退出（下次运行自动续爬）')
    save_json(config.DOCS_JSON, list(records.values()))
    ok = sum(1 for d in records.values() if d.get('status') == 'ok')
    ab = sum(1 for d in records.values() if d.get('status') == 'abandoned')
    log(f'抓取层完成：共 {len(records)} 条，成功 {ok} 条，放弃 {ab} 条 -> {config.DOCS_JSON}')


if __name__ == '__main__':
    main()
