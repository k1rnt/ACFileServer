#!/bin/bash

# 仮想環境が存在しなければ作成
if [ ! -d "venv" ]; then
    echo "仮想環境を作成しています..."
    python3 -m venv venv
fi

# .env が存在しなければ、.env.example からコピーする
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo ".env が見つからないため、.env.example を .env にコピーします..."
        cp .env.example .env
    else
        echo ".env.example が存在しません。"
    fi
fi

# 仮想環境をアクティブにする
echo "仮想環境をアクティブにしています..."
source venv/bin/activate

# pip のアップグレード
echo "pip をアップグレードしています..."
pip install --upgrade pip

# 依存関係のインストール
echo "依存関係をインストールしています..."
pip install -r requirements.txt

echo "セットアップ完了。仮想環境がアクティブです。"
