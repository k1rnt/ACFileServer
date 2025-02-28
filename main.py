import os
import sys
import random
import string
import socket
import secrets
from functools import wraps
from flask import Flask, send_from_directory, request, redirect, url_for, Response, session, abort
from dotenv import load_dotenv
from flask_talisman import Talisman
from werkzeug.utils import secure_filename
from markupsafe import escape

# .env の読み込み
load_dotenv()

app = Flask(__name__)
# セッション用 secret_key（.env から取得、なければランダム生成）
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(16))

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

# ファイルの公開状態（メモリ上の辞書）
# True: 公開, False: 非公開
file_status = {}

def load_files():
    """
    指定ディレクトリ内のファイル一覧を取得します。
    """
    files = []
    try:
        for f in os.listdir(FILE_DIRECTORY):
            if os.path.isfile(os.path.join(FILE_DIRECTORY, f)):
                files.append(f)
    except Exception:
        pass
    return files

def initialize_file_status():
    """
    新規ファイルがあれば、デフォルト（非公開）状態で辞書に追加します。
    """
    files = load_files()
    for f in files:
        if f not in file_status:
            file_status[f] = False

# 管理者認証情報（.env から取得）
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "password")
# 管理画面のパス（.env で指定されなければランダムな16文字）
ADMIN_ROUTE = os.environ.get("ADMIN_ROUTE")
if not ADMIN_ROUTE:
    ADMIN_ROUTE = ''.join(random.choices(string.ascii_letters + string.digits, k=16))

def get_lan_ip():
    """
    ホスト名から取得できるIPアドレス群の中から、192.168.で始まるIPを返す。
    見つからなければソケット接続で得たIPを返す。
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

def check_auth(username, password):
    """
    管理者認証のチェック
    """
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def authenticate():
    """
    認証が必要な場合のレスポンスを返す
    """
    return Response(
        '認証が必要です', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    """
    管理画面へのアクセスに認証を要求するデコレータ
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.after_request
def set_security_headers(response):
    """
    セキュリティヘッダーを設定
    """
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.route("/")
def index():
    """
    エンドユーザー向けのファイル一覧画面（公開ファイルのみ）
    """
    initialize_file_status()
    public_files = [f for f in load_files() if file_status.get(f, False)]
    html = "<h1>ファイル一覧</h1><ul>"
    for f in public_files:
        safe_f = escape(f)
        html += f'<li><a href="/download/{safe_f}">{safe_f}</a></li>'
    html += "</ul>"
    return html

@app.route("/download/<filename>")
def download(filename):
    """
    指定ファイルのダウンロード処理
    """
    safe_filename = secure_filename(filename)
    if safe_filename != filename:
        return "不正なファイル名です", 400
    file_path = os.path.join(FILE_DIRECTORY, filename)
    if not os.path.exists(file_path):
        return "ファイルが見つかりません", 404
    if not file_status.get(filename, False):
        return "このファイルは現在非公開です", 403
    return send_from_directory(FILE_DIRECTORY, filename, as_attachment=True)

def generate_csrf_token():
    """
    CSRF 対策用のトークンを生成し、セッションに保存する
    """
    token = secrets.token_hex(16)
    session['csrf_token'] = token
    return token

@app.route("/" + ADMIN_ROUTE, methods=["GET", "POST"])
@requires_auth
def admin():
    """
    管理者向けインターフェース
      GET: ファイル一覧と公開状態を表示
      POST: CSRF トークン検証後、公開状態を更新
    """
    initialize_file_status()
    if request.method == "POST":
        # CSRF トークン検証
        token = request.form.get("csrf_token", "")
        if not token or token != session.get("csrf_token", ""):
            abort(400, "CSRF token missing or invalid")
        # ファイルの公開状態更新
        files = load_files()
        for filename in files:
            file_status[filename] = (request.form.get(filename) == "on")
        return redirect(url_for("admin"))
    
    csrf_token = generate_csrf_token()
    html = "<h1>管理者インターフェース</h1>"
    html += "<form method='POST'>"
    html += f'<input type="hidden" name="csrf_token" value="{csrf_token}">'
    html += "<table border='1'><tr><th>ファイル名</th><th>公開状態</th></tr>"
    for f in load_files():
        safe_f = escape(f)
        checked = "checked" if file_status.get(f, False) else ""
        html += f"<tr><td>{safe_f}</td><td><input type='checkbox' name='{safe_f}' {checked}></td></tr>"
    html += "</table>"
    html += "<input type='submit' value='更新'>"
    html += "</form>"
    html += '<br><a href="/">ファイル一覧へ戻る</a>'
    return html

if __name__ == "__main__":
    if not os.path.exists(FILE_DIRECTORY):
        os.makedirs(FILE_DIRECTORY)
    
    # コマンドライン引数でポート番号を指定（指定がない場合は5000）
    port = 5000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("ポート番号は整数で指定してください")
            sys.exit(1)
    
    local_ip = get_lan_ip()
    print(f"管理者パネルのURL: http://{local_ip}:{port}/{ADMIN_ROUTE}")
    app.run(host="0.0.0.0", port=port)
