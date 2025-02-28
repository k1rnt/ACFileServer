# ACFileServer
公開/非公開を選択できるファイルサーバー

## セットアップ (基本的には初回のみでok)
1. chmod +x ./setup.sh
2. ./setup.sh

## 起動方法
```bash
# 管理者情報を記入する
`.env` ファイルを編集してユーザー情報とパスワードを設定

# デフォルトでは80番ポートで起動
venv/bin/python3 main.py

# ポートを指定して起動
venv/bin/python3 main.py 8000
```