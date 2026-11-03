# -*- coding: utf-8 -*-
"""
一键流水线：发现层 -> 抓取层 -> 输出层
- 三个环节全部支持断点续爬，任意时刻中断后重新运行本脚本即可从断点继续
- 中断方式：Ctrl+C 安全退出；断电/强杀则靠各环节的周期检查点（最多损失约5分钟进度）
"""
import os, sys, subprocess, time

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
STEPS = [
    ('discovery.py', '1/3 发现层：检索政策链接（断点续爬）'),
    ('fetch_pages.py', '2/3 抓取层：抓取政策原文（断点续爬）'),
    ('build_excel.py', '3/3 输出层：生成Excel（可重复执行）'),
]


def run_step(script):
    log = f'logs/{os.path.splitext(script)[0]}.log'
    with open(os.path.join(SCRIPTS_DIR, '..', log), 'a', encoding='utf-8') as lf:
        lf.write(f'\n===== {time.strftime("%Y-%m-%d %H:%M:%S")} 启动 {script} =====\n')
        lf.flush()
        code = subprocess.call([sys.executable, '-I', '-X', 'utf8', '-u',
                                os.path.join(SCRIPTS_DIR, script)],
                               cwd=SCRIPTS_DIR, stdout=lf, stderr=subprocess.STDOUT)
    return code


def main():
    print('=' * 56)
    print('长护险政策文本爬取流水线（全程断点续爬，可反复运行）')
    print('=' * 56)
    for script, desc in STEPS:
        print(f'\n>>> {desc}')
        code = run_step(script)
        if code != 0:
            print(f'[!] {script} 异常退出（code={code}）。已保存断点，重新运行本脚本可续爬。')
            sys.exit(code)
    print('\n[OK] 全流程完成。最终输出：长护险政策文本汇总.xlsx')


if __name__ == '__main__':
    main()
