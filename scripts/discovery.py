# -*- coding: utf-8 -*-
"""
发现层 v2：三引擎轮换 + 智能冷却，稳健检索长护险政策文本链接
- 引擎: 搜狗 / 必应 / 360，轮换使用，每个引擎独立会话与限速
- 触发验证码/封禁时该引擎冷却15-30分钟，自动切到其它引擎
- 直爬渠道: 国家医保局长护险专栏 + 中国政府网政策库 + 栏目页扩展
- 所有结果仅保留 *.gov.cn 政府官方域名，断点续传
"""
import os, sys, json, time, random, re, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import config, common

logger = logging.getLogger('crawl')
logger.setLevel(logging.INFO)
_fh = logging.FileHandler(config.LOG_FILE, encoding='utf-8')
_fh.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
logger.addHandler(_fh)
_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(_sh)

URLS_JSON = config.URLS_JSON
KEYWORD_RE = re.compile(r'长期护理|长护险')
CAPTCHA_RE = re.compile(r'验证码|antispider|请输入验证|security verification', re.I)
GOV_RE = re.compile(r'([\w-]+\.)+gov\.cn')


def log(msg):
    logger.info(msg)


def load_seen():
    if os.path.exists(URLS_JSON):
        try:
            with open(URLS_JSON, encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            # 文件损坏（如休眠中断写入）：尝试恢复第一段完整JSON
            with open(URLS_JSON, encoding='utf-8') as f:
                text = f.read()
            try:
                data, _ = json.JSONDecoder().raw_decode(text)
                log(f'[warn] {URLS_JSON} 文件不完整，已恢复前 {len(data)} 条记录')
                return data
            except Exception:
                log(f'[error] {URLS_JSON} 无法解析')
                return []
    return []


def save_seen(seen):
    os.makedirs(os.path.dirname(URLS_JSON), exist_ok=True)
    tmp = URLS_JSON + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(seen, f, ensure_ascii=False, indent=1)
    os.replace(tmp, URLS_JSON)  # 原子替换，避免中断写坏文件


def norm_key(url):
    return common.normalize_url(url)


def gov_hint(text):
    m = GOV_RE.search(text or '')
    return m.group(0) if m else ''


# ==================== 引擎定义 ====================
class Engine:
    def __init__(self, name, delay_range, resolve_range=(2, 4)):
        self.name = name
        self.sess = common.new_session()
        self.delay_range = delay_range
        self.resolve_range = resolve_range
        self.cooldown_until = 0.0

    def ok(self):
        return time.time() >= self.cooldown_until

    def cool(self, minutes):
        self.cooldown_until = time.time() + minutes * 60
        log(f'  [engine] {self.name} 冷却 {minutes} 分钟至 {time.strftime("%H:%M", time.localtime(self.cooldown_until))}')
        self.sess = common.new_session()

    def pause(self):
        d = random.uniform(*self.delay_range)
        time.sleep(d)

    def resolve_pause(self):
        time.sleep(random.uniform(*self.resolve_range))


def _parse_sogou(html):
    if CAPTCHA_RE.search(html[:3000]):
        return None, 'captcha'
    soup = BeautifulSoup(html, 'lxml')
    items = []
    for blk in soup.select('div.vrwrap, div.rb'):
        a = blk.select_one('h3 a')
        if not a:
            continue
        blk_text = blk.get_text(' ', strip=True)
        items.append({'title': a.get_text(strip=True), 'href': a.get('href', ''),
                      'snippet': blk_text[:200], 'domain_hint': gov_hint(blk_text)})
    return items, 'ok'


def _resolve_sogou(eng, href, expect_domain=''):
    if not href.startswith('/link'):
        return href
    eng.resolve_pause()
    r = common.fetch(eng.sess, 'https://www.sogou.com' + href, retries=2)
    if r is None:
        return ''
    m = re.search(r'https?://[^"\'\s<>\\]+?\.gov\.cn[^"\'\s<>\\]*', r.text)
    if not m:
        return ''
    u = m.group(0).replace('\\u002F', '/').replace('\\/', '/')
    return u if (not expect_domain or expect_domain in u) else ''


def _parse_bing(html):
    if 'b_algo' not in html:
        return None, 'blocked'
    soup = BeautifulSoup(html, 'lxml')
    items = []
    for blk in soup.select('li.b_algo'):
        a = blk.select_one('h2 a')
        if not a:
            continue
        cap = blk.select_one('.b_caption')
        items.append({'title': a.get_text(strip=True), 'href': a.get('href', ''),
                      'snippet': cap.get_text(' ', strip=True)[:200] if cap else '',
                      'domain_hint': ''})
    return items, 'ok'


def _parse_so360(html):
    if CAPTCHA_RE.search(html[:3000]):
        return None, 'captcha'
    soup = BeautifulSoup(html, 'lxml')
    items = []
    for blk in soup.select('li.res-list'):
        a = blk.select_one('h3 a')
        if not a:
            continue
        blk_text = blk.get_text(' ', strip=True)
        items.append({'title': a.get_text(strip=True), 'href': a.get('href', ''),
                      'snippet': blk_text[:200], 'domain_hint': gov_hint(blk_text)})
    return items, 'ok'


def _resolve_so360(eng, href, expect_domain=''):
    if '/link' not in href:
        return href
    eng.resolve_pause()
    r = common.fetch(eng.sess, href, retries=2, allow_redirects=True)
    if r is None:
        return ''
    if common.is_gov_domain(urlparse(r.url).netloc):
        return r.url
    m = re.search(r'https?://[^"\'\s<>\\]+?\.gov\.cn[^"\'\s<>\\]*', r.text[:8000])
    if not m:
        return ''
    u = m.group(0)
    return u if (not expect_domain or expect_domain in u) else ''


def _search_bing(eng, q, offset):
    eng.pause()
    for host in ('https://cn.bing.com/search', 'https://www.bing.com/search'):
        r = common.fetch(eng.sess, host,
                         params={'q': q, 'first': offset + 1, 'mkt': 'zh-CN'}, retries=2)
        if r is None:
            continue
        items, st = _parse_bing(r.text)
        if st == 'ok':
            return items, 'ok'
    return None, 'blocked'


def _search_sogou(eng, q, page):
    eng.pause()
    r = common.fetch(eng.sess, 'https://www.sogou.com/web',
                     params={'query': q, 'page': page}, retries=2)
    if r is None:
        return None, 'http_fail'
    return _parse_sogou(r.text)


def _search_so360(eng, q, page):
    eng.pause()
    r = common.fetch(eng.sess, 'https://www.so.com/s',
                     params={'q': q, 'pn': page}, retries=2)
    if r is None:
        return None, 'http_fail'
    return _parse_so360(r.text)


def search(eng, q, page_or_offset, engine_idx):
    """按引擎类型执行搜索，返回 (items, status)"""
    if engine_idx == 0:
        return _search_sogou(eng, q, page_or_offset)
    if engine_idx == 1:
        return _search_bing(eng, q, page_or_offset)
    return _search_so360(eng, q, page_or_offset)


def resolve(eng, item, engine_idx):
    if engine_idx == 0:
        return _resolve_sogou(eng, item['href'], item['domain_hint'])
    if engine_idx == 1:
        return item['href']
    return _resolve_so360(eng, item['href'], item['domain_hint'])


# ==================== 任务构造 ====================
def task_id(unit, utype, query, page):
    """基于任务内容的稳定ID（与顺序无关，配置不变则重启后ID不变）"""
    import hashlib
    key = f'{unit}|{utype}|{query}|{page}'
    return hashlib.md5(key.encode('utf-8')).hexdigest()[:12]


def build_tasks():
    tasks = []
    for unit, utype, prio in config.build_units():
        queries = config.build_queries(unit, utype)
        pages = config.SEARCH_PAGES_PER_QUERY
        if prio == 1:
            pass  # 高优先级：全部查询
        else:
            queries = queries[:2]  # 低优先级城市只跑2个核心查询
        for q in queries:
            for p in range(1, pages + 1):
                tasks.append({'unit': unit, 'utype': utype, 'prio': prio, 'query': q,
                              'page': p, 'tries': 0, 'id': task_id(unit, utype, q, p)})
    # 高优先级在前
    tasks.sort(key=lambda t: t['prio'])
    return tasks


def process_task(eng, task, engine_idx, seen, seen_keys, lock):
    """用指定引擎处理一个检索任务，返回 'done' / 'captcha' / 'cooling'"""
    q, page = task['query'], task['page']
    if not eng.ok():
        return 'cooling'
    items, st = search(eng, q, page, engine_idx)
    if st == 'captcha' or st == 'blocked':
        eng.cool(random.randint(15, 30))
        return 'captcha'
    if items is None:
        time.sleep(15)
        return 'retry'
    for it in items:
        if not KEYWORD_RE.search(it['title']) and not KEYWORD_RE.search(it['snippet']):
            continue
        if it['domain_hint'] and not common.is_gov_domain(it['domain_hint']):
            continue
        if engine_idx != 1:  # sogou/so360需要解析跳转
            real = resolve(eng, it, engine_idx)
            if not real or not common.is_gov_domain(urlparse(real).netloc):
                continue
        else:
            real = it['href']
            if not real.startswith('http') or not common.is_gov_domain(urlparse(real).netloc):
                continue
        k = norm_key(real)
        with lock:
            if k in seen_keys:
                continue
            seen_keys.add(k)
            seen.append({'url': real, 'title': it['title'], 'snippet': it['snippet'],
                         'engine': eng.name, 'query': q, 'unit': task['unit'], 'utype': task['utype']})
        log(f'  + [{task["unit"]}] {it["title"][:36]} | {real[:70]}')
    return 'done'


def worker(idx, eng, q, seen, seen_keys, lock, done_counter, state, total):
    while True:
        task = q.get()
        if task is None:
            return
        if done_counter[0] >= total:
            return
        try:
            if task.get('tries', 0) >= 3:
                with lock:
                    done_counter[0] += 1
                    state.setdefault('done_ids', []).append(task['id'])
                continue
            st = process_task(eng, task, idx, seen, seen_keys, lock)
            if st == 'done':
                with lock:
                    done_counter[0] += 1
                    state.setdefault('done_ids', []).append(task['id'])
            elif st in ('captcha', 'cooling', 'retry'):
                task['tries'] = task.get('tries', 0) + 1
                if st == 'captcha':
                    time.sleep(random.uniform(5, 15))
                elif st == 'cooling':
                    time.sleep(random.uniform(30, 60))
                q.put(task)  # 放回队尾，由其它引擎线程再试
        except Exception as e:
            log(f'  [err] 任务异常 {task.get("unit")}/{task.get("query")}: {e}')
            with lock:
                done_counter[0] += 1
                state.setdefault('done_ids', []).append(task['id'])


# ==================== 官方栏目直爬 ====================
def run_nhsa(seen, seen_keys):
    base = 'https://www.nhsa.gov.cn'
    cols = [('https://www.nhsa.gov.cn/col/col194/index.html', 'national', '国家层面'),
            ('https://www.nhsa.gov.cn/col/col196/index.html', 'national', '国家层面'),
            ('https://www.nhsa.gov.cn/col/col197/index.html', 'national', '国家层面')]
    sess = common.new_session()
    for col_url, utype, unit in cols:
        for pg in range(1, 6):
            u = col_url if pg == 1 else col_url.replace('index.html', f'index_{pg-1}.html')
            r = common.fetch(sess, u, retries=2)
            if r is None or r.status_code != 200:
                break
            soup = BeautifulSoup(r.content, 'lxml')
            got = 0
            for a in soup.select('a[href]'):
                t, h = a.get_text(strip=True), a.get('href', '')
                if not KEYWORD_RE.search(t) or 'art_' not in h or 'javascript' in h:
                    continue
                absu = h if h.startswith('http') else base + h
                k = norm_key(absu)
                if k in seen_keys:
                    continue
                seen_keys.add(k)
                seen.append({'url': absu, 'title': t, 'snippet': '', 'engine': 'nhsa',
                             'query': 'nhsa长护险专栏', 'unit': unit, 'utype': utype})
                log(f'  + [NHSA] {t[:40]} | {absu[:70]}')
                got += 1
            time.sleep(random.uniform(3, 6))
            if got == 0:
                break


def run_govcn(seen, seen_keys):
    sess = common.new_session()
    for list_url in ('https://www.gov.cn/zhengce/zuixin/', 'https://www.gov.cn/zhengce/zhengceku/'):
        for pg in range(1, 13):
            u = list_url if pg == 1 else list_url + f'index_{pg}.htm'
            r = common.fetch(sess, u, retries=2)
            if r is None or r.status_code != 200:
                break
            soup = BeautifulSoup(r.content, 'lxml')
            got = 0
            for a in soup.select('a[href]'):
                t, h = a.get_text(strip=True), a.get('href', '')
                if not KEYWORD_RE.search(t) or ('/zhengce/' not in h and '/yaowen/' not in h):
                    continue
                absu = h if h.startswith('http') else 'https://www.gov.cn' + h
                k = norm_key(absu)
                if k in seen_keys:
                    continue
                seen_keys.add(k)
                seen.append({'url': absu, 'title': t, 'snippet': '', 'engine': 'govcn',
                             'query': 'gov.cn政策库', 'unit': '国家层面', 'utype': 'national'})
                log(f'  + [GOVCN] {t[:40]} | {absu[:70]}')
                got += 1
            time.sleep(random.uniform(3, 6))
            if got == 0 and pg > 2:
                break


def looks_like_column(u):
    p = urlparse(u).path
    return p.endswith('/') and not re.search(r'\.(htm|html|shtml|aspx|jsp)$', p)


def expand_columns(seen, seen_keys, max_rounds=3):
    sess = common.new_session()
    for rnd in range(max_rounds):
        cols = [x for x in seen if looks_like_column(x['url']) and not x.get('_expanded')]
        log(f'[expand] 第{rnd+1}轮：{len(cols)} 个候选栏目页')
        new_cnt = 0
        for c in cols:
            c['_expanded'] = True
            r = common.fetch(sess, c['url'], retries=2)
            if r is None:
                continue
            soup = BeautifulSoup(r.content, 'lxml')
            for a in soup.select('a[href]'):
                t, h = a.get_text(strip=True), a.get('href', '')
                if not KEYWORD_RE.search(t) or not h or 'javascript' in h:
                    continue
                absu = urljoin(c['url'], h)
                if not common.is_gov_domain(urlparse(absu).netloc):
                    continue
                k = norm_key(absu)
                if k in seen_keys:
                    continue
                seen_keys.add(k)
                seen.append({'url': absu, 'title': t, 'snippet': '', 'engine': 'column',
                             'query': f'栏目扩展:{c["url"][:60]}', 'unit': c.get('unit', ''),
                             'utype': c.get('utype', '')})
                new_cnt += 1
            time.sleep(random.uniform(2, 4))
        log(f'[expand] 第{rnd+1}轮新增 {new_cnt} 条')
        if new_cnt == 0:
            break
        save_seen(seen)


STATE_JSON = config.STATE_JSON

def load_state():
    if os.path.exists(STATE_JSON):
        with open(STATE_JSON, encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_state(state):
    tmp = STATE_JSON + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False)
    os.replace(tmp, STATE_JSON)  # 原子替换

def main():
    import threading, queue
    seen = load_seen()
    seen_keys = {norm_key(x['url']) for x in seen}
    state = load_state()
    log(f'已载入 {len(seen)} 条既有链接，开始增量发现（三引擎并行，断点续爬）')

    engines = [Engine('sogou', (12, 18)), Engine('bing', (8, 13)), Engine('so360', (10, 15))]
    # 断点续爬：按稳定任务ID过滤掉已完成的检索任务
    done_ids = set(state.get('done_ids', []))
    if not done_ids and state.get('tasks_done'):  # 兼容旧版状态格式
        all_tasks = build_tasks()
        done_ids = {t['id'] for t in all_tasks[:state['tasks_done']]}
    tasks = [t for t in build_tasks() if t['id'] not in done_ids]
    total = len(tasks)
    log(f'剩余任务: {total}（已完成 {len(done_ids)} 个检索任务）')
    if total == 0:
        log('无剩余检索任务，跳过搜索引擎扫描')

    q = queue.Queue()
    for t in tasks:
        q.put(t)
    lock = threading.Lock()
    done_counter = [0]
    threads = []
    for idx, eng in enumerate(engines):
        th = threading.Thread(target=worker, args=(idx, eng, q, seen, seen_keys, lock, done_counter, state, total),
                              daemon=True)
        th.start()
        threads.append(th)
    last_save = time.time()
    try:
        while done_counter[0] < total:
            time.sleep(30)
            if not any(th.is_alive() for th in threads):
                log(f'[!] 所有worker线程已退出但任务未完成（完成 {done_counter[0]}/{total}），保存状态后停止')
                break
            with lock:
                cur = len(seen)
            log(f'[hb] 完成 {done_counter[0]}/{total} 任务 | 累计链接 {cur}')
            if time.time() - last_save > 300:
                with lock:
                    save_seen(seen)
                    save_state(state)
                last_save = time.time()
    except KeyboardInterrupt:
        log('[!] 收到中断信号，保存断点后退出（下次运行自动续爬）')
    for _ in engines:
        q.put(None)
    for th in threads:
        th.join(timeout=10)
    with lock:
        save_seen(seen)
        save_state(state)
    log('搜索引擎扫描完成（或已保存断点）')
    log('搜索引擎扫描完成，开始官方栏目直爬...')
    run_nhsa(seen, seen_keys)
    run_govcn(seen, seen_keys)
    save_seen(seen)
    log('开始栏目页扩展...')
    expand_columns(seen, seen_keys)
    save_seen(seen)
    log(f'发现层完成，共 {len(seen)} 条唯一链接 -> {URLS_JSON}')


if __name__ == '__main__':
    main()
