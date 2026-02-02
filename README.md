# Teams LLM Bot

Python 製の Microsoft Teams 向けボットです。  
Bot Framework 互換のエンドポイントを提供し、ローカルで動作する LLM と連携してチャット応答を返します。

## 特長

- ローカル LLM（例: `http://localhost:1234/v1/chat/completions` 形式）と連携
- FastAPI ベースの軽量サーバー
- ngrok などでインターネット公開すれば、そのまま Teams から利用可能
- MIT License / オープンソース

## ディレクトリ構成（提案）

```text
.
├─ src/
│  └─ bot/
│     ├─ __init__.py
│     ├─ settings.py        # 環境変数・設定読み込み
│     ├─ llm_client.py      # ローカル LLM との通信
│     ├─ teams_bot.py       # Teams メッセージハンドラ
│     └─ server.py          # FastAPI サーバーとエンドポイント定義
├─ config_example.yaml      # 設定ファイルのサンプル
├─ config.yaml              # 実際に利用される設定（初回起動時に自動生成）
├─ requirements.txt
├─ start_bot.bat            # 起動用バッチ（Windows 用）
└─ README.md
```

## 必要環境

- Python 3.10.x（3.10 系に固定することを推奨）
- ローカル LLM サーバー（例: LM Studio / vLLM / LocalAI / llama.cpp HTTP サーバーなど）
- （任意）ngrok などのトンネリングツール

## セットアップ手順

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

上記コマンドは PowerShell / コマンドプロンプトで実行してください。

## 設定ファイル（config.yaml）

- ルート直下の `config_example.yaml` を元に、初回起動時に `config.yaml` が自動生成されます。
- 値を変更したい場合は `config.yaml` を直接編集してください。

```yaml
bot:
  microsoft_app_id: "YOUR_APP_ID"
  microsoft_app_password: "YOUR_APP_PASSWORD"

server:
  host: "0.0.0.0"
  port: 3978

llm:
  base_url: "http://localhost:1234"
  chat_path: "/v1/chat/completions"
  model: "local-model"
  system_prompt: "ここに Bot 全体で使うシステムプロンプトを書く"
  supports_vision: false  # 画像入力に対応したモデルを使う場合は true にする
```

LM Studio や vLLM など OpenAI 互換エンドポイントを提供するサーバーであれば、  
`base_url` と `model` を合わせるだけで利用できます。

## 起動方法

### 1. バッチファイルで起動（推奨）

Windows エクスプローラーから `start_bot.bat` をダブルクリックするか、  
ターミナルから次のように実行します。

```bat
start_bot.bat
```

### 2. 手動で起動

```bash
.venv\Scripts\activate
uvicorn src.bot.server:app --host 0.0.0.0 --port 3978 --reload
```

## ローカル LLM 側の想定 API 仕様

- エンドポイント: `http://localhost:1234/v1/chat/completions`（例）
- メソッド: `POST`
- ボディ（例・ストリーミング OFF の場合）:

```json
{
  "model": "local-model",
  "messages": [
    { "role": "user", "content": "こんにちは" }
  ]
}
```

レスポンスは OpenAI 互換 (`choices[0].message.content`) を想定します。

### ストリーミング有効時（疑似ストリーミング表示用）

`src/bot/llm_client.py` では OpenAI 互換のストリーミング API を利用して、  
Bot 側でメッセージを数回に分けて更新する「疑似ストリーミング」を実装しています。

- リクエスト例:

```json
{
  "model": "local-model",
  "messages": [
    { "role": "system", "content": "..." },
    { "role": "user", "content": "こんにちは" }
  ],
  "stream": true
}
```

- レスポンス形式（例）:

```text
data: {"choices":[{"delta":{"content":"こん"},"finish_reason":null}]}
data: {"choices":[{"delta":{"content":"にちは"},"finish_reason":null}]}
data: {"choices":[{"delta":{"content":"！"},"finish_reason":"stop"}]}
data: [DONE]
```

LM Studio / vLLM 側で OpenAI 互換の `stream: true` と上記のような SSE (`data: ...`) 出力を有効にしておく必要があります。

### 画像入力（Vision 対応モデルを利用する場合）

- `config.yaml` の `llm.supports_vision` を `true` に設定すると、  
  Teams メッセージに添付された画像を OpenAI 互換の `image_url` 形式で LLM に渡します。
- Vision 非対応モデル（`supports_vision: false`）のまま画像が添付された場合は、
  - テキストのみで応答を生成
  - Bot の応答文末に  
    `<sub>画像認識には対応していないモデルです。</sub>`  
    という注意書きが小さく追記されます。

`config.yaml` の `llm` セクションを編集することで、  
任意のローカル LLM サーバーに接続できます。

## Teams 側との連携の概要

1. このボットサーバーをインターネットから到達可能にする。  
   - 例: サーバー PC をそのまま公開し `https://<サーバーの FQDN>/api/messages` にルーティング。  
   - あるいは、リバースプロキシ（nginx / IIS など）で 443 → 3978 に転送。
2. Microsoft Bot Framework で Bot リソースを作成し、メッセージエンドポイントを  
   `https://<サーバーの FQDN>/api/messages` に設定。
3. チャネル設定で Teams を有効化。

### Teams Toolkit と一緒に使う場合（VS Code）

- VS Code に **Teams Toolkit** 拡張機能をインストール。
- 「既存アプリケーションをインポート」シナリオとして、このリポジトリを選択。  
- `teams_manifest.json` を Teams アプリのマニフェストとして利用し、`<<YOUR_APP_ID>>` と `<<YOUR_DOMAIN>>` を書き換える。
- Teams Toolkit から Azure / Teams へアプリをアップロード・管理すれば、  
  バックエンドはこの Python Bot（`/api/messages`）をそのまま利用できます。

Bot Framework / Azure Portal での詳細な設定手順は公式ドキュメントを参照してください。

## ライセンス

MIT License  
詳細は `LICENSE` を参照してください。

