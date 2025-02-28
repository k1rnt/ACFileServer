#!/bin/bash
set -e

# ロールバック用フラグ
CREATED_VENV="false"
COPIED_ENV="false"

# エラートラップによるロールバック処理
function rollback {
    echo "エラーが発生しました。ロールバックを開始します..."
    if [ "$CREATED_VENV" = "true" ]; then
        echo "作成した仮想環境 'venv' を削除します..."
        rm -rf venv
    fi
    if [ "$COPIED_ENV" = "true" ]; then
        echo "コピーした .env ファイルを削除します..."
        rm -f .env
    fi
    exit 1
}

trap rollback ERR

echo "セットアップを開始します..."

# 仮想環境が存在しなければ作成
if [ ! -d "venv" ]; then
    echo "仮想環境を作成しています..."
    python3 -m venv venv
    CREATED_VENV="true"
fi

# .env が存在しなければ、.env.example からコピーする
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo ".env が見つからないため、.env.example を .env にコピーします..."
        cp .env.example .env
        COPIED_ENV="true"
    else
        echo ".env.example が存在しません。"
        exit 1
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

# すべて成功した場合、ロールバック用フラグをリセット
CREATED_VENV="false"
COPIED_ENV="false"

echo "セットアップ完了。仮想環境がアクティブです。"
