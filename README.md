# 放課後レスキュー

宿題やテスト勉強で分からない問題を、高校生同士で助け合う掲示板です。

- 公開サイト：https://sk-high-school-bulletin-board-fbbfcvdxbqgraadj.japaneast-01.azurewebsites.net/
- GitHub：https://github.com/Bamboo2651/SK-Azure

## 主な機能

- 教科、困り度、期限、希望する助け方を指定した質問投稿
- 質問ごとの返信投稿と返信一覧
- 教科別の絞り込みとキーワード検索
- 未解決・解決済みの状態管理
- Azure Table Storageへの投稿保存
- Azure Blob Storageへの画像保存
- スマートフォン対応

## ローカルでの起動

1. Pythonの仮想環境を作り、依存ライブラリをインストールする。

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Azure Storageの接続文字列を、そのターミナルだけで有効な環境変数へ設定する。

   ```powershell
   $env:AZURE_STORAGE_CONNECTION_STRING = "接続文字列"
   ```

3. Flaskを起動する。

   ```powershell
   flask --app app run --debug
   ```

接続文字列はソースコード、`.env`、GitHubへ保存しないでください。

## Azure App Serviceの設定

- アプリ設定に `AZURE_STORAGE_CONNECTION_STRING` を登録する。
- スタートアップコマンドを `gunicorn app:app` にする。
- App Serviceから利用するStorageアカウントに、Table StorageとBlob Storageを用意する。

詳しい要件は [requirements.md](requirements.md) を参照してください。
