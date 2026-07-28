# -*- coding: utf-8 -*-
"""把 Web 资源拷贝到 app/ 目录，供 Capacitor 打包（入口改名为 index.html）。

用法：py -3 _build_app.py
题库/词库/前端有更新后，重新跑一次本脚本再 npx cap sync 即可。
"""
import os
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(BASE, 'app')

FILES = ['vocab.json', 'questions.json', 'study.json']


def main():
    if os.path.isdir(APP):
        shutil.rmtree(APP)
    os.makedirs(APP)
    shutil.copyfile(os.path.join(BASE, '学位英语学习系统.html'), os.path.join(APP, 'index.html'))
    shutil.copytree(os.path.join(BASE, 'static'), os.path.join(APP, 'static'))
    for f in FILES:
        src = os.path.join(BASE, f)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(APP, f))
        else:
            print(f'[警告] 缺少 {f}')
    print('已生成 app/ ：index.html + static/ + ' + ', '.join(FILES))


if __name__ == '__main__':
    main()
