import os
import sys
import random
import string
import socket
from functools import wraps
from flask import Flask, send_from_directory, request, redirect, url_for, Response
from dotenv import load_dotenv

# .env ファイルの内容を読み込み
load_dotenv()

app = Flask(__name__)

# ダウンロード対象のファイルが格納されているディレクトリ
FILE_DIRECTORY = "./files"

# 各ファイルの公開状態を保持する辞書
# True: 公開, False: 非公開
file_status = {}

def load_files():
    """
    指定ディレクトリ内のファイル一覧を取得します。
    """
    files = []
    for f in os.listdir(FILE_DIRECTORY):
        if os.path.isfile(os.path.join(FILE_DIRECTORY, f)):
            files.append(f)
    return files

def initialize_file_status():
    """
    新規ファイルがあれば、デフォルト（非公開）状態で辞書に追加します。
    """
    files = load_files()
    for f in files:
        if f not in file_status:
            file_status[f] = False

# 管理者認証情報：.env ファイルから取得（未設定の場合はデフォルト値）
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "password")

# 管理画面のパスをランダムな英数字16文字に設定（.env で上書き可能）
ADMIN_ROUTE = os.environ.get("ADMIN_ROUTE")
if not ADMIN_ROUTE:
    ADMIN_ROUTE = ''.join(random.choices(string.ascii_letters + string.digits, k=16))

def get_lan_ip():
    """
    ホスト名から取得できるIPアドレス群の中から、192.168.で始まるIPアドレスを返します。
    見つからなければ、ソケットを用いて外部への接続で得たIPを返します。
    """
    try:
        hostname = socket.gethostname()
        ips = socket.gethostbyname_ex(hostname)[2]
        for ip in ips:
            if ip.startswith("192.168."):
                return ip
    except Exception:
        pass

    # 上記で取得できなかった場合、ソケット接続でIPを取得する方法
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
    ユーザー名とパスワードが正しいかを確認します。
    """
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def authenticate():
    """
    認証が必要な場合のレスポンスを返します。
    """
    return Response(
        '認証が必要です', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    """
    管理画面へのアクセスに認証が必要なことを保証するデコレータ。
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def index():
    """
    エンドユーザー向けのファイル一覧画面。
    公開状態になっているファイルのみを表示します。
    """
    initialize_file_status()
    public_files = [f for f in load_files() if file_status.get(f, False)]
    html = "<h1>ファイル一覧</h1><ul>"
    for f in public_files:
        html += f'<li><a href="/download/{f}">{f}</a></li>'
    html += "</ul>"
    return html

@app.route("/download/<filename>")
def download(filename):
    """
    指定ファイルのダウンロード処理。
    ファイルが存在し、かつ公開状態の場合のみダウンロード可能です。
    """
    file_path = os.path.join(FILE_DIRECTORY, filename)
    if not os.path.exists(file_path):
        return "ファイルが見つかりません", 404
    if not file_status.get(filename, False):
        return "このファイルは現在非公開です", 403
    return send_from_directory(FILE_DIRECTORY, filename, as_attachment=True)

@app.route("/" + ADMIN_ROUTE, methods=["GET", "POST"])
@requires_auth
def admin():
    """
    管理者向けインターフェース。
    GETの場合、全ファイルの一覧と公開状態を表示します。
    POSTの場合、フォーム送信された内容で各ファイルの公開状態を更新します。
    """
    initialize_file_status()
    if request.method == "POST":
        for filename in load_files():
            file_status[filename] = (request.form.get(filename) == "on")
        return redirect(url_for("admin"))
    
    html = "<h1>管理者インターフェース</h1>"
    html += "<form method='POST'>"
    html += "<table border='1'><tr><th>ファイル名</th><th>公開状態</th></tr>"
    for f in load_files():
        checked = "checked" if file_status.get(f, False) else ""
        html += f"<tr><td>{f}</td><td><input type='checkbox' name='{f}' {checked}></td></tr>"
    html += "</table>"
    html += "<input type='submit' value='更新'>"
    html += "</form>"
    html += '<br><a href="/">ファイル一覧へ戻る</a>'
    return html

if __name__ == "__main__":
    if not os.path.exists(FILE_DIRECTORY):
        os.makedirs(FILE_DIRECTORY)
    
    # コマンドライン引数でポート番号を指定（指定がない場合は5000を使用）
    port = 5000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("ポート番号は整数で指定してください")
            sys.exit(1)
    
    # ローカルネットワークのIPアドレスを取得
    local_ip = get_lan_ip()
    # アプリケーション起動時に管理画面のURLをログ出力
    print(f"管理者パネルのURL: http://{local_ip}:{port}/{ADMIN_ROUTE}")
    
    app.run(host="0.0.0.0", port=port)
