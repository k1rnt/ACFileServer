# ACFileServer
公開/非公開を選択できるファイルサーバー

## セットアップ (基本的には初回のみでok)
1. chmod +x ./setup.sh
2. ./setup.sh

## 起動方法
```bash
# デフォルトでは80番ポートで起動
venv/bin/python3 main.py

# ポートを指定して起動
venv/bin/python3 main.py 8000
```

## 管理画面の認証情報の設定
セットアップが完了したら、`.env`ファイルを開き設定したい認証情報を記述して保存してから起動してください。
下記は例です。
```
ADMIN_USERNAME=superStrongUser
ADMIN_PASSWORD=superStrongPassword
```