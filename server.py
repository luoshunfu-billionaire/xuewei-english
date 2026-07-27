# -*- coding: utf-8 -*-
"""学位英语学习系统 - 本地同步服务器
双击「启动学习系统.bat」运行。手机/平板连同一 Wi-Fi，浏览器输入显示的地址即可。
支持多用户：每个用户一份进度，存在 users/ 目录下，各设备按用户名共享。
"""
import http.server, socketserver, json, os, socket, sys, io, webbrowser, re
from urllib.parse import urlparse, parse_qs, unquote
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = os.path.dirname(os.path.abspath(__file__))
USERS_DIR = os.path.join(BASE, 'users')
os.makedirs(USERS_DIR, exist_ok=True)
PORT = 5000

def safe_name(name):
    """清洗用户名，只保留中英文数字，防止路径穿越"""
    name = unquote(name or '').strip()
    name = re.sub(r'[^\w一-鿿\-]', '', name)
    return name[:20]

def user_file(name):
    return os.path.join(USERS_DIR, safe_name(name) + '.json')

def migrate_old_progress():
    """把旧单用户 progress.json 迁移为 users/默认.json"""
    old = os.path.join(BASE, 'progress.json')
    dst = user_file('默认')
    if os.path.exists(old) and not os.path.exists(dst):
        try:
            data = json.load(open(old, encoding='utf-8'))
            if data and data.get('words'):
                json.dump(data, open(dst, 'w', encoding='utf-8'), ensure_ascii=False)
        except Exception:
            pass

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=BASE, **kw)

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode('utf-8'))

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == '/api/users':
            names = [f[:-5] for f in os.listdir(USERS_DIR) if f.endswith('.json')]
            self._json(sorted(names))
        elif u.path == '/api/state':
            name = safe_name(parse_qs(u.query).get('user', [''])[0])
            data = {}
            fp = user_file(name)
            if name and os.path.exists(fp):
                try: data = json.load(open(fp, encoding='utf-8'))
                except Exception: data = {}
            self._json(data)
        elif self.path == '/':
            self.path = '/学位英语学习系统.html'
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == '/api/newuser':
            name = safe_name(parse_qs(u.query).get('user', [''])[0])
            if not name:
                return self._json({'ok': False, 'err': '名字无效'}, 400)
            fp = user_file(name)
            if not os.path.exists(fp):
                json.dump({'settings': {'dailyNew': 25}, 'words': {}, 'days': {}, 'extTasks': {}},
                          open(fp, 'w', encoding='utf-8'), ensure_ascii=False)
            return self._json({'ok': True, 'user': name})
        if u.path == '/api/state':
            name = safe_name(parse_qs(u.query).get('user', [''])[0])
            n = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(n)
            if not name:
                return self._json({'ok': False}, 400)
            try:
                json.loads(body)  # 校验是合法 JSON 才写入
                with open(user_file(name), 'wb') as f:
                    f.write(body)
                return self._json({'ok': True})
            except Exception:
                return self._json({'ok': False}, 400)
        self.send_response(404); self.end_headers()

def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

if __name__ == '__main__':
    migrate_old_progress()
    ip = lan_ip()
    print('=' * 46)
    print('  学位英语学习系统服务器已启动')
    print(f'  电脑使用：http://localhost:{PORT}')
    print(f'  手机/平板使用：http://{ip}:{PORT}')
    print('  （手机/平板需和电脑连同一个 Wi-Fi）')
    print('  关闭此窗口即停止同步')
    print('=' * 46)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(('', PORT), Handler) as httpd:
        webbrowser.open(f'http://localhost:{PORT}')
        httpd.serve_forever()
