import os
import sys
import random
import string
import socket
import secrets
import io
import zipfile
import threading
from functools import wraps
from urllib.parse import urlparse, urljoin

from flask import Flask, send_from_directory, request, redirect, url_for, Response, session, abort, send_file
from dotenv import load_dotenv
from flask_talisman import Talisman
from werkzeug.utils import secure_filename
from markupsafe import escape

# .env の読み込み
load_dotenv()

app = Flask(__name__)
# セッション用 secret_key（.env から取得、なければランダム生成）
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))

# Talisman の初期化（HTTP環境でも利用可能）
Talisman(
    app,
    force_https=False,
    session_cookie_secure=False,
    content_security_policy={
        'default-src': ["'self'"],
        'script-src': ["'self'"],
        'style-src': ["'self'", "https:"]
    }
)

# ファイル格納ディレクトリ
FILE_DIRECTORY = "./files"

# ファイル・フォルダの公開状態を保持する辞書
file_status = {}
# レースコンディション対策用のロック（再帰的にロックできるように RLock を利用）
file_status_lock = threading.RLock()

def initialize_file_status():
    """
    FILE_DIRECTORY 以下の全アイテムを再帰的に走査し、
    新規アイテムに対してデフォルト（非公開）の公開状態を設定する。
    """
    with file_status_lock:
        for root, dirs, files in os.walk(FILE_DIRECTORY):
            rel_root = os.path.relpath(root, FILE_DIRECTORY)
            if rel_root == ".":
                rel_root = ""
            for d in dirs:
                path = os.path.join(rel_root, d).lstrip(os.sep)
                if path not in file_status:
                    file_status[path] = False
            for f in files:
                path = os.path.join(rel_root, f).lstrip(os.sep)
                if path not in file_status:
                    file_status[path] = False

def safe_join(directory, path):
    """
    ユーザー入力をサニタイズし、directory 内の安全なパスを生成する。
    ※secure_filenameはファイル名のサニタイズ用なので、パスは各要素ごとに処理する。
    """
    parts = path.split(os.sep)
    safe_parts = [secure_filename(part) for part in parts]
    safe_path = os.path.join(*safe_parts)
    final_path = os.path.join(directory, safe_path)
    # 絶対パスに変換し、指定ディレクトリ内にあるか確認
    if os.path.commonpath([os.path.abspath(final_path), os.path.abspath(directory)]) != os.path.abspath(directory):
        raise Exception("無効なパス")
    return final_path

def get_lan_ip():
    """
    ホスト名から取得できるIPアドレス群の中から、192.168.で始まるIPを返す。
    見つからなければ、ソケット接続で得たIPを返す。
    """
    try:
        hostname = socket.gethostname()
        ips = socket.gethostbyname_ex(hostname)[2]
        for ip in ips:
            if ip.startswith("192.168."):
                return ip
    except Exception:
        pass
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

# 管理者認証情報（.env から取得）
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "password")
# 管理画面のパス（.env で指定されなければランダムな16文字）
ADMIN_ROUTE = os.environ.get("ADMIN_ROUTE")
if not ADMIN_ROUTE:
    ADMIN_ROUTE = ''.join(random.choices(string.ascii_letters + string.digits, k=16))

def check_auth(username, password):
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def authenticate():
    return Response('認証が必要です', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Cache-Control'] = 'no-store'
    return response

def generate_csrf_token():
    token = secrets.token_hex(16)
    session['csrf_token'] = token
    return token

def load_top_items():
    """
    FILE_DIRECTORY直下のアイテムのみをリストアップする。
    """
    items = []
    try:
        for item in sorted(os.listdir(FILE_DIRECTORY)):
            items.append(item)
    except Exception:
        pass
    return items

def propagate_public_status():
    """
    管理者でフォルダが公開に更新された場合、そのフォルダ内の全アイテムも公開にする。
    """
    with file_status_lock:
        for path in list(file_status.keys()):
            abs_path = os.path.join(FILE_DIRECTORY, path)
            if os.path.isdir(abs_path) and file_status.get(path, False):
                for other in file_status:
                    if other != path and other.startswith(path + os.sep):
                        file_status[other] = True

def safe_redirect(target):
    """
    外部サイトへのリダイレクトを防ぐため、内部パスのみ許可する。
    """
    if not target or urlparse(target).netloc != "":
        target = url_for("browse", subpath="")
    return redirect(target)

# ブラウズ画面：指定されたサブパスのディレクトリ内の公開アイテムを一覧表示
@app.route("/", defaults={"subpath": ""})
@app.route("/browse/<path:subpath>")
def browse(subpath):
    initialize_file_status()
    try:
        abs_path = safe_join(FILE_DIRECTORY, subpath)
    except Exception:
        return "無効なパスです", 400

    if not os.path.isdir(abs_path):
        return "ディレクトリが見つかりません", 404

    items = []
    for item in os.listdir(abs_path):
        rel_item = os.path.join(subpath, item).lstrip(os.sep)
        with file_status_lock:
            if file_status.get(rel_item, False):
                full_path = os.path.join(abs_path, item)
                item_type = "dir" if os.path.isdir(full_path) else "file"
                items.append((item, item_type))

    html = "<h1>ファイル一覧</h1>"
    if subpath:
        parent = os.path.dirname(subpath)
        html += f'<a href="{url_for("browse", subpath=parent)}">[..]</a><br>'
    html += "<ul>"
    for name, typ in items:
        safe_name = escape(name)
        rel_item = os.path.join(subpath, name).lstrip(os.sep)
        if typ == "dir":
            link = url_for("browse", subpath=rel_item)
        else:
            link = url_for("download", subpath=rel_item)
        html += f'<li><a href="{link}">{safe_name} ({typ})</a></li>'
    html += "</ul>"
    return html

# ダウンロードエンドポイント：ファイルはそのまま送信、ディレクトリはZIP圧縮して送信
@app.route("/download/<path:subpath>")
def download(subpath):
    initialize_file_status()
    try:
        abs_path = safe_join(FILE_DIRECTORY, subpath)
    except Exception:
        return "無効なパスです", 400

    if not os.path.exists(abs_path):
        return "アイテムが見つかりません", 404

    with file_status_lock:
        if not file_status.get(subpath, False):
            return "このアイテムは現在非公開です", 403

    if os.path.isfile(abs_path):
        directory = os.path.dirname(abs_path)
        filename = os.path.basename(abs_path)
        return send_from_directory(directory, filename, as_attachment=True)
    elif os.path.isdir(abs_path):
        # ZIP圧縮処理（ZIP Slip 対策、シンボリックリンク除外）
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(abs_path):
                for file in files:
                    abs_file = os.path.join(root, file)
                    if os.path.islink(abs_file):
                        continue
                    rel_file = os.path.relpath(abs_file, abs_path)
                    if ".." in rel_file:
                        continue
                    zf.write(abs_file, arcname=rel_file)
        memory_file.seek(0)
        zip_filename = secure_filename(os.path.basename(os.path.normpath(abs_path))) + ".zip"
        return send_file(memory_file, download_name=zip_filename, as_attachment=True)
    else:
        return "不正なアイテムです", 400

# 管理者インターフェース：FILE_DIRECTORY直下のアイテムのみを一覧表示・更新
@app.route("/" + ADMIN_ROUTE, methods=["GET", "POST"])
@requires_auth
def admin():
    initialize_file_status()
    if request.method == "POST":
        token = request.form.get("csrf_token", "")
        if not token or token != session.get("csrf_token", ""):
            abort(400, "CSRFトークンが存在しないか無効です")
        with file_status_lock:
            for item in load_top_items():
                # チェックボックスの値により公開状態を更新
                file_status[item] = (request.form.get(item) == "on")
            propagate_public_status()
        return safe_redirect(url_for("admin"))
    
    csrf_token = generate_csrf_token()
    items = load_top_items()
    html = "<h1>管理者インターフェース</h1>"
    html += "<form method='POST'>"
    html += f'<input type="hidden" name="csrf_token" value="{csrf_token}">'
    html += "<table border='1'><tr><th>アイテム</th><th>公開状態</th></tr>"
    with file_status_lock:
        for item in items:
            safe_item = escape(item)
            checked = "checked" if file_status.get(item, False) else ""
            html += f"<tr><td>{safe_item}</td><td><input type='checkbox' name='{safe_item}' {checked}></td></tr>"
    html += "</table>"
    html += "<input type='submit' value='更新'>"
    html += "</form>"
    html += '<br><a href="' + url_for("browse", subpath="") + '">ファイル一覧へ戻る</a>'
    return html

if __name__ == "__main__":
    if not os.path.exists(FILE_DIRECTORY):
        os.makedirs(FILE_DIRECTORY)
    port = 5000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("ポート番号は整数で指定してください")
            sys.exit(1)
    local_ip = get_lan_ip()
    print(f"管理者パネルのURL: http://{local_ip}:{port}/{ADMIN_ROUTE}")
    # 本番環境では debug モードを無効化（RCE対策）
    app.run(host="0.0.0.0", port=port, debug=False)
