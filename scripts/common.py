# -*- coding: utf-8 -*-
"""公共工具：HTTP会话、URL规范化、政策页面解析（标题/时间/主体/文号/正文/附件）"""
import os, re, time, random, logging, html as htmlmod
from urllib.parse import urlparse, urljoin, parse_qs, urlunparse
import requests
from bs4 import BeautifulSoup
import config

UA_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
]

def log(msg):
    logging.getLogger('crawl').info(msg)
    print(msg, flush=True)

def new_session(engine=None):
    s = requests.Session()
    s.headers.update({
        'User-Agent': random.choice(UA_LIST),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.5',
        'Connection': 'keep-alive',
    })
    if engine == 'sogou':
        s.headers['Referer'] = 'https://www.sogou.com/'
    return s

def fetch(s, url, params=None, timeout=None, retries=None, delay=0, **kw):
    """带重试的GET，返回 response 或 None"""
    timeout = timeout or config.TIMEOUT
    retries = retries if retries is not None else config.MAX_RETRY
    for i in range(retries):
        try:
            if delay and i > 0:
                time.sleep(delay * (i + 1) + random.uniform(0.5, 2))
            r = s.get(url, params=params, timeout=timeout, **kw)
            if r.status_code in (403, 429):
                # 疑似触发反爬，等待后重试
                time.sleep(random.uniform(15, 40))
                continue
            return r
        except requests.RequestException as e:
            log(f'  [warn] fetch fail {url[:80]} err={e.__class__.__name__} try={i+1}')
            time.sleep(random.uniform(3, 8))
    return None

CHARSET_RE = re.compile(rb'charset\s*=\s*["\']?\s*([a-zA-Z0-9_-]+)', re.I)

def decode_page(r):
    """网页编码嗅探：meta声明 > HTTP头 > 严格UTF-8 > GB18030兜底"""
    data = r.content
    m = CHARSET_RE.search(data[:2048])
    declared = m.group(1).decode('ascii', 'ignore').lower() if m else ''
    if declared in ('utf-8', 'utf8'):
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            pass  # 声明与实际不符，走后续嗅探
    elif declared in ('gb2312', 'gbk', 'gb18030', 'gb-2312'):
        try:
            return data.decode('gb18030')
        except UnicodeDecodeError:
            pass
    hdr = (r.encoding or '').lower().replace('_', '-')
    if hdr in ('utf-8', 'utf8'):
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            pass
    try:
        return data.decode('utf-8')  # 严格解码成功即按UTF-8
    except UnicodeDecodeError:
        return data.decode('gb18030', 'replace')

def is_gov_domain(host):
    """判断是否政府官方域名（*.gov.cn 及其它政府机构域名）"""
    h = host.lower().rstrip('.')
    if h.endswith('.gov.cn') or h == 'gov.cn':
        return True
    if h in ('npc.gov.cn',):
        return True
    return False

def normalize_url(url):
    """URL规范化：去掉常见跟踪参数、统一小写主机名"""
    if not url:
        return ''
    url = url.strip().split('#')[0]
    p = urlparse(url)
    host = p.netloc.lower()
    # 去掉跟踪参数
    drop = {'sessionid', 'spm', 'from', 'source', 'wfr', 'ivk_sa', 'clicktime', 'platform', 'eqid', 'chksm'}
    qs = parse_qs(p.query, keep_blank_values=True)
    qs = {k: v for k, v in qs.items() if k.lower() not in drop and not k.lower().startswith('spm')}
    path = p.path.rstrip('/') or '/'
    q = '&'.join(f'{k}={v[0]}' for k, v in sorted(qs.items()))
    return urlunparse((p.scheme.lower(), host, path, '', q, ''))

# ---------- 正文容器候选选择器（覆盖主流政府网站CMS） ----------
CONTENT_SELECTORS = [
    'div.TRS_Editor', 'div.TRS_UEDITOR', 'div#UCAP-CONTENT', 'div.ucap-content',
    'div.pages_content', 'div.article-content', 'div.article_content', 'div.article-body',
    'div.article_con', 'div#zoom', 'div.zoom', 'div.wzcon', 'div.xl_content', 'div.content',
    'div.zw', 'div.zhengwen', 'div.detail-content', 'div.detail_content', 'div.main-text',
    'div.Custom_UnionStyle', 'div.view', 'div.news_content', 'div.text_con', 'div.content_box',
    'div#content', 'div.article', 'div.nr', 'td#zoom', 'div#zoomcon', 'div.zoomcon',
    'div.content_left', 'div.article_txt', 'div#fontzoom', 'div#zoomcontent',
]
NAV_WORDS = ['登录', '注册', '导航', '首页', '搜索', '当前位置', '无障碍', '长者版', '繁体', 'English',
             '公务邮箱', '智能问答', '我要收藏', '分享', '打印', '关闭窗口', '返回顶部', '网站地图',
             'copyright', '版权所有', 'ICP备', '公网安备', '主办单位', '承办单位']
ATTACH_RE = re.compile(r'\.(pdf|docx?|wps|xlsx?|zip|rar)$', re.I)

def clean_text(s):
    s = re.sub(r'[　\xa0]', ' ', s)
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\n\s*\n+', '\n', s)
    return s.strip()

BODY_KW_RE = re.compile(r'长期护理|长护|照护')

def extract_body(soup):
    """提取正文：已知选择器 > 含关键词div最优 > 文本密度回退；栏目列表页返回空"""
    for sel in CONTENT_SELECTORS:
        for node in soup.select(sel):
            t = clean_text(node.get_text('\n'))
            if len(t) >= 50 and (BODY_KW_RE.search(t) or len(t) > 300):
                return t
    # 回退1：含关键词的div，按 长度-导航词惩罚 选最优（跳过栏目列表页）
    best, best_score = '', -1
    for node in soup.select('div, article, section, td'):
        if not BODY_KW_RE.search(node.get_text(' ', strip=True)):
            continue
        if len(node.select('a[href]')) > 12:  # 链接过多说明是栏目/列表页
            continue
        t = clean_text(node.get_text('\n'))
        if len(t) < 80:
            continue
        nav = sum(t.count(w) for w in NAV_WORDS)
        score = len(t) - nav * 250
        if score > best_score:
            best, best_score = t, score
    if best:
        return best
    # 回退2：无嵌套div的叶子节点中文本最长且导航词最少的
    best, best_score = '', -1
    for node in soup.select('div, article, section, td'):
        if node.select('div'):
            continue
        t = clean_text(node.get_text('\n'))
        if len(t) < 150:
            continue
        nav = sum(t.count(w) for w in NAV_WORDS)
        score = len(t) - nav * 250
        if score > best_score:
            best, best_score = t, score
    return best

DATE_RE = re.compile(r'(20\d{2})[-年/.·](\d{1,2})[-月/.·](\d{1,2})日?')
DOCNO_RE = re.compile(r'([一-龥A-Za-z]{1,12}?〔20\d{2}〕\s*\d+\s*号)')

def norm_date(m):
    """DATE_RE匹配结果转规范日期，非法值（如2095-80-54）返回空串"""
    if not m:
        return ''
    try:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    except Exception:
        return ''
    if 1990 <= y <= 2036 and 1 <= mo <= 12 and 1 <= d <= 31:
        return f'{y:04d}-{mo:02d}-{d:02d}'
    return ''

def _clean_issuer(v):
    """清理主体值：去标点、去尾部粘连的日期/时间"""
    v = v.strip(' \t:：,，;；|、-—【】[]()（）')
    v = re.sub(r'(20\d{2}[-年/.]\d{1,2}[-月/.]\d{1,2}日?\s*[\d:：]*\s*)$', '', v).strip()
    v = re.sub(r'(浏览次数|点击次数|点击|编辑|责任编辑|供稿).*$', '', v).strip()
    return v.strip(' \t:：,，;；|、-—【】[]()（）')

ORG_KW_RE = re.compile(r'政府|局|部|委|厅|办|中心|委员会|保险')

def extract_meta(soup, full_text, url, title_tag):
    """提取 发表时间/发表主体/文号"""
    pub_date = ''
    # 1) meta标签
    for meta in soup.select('meta'):
        n = (meta.get('name') or '').lower()
        if n in ('pubdate', 'govdate', 'createdate', 'publishdate', 'release_date', 'date'):
            pub_date = norm_date(DATE_RE.search(meta.get('content', '')))
            if pub_date:
                break
    head = full_text[:2500]
    # 2) 文本中的“发布日期/发布时间/成文日期”等标注
    if not pub_date:
        m = re.search(r'(?:发布日期|发布时间|成文日期|公开日期|发稿时间)\s*[:：]?\s*' + DATE_RE.pattern, head)
        if m:
            pub_date = norm_date(DATE_RE.search(m.group(0)))
    # 2b) “来源：xxx2021-06-30”类粘连日期
    if not pub_date:
        m = re.search(r'来源[^\n:：]{0,30}?((?:20\d{2})[-年/.]\d{1,2}[-月/.]\d{1,2}日?)', head)
        if m:
            pub_date = norm_date(DATE_RE.search(m.group(1)))
    # 3) URL中的日期
    if not pub_date:
        m = re.search(r'/((20\d{2})(\d{2})(\d{2}))/', url) or re.search(r'[t_]((20\d{2})(\d{2})(\d{2}))', url)
        if m:
            g = m.groups()
            try:
                y, mo, d = int(g[-3]), int(g[-2]), int(g[-1])
                if 1990 <= y <= 2036 and 1 <= mo <= 12 and 1 <= d <= 31:
                    pub_date = f'{y:04d}-{mo:02d}-{d:02d}'
            except Exception:
                pass
    # 4) 全文首个合法日期兜底
    if not pub_date:
        pub_date = norm_date(DATE_RE.search(head))

    # 发表主体
    issuer = ''
    # 4.1) 明确的发文单位标注（权威）
    for label in ('发文单位', '发文机关', '发布机构', '发布单位', '印发单位', '成文单位', '来源单位', '信息来源'):
        m = re.search(label + r'\s*[:：]?\s*([^\s\n,，;；|）)]{2,40})', head)
        if m:
            v = _clean_issuer(m.group(1))
            if len(v) >= 2:
                issuer = v
                break
    # 4.2) “来源：xxx”标注（要求含机构关键词，排除报社等媒体）
    if not issuer:
        m = re.search(r'来源\s*[:：]\s*([^\s\n,，;；|）)]{2,40})', head)
        if m:
            v = _clean_issuer(m.group(1))
            if len(v) >= 2 and v not in ('本站', '本网', '本局', '互联网', '网络', '不详') and ORG_KW_RE.search(v):
                issuer = v
    # 4.3) meta contentsource
    if not issuer:
        for meta in soup.select('meta'):
            n = (meta.get('name') or '').lower()
            if n in ('contentsource', 'source', 'govsource') and meta.get('content', '').strip():
                c = _clean_issuer(meta.get('content', ''))
                if c and len(c) <= 40 and not c.isdigit() \
                        and not re.match(r'^[\w@. -]+$', c) and ORG_KW_RE.search(c):
                    issuer = c
                    break
    # 4.4) 从标题前缀推断（如“青岛市人民政府关于印发...”）
    if not issuer and title_tag:
        m = re.match(r'^([一-龥]{2,25}?(?:人民政府|政府办公厅|办公室|委员会|医疗保障局|医保局|人力资源|人社厅|人社部|民政厅|民政局|财政部|财政厅|财政局|卫健委|卫生健康|部|厅|局))', title_tag)
        if m:
            issuer = m.group(1)

    # 文号
    doc_no = ''
    m = re.search(r'(?:发文字号|文号)\s*[:：]?\s*' + DOCNO_RE.pattern, head)
    if m:
        doc_no = re.search(DOCNO_RE.pattern, m.group(0)).group(1)
    if not doc_no:
        ms = DOCNO_RE.findall(head[:1500])
        if ms:
            doc_no = max(ms, key=len)

    return pub_date, issuer, doc_no

def parse_policy_page(url, session, dl_dir):
    """抓取并解析单个政策页面，返回结果dict"""
    r = fetch(session, url)
    if r is None:
        return {'url': url, 'status': 'fetch_fail'}
    ct = r.headers.get('Content-Type', '')
    path = urlparse(url).path.lower()
    rec = {'url': url, 'status': 'ok', 'content_type': ct.split(';')[0].strip()}

    # PDF附件/文件直接处理
    if 'pdf' in ct or path.endswith('.pdf'):
        rec['file_type'] = 'PDF'
        return parse_pdf(url, r, session, dl_dir, rec)
    if 'word' in ct or re.search(r'\.(docx?|wps)$', path):
        rec['file_type'] = 'DOC'
        return parse_doc(url, r, session, dl_dir, rec)

    soup = BeautifulSoup(decode_page(r), 'lxml')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    title_tag = soup.title.get_text(strip=True) if soup.title else ''
    title_tag = re.sub(r'[_|—\-].{0,30}$', '', title_tag).strip()  # 去掉网站后缀
    full_text = clean_text(soup.get_text('\n'))
    body = extract_body(soup)
    pub_date, issuer, doc_no = extract_meta(soup, full_text, url, title_tag)

    # 附件链接
    atts = []
    for a in soup.select('a[href]'):
        h = a.get('href', '')
        if ATTACH_RE.search(h) and 'javascript' not in h:
            absu = urljoin(url, h)
            atts.append({'name': (a.get_text(strip=True) or os.path.basename(absu))[:80],
                         'url': absu, 'ext': re.search(ATTACH_RE, h).group(1).lower()})

    rec.update({'file_type': 'HTML', 'title': title_tag, 'body': body,
                'pub_date': pub_date, 'issuer': issuer, 'doc_no': doc_no,
                'attachments': atts, 'text_len': len(body or '')})
    return rec

def parse_pdf(url, r, session, dl_dir, rec):
    """下载并抽取PDF文本"""
    try:
        # 内容嗅探：确保真的是PDF（防止404/HTML页面被存为.pdf）
        sniff = r.content[:8]
        ct_ok = 'pdf' in r.headers.get('Content-Type', '').lower()
        if not ct_ok and not sniff.startswith(b'%PDF'):
            rec.update({'body': '', 'text_len': 0, 'status': 'not_pdf',
                        'pdf_error': '响应不是PDF文件（可能为错误页面或链接失效）'})
            return rec
        fname = os.path.basename(urlparse(url).path) or 'doc.pdf'
        fpath = os.path.join(dl_dir, fname)
        if not os.path.exists(fpath):
            with open(fpath, 'wb') as f:
                f.write(r.content)
        import pypdf
        reader = pypdf.PdfReader(fpath)
        txt = '\n'.join((p.extract_text() or '') for p in reader.pages)
        rec.update({'body': clean_text(txt), 'text_len': len(txt), 'pdf_path': fpath})
    except Exception as e:
        rec.update({'body': '', 'text_len': 0, 'pdf_error': str(e)[:200], 'status': 'pdf_fail'})
    return rec

def parse_doc(url, r, session, dl_dir, rec):
    """下载并抽取docx文本（doc老格式无法解析时仅保留链接）"""
    try:
        fname = os.path.basename(urlparse(url).path) or 'doc.docx'
        fpath = os.path.join(dl_dir, fname)
        if not os.path.exists(fpath):
            with open(fpath, 'wb') as f:
                f.write(r.content)
        import zipfile
        with zipfile.ZipFile(fpath) as z:
            xml = z.read('word/document.xml').decode('utf-8', 'ignore')
        t = re.sub(r'<w:p [^>]*>|<w:p>', '\n', xml)
        t = re.sub(r'<[^>]+>', '', t)
        t = htmlmod.unescape(t)
        rec.update({'body': clean_text(t), 'text_len': len(t), 'pdf_path': fpath})
    except Exception as e:
        rec.update({'body': '', 'text_len': 0, 'doc_error': str(e)[:200], 'status': 'doc_fail'})
    return rec
