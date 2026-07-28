# -*- coding: utf-8 -*-
"""学位英语学习系统 - 本地同步服务器

双击「启动学习系统.bat」运行。
手机/平板连同一 Wi-Fi，浏览器输入窗口显示的地址即可。
进度按用户保存在 users/ 目录，多设备共享。
"""
from __future__ import annotations

import http.server
import io
import json
import os
import re
import socket
import socketserver
import sys
import threading
import webbrowser
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.join(BASE, 'users')
STATIC_DIR = os.path.join(BASE, 'static')
PORT = 5000
os.makedirs(USERS_DIR, exist_ok=True)

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _user_lock(name: str) -> threading.Lock:
    with _locks_guard:
        if name not in _locks:
            _locks[name] = threading.Lock()
        return _locks[name]


def safe_name(name: str) -> str:
    name = unquote(name or '').strip()
    name = re.sub(r'[^\w一-鿿\-]', '', name)
    return name[:20]


def user_file(name: str) -> str:
    return os.path.join(USERS_DIR, safe_name(name) + '.json')


def migrate_old_progress():
    old = os.path.join(BASE, 'progress.json')
    dst = user_file('默认')
    if os.path.exists(old) and not os.path.exists(dst):
        try:
            data = json.load(open(old, encoding='utf-8'))
            if data and data.get('words'):
                data.setdefault('updatedAt', 0)
                json.dump(data, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
        except Exception:
            pass


def read_user(name: str) -> dict:
    fp = user_file(name)
    if not name or not os.path.exists(fp):
        return {}
    try:
        with open(fp, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_user(name: str, data: dict) -> None:
    fp = user_file(name)
    tmp = fp + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, fp)


def list_materials() -> list[dict]:
    """列出资料夹中的 PDF，供前端打开（不自动解析成题库）。"""
    roots = [
        ('学位英语资料', os.path.join(BASE, '学位英语资料')),
        ('湖南省学位英语资料', os.path.join(BASE, '湖南省学位英语资料')),
    ]
    out = []
    for label, root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for fn in sorted(files):
                if not fn.lower().endswith('.pdf'):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, BASE).replace('\\', '/')
                out.append({
                    'group': label,
                    'name': fn,
                    'url': '/' + rel,
                })
    return out


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=BASE, **kw)

    def log_message(self, *a):
        pass

    def end_headers(self):
        # App（Capacitor https://localhost）跨域访问局域网 API 需要 CORS
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        path = urlparse(self.path).path.lower()
        if path.endswith(('.html', '.js', '.css')):
            self.send_header('Cache-Control', 'no-store')
        elif path.startswith('/api/'):
            self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _new_user(self, query: str):
        name = safe_name(parse_qs(query).get('user', [''])[0])
        if not name:
            return self._json({'ok': False, 'err': '名字无效'}, 400)
        with _user_lock(name):
            if not os.path.exists(user_file(name)):
                write_user(name, {
                    'settings': {'dailyNew': 25},
                    'words': {},
                    'days': {},
                    'extTasks': {},
                    'plan': {'extra': {}, 'settledThrough': None},
                    'updatedAt': 0,
                })
        return self._json({'ok': True, 'user': name})

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == '/api/users':
            names = [f[:-5] for f in os.listdir(USERS_DIR) if f.endswith('.json')]
            return self._json(sorted(names))
        if u.path == '/api/newuser':
            return self._new_user(u.query)
        if u.path == '/api/state':
            name = safe_name(parse_qs(u.query).get('user', [''])[0])
            with _user_lock(name):
                return self._json(read_user(name))
        if u.path == '/api/materials':
            return self._json(list_materials())
        if u.path == '/api/health':
            return self._json({'ok': True, 'time': datetime.now().isoformat(timespec='seconds')})
        if u.path == '/':
            self.path = '/学位英语学习系统.html'
            return super().do_GET()
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == '/api/newuser':
            return self._new_user(u.query)
        if u.path == '/api/state':
            name = safe_name(parse_qs(u.query).get('user', [''])[0])
            n = int(self.headers.get('Content-Length', 0))
            raw = self.rfile.read(n)
            if not name:
                return self._json({'ok': False, 'err': '用户无效'}, 400)
            try:
                incoming = json.loads(raw.decode('utf-8'))
                if not isinstance(incoming, dict):
                    raise ValueError('not object')
            except Exception:
                return self._json({'ok': False, 'err': 'JSON无效'}, 400)

            with _user_lock(name):
                current = read_user(name)
                cur_ts = int(current.get('updatedAt') or 0)
                in_ts = int(incoming.get('updatedAt') or 0)
                # 服务器更新且时间戳更新：拒绝覆盖，返回冲突
                if current and cur_ts > in_ts:
                    return self._json({'ok': False, 'conflict': True, 'state': current}, 409)
                if in_ts <= cur_ts:
                    incoming['updatedAt'] = cur_ts + 1
                write_user(name, incoming)
                return self._json({'ok': True, 'updatedAt': incoming['updatedAt']})
        self.send_response(404)
        self.end_headers()


def lan_ips() -> list[str]:
    """列出本机所有局域网 IPv4（排除回环/链路本地），VPN 虚拟网卡地址也会列出，按名称排序。"""
    ips = []
    try:
        for _, addrs in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = addrs[0]
            if ip.startswith(('127.', '169.254.')) or ip in ips:
                continue
            ips.append(ip)
    except Exception:
        pass
    if not ips:
        ips.append('127.0.0.1')
    return sorted(ips)


if __name__ == '__main__':
    migrate_old_progress()
    ips = lan_ips()
    print('=' * 50)
    print('  学位英语学习系统已启动')
    print(f'  电脑：http://localhost:{PORT}')
    for ip in ips:
        print(f'  手机/平板：http://{ip}:{PORT}')
    if len(ips) > 1:
        print('  有多个地址时，用手机 Wi-Fi 同网段的（一般 192.168.x.x 且与手机前三段相同）')
    print('  需同一 Wi-Fi；关闭本窗口即停止同步')
    print('  若手机打不开：检查 Windows 防火墙是否放行端口 5000')
    print('=' * 50)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(('', PORT), Handler) as httpd:
        webbrowser.open(f'http://localhost:{PORT}')
        httpd.serve_forever()
