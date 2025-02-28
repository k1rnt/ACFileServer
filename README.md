# ACFileServer
公開/非公開を選択できるファイルサーバー

## セットアップ (基本的には初回のみでok)
```bash
# 実行権限を付与
chmod +x ./setup.sh

# セットアップの実行
./setup.sh
```

## 起動方法
```bash
# デフォルトでは5000番ポートで起動
venv/bin/python3 main.py

# ポートを指定して起動
venv/bin/python3 main.py 8000

# 起動に成功すると管理画面のパスが表示されます。
```

## 管理画面の認証情報の設定
セットアップが完了したら、`.env`ファイルを開き設定したい認証情報を記述して保存してから起動してください。
下記は例です。
```
ADMIN_USERNAME=superStrongUser
ADMIN_PASSWORD=superStrongPassword
```
