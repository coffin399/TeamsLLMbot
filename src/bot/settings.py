"""設定値を YAML ファイルから読み込んで管理するモジュール。"""

from __future__ import annotations

from dataclasses import dataclass  # 設定オブジェクト定義用に dataclass をインポート
from pathlib import Path  # 設定ファイルのパス操作に利用するため Path をインポート
from typing import Final  # 不変（定数）を表現するために Final をインポート

import yaml  # YAML 形式の設定ファイルを読み書きするために PyYAML をインポート


@dataclass(frozen=True)
class Settings:
    """アプリケーション全体で利用する設定値を保持するデータクラス。"""

    # Bot Framework から送信されるリクエストの検証に使用するアプリ ID
    microsoft_app_id: str
    # Bot Framework から送信されるリクエストの検証に使用するアプリ パスワード
    microsoft_app_password: str
    # ローカル LLM の HTTP ベース URL
    llm_base_url: str
    # ローカル LLM のチャット補完エンドポイントパス
    llm_chat_path: str
    # 利用するモデル名（ローカル LLM 側の設定に依存）
    llm_model: str
    # FastAPI / uvicorn が待ち受けるホスト名
    host: str
    # FastAPI / uvicorn が待ち受けるポート番号
    port: int


def _project_root() -> Path:
    """このファイル位置からプロジェクトルートディレクトリを解決するヘルパー関数。"""

    # 現在のファイルパスを絶対パスに変換して取得
    current_file = Path(__file__).resolve()
    # src/bot/settings.py から 2 階層上がることでリポジトリルートを指す Path を取得
    root_dir = current_file.parents[2]
    # 求めたルートディレクトリ Path オブジェクトを返す
    return root_dir


def _ensure_config_file(root_dir: Path) -> Path:
    """config.yaml が無ければ config_example.yaml から生成し、最終的なパスを返すヘルパー関数。"""

    # ルートディレクトリ直下の config.yaml のパスを生成
    config_path = root_dir / "config.yaml"
    # 既に config.yaml が存在する場合は何もせずそのパスを返す
    if config_path.exists():
        # 以降の処理で利用するために既存の config.yaml パスをそのまま返却
        return config_path

    # サンプル設定ファイル config_example.yaml のパスを生成
    example_path = root_dir / "config_example.yaml"
    # サンプル設定ファイルが存在しない場合はユーザーに明示的に知らせるため例外を送出
    if not example_path.exists():
        # どのパスが見つからなかったかを含むエラーメッセージで RuntimeError を送出
        raise RuntimeError(f"サンプル設定ファイルが見つかりません: {example_path}")

    # サンプル設定ファイルの内容をテキストとして読み込む
    example_text = example_path.read_text(encoding="utf-8")
    # 読み込んだテキストをそのまま config.yaml に書き込んで初期ファイルを生成
    config_path.write_text(example_text, encoding="utf-8")
    # 生成した config.yaml のパスを返す
    return config_path


def _load_config_dict(config_path: Path) -> dict:
    """指定されたパスから YAML を読み込み、辞書オブジェクトとして返すヘルパー関数。"""

    # config.yaml の内容をテキストとして読み込む
    yaml_text = config_path.read_text(encoding="utf-8")
    # 読み込んだ YAML テキストを安全なモードでパースして Python オブジェクトに変換
    data = yaml.safe_load(yaml_text) or {}
    # 返り値の型を明示するため dict 型にキャストして返却
    return dict(data)


def load_settings() -> Settings:
    """YAML 設定ファイルから Settings オブジェクトを生成して返すファクトリ関数。"""

    # プロジェクトルートディレクトリを取得
    root_dir = _project_root()
    # ルートディレクトリから設定ファイルを確認し、必要であればサンプルから生成
    config_path = _ensure_config_file(root_dir)
    # 確定した設定ファイルパスから YAML を読み込み辞書形式の設定データを取得
    config_dict = _load_config_dict(config_path)

    # Bot 関連設定セクションを取得し、存在しない場合は空辞書を用意
    bot_cfg = dict(config_dict.get("bot", {}))
    # サーバー関連設定セクションを取得し、存在しない場合は空辞書を用意
    server_cfg = dict(config_dict.get("server", {}))
    # LLM 関連設定セクションを取得し、存在しない場合は空辞書を用意
    llm_cfg = dict(config_dict.get("llm", {}))

    # Bot Framework 用のアプリ ID を bot セクションから取得し、未設定なら空文字列を用いる
    microsoft_app_id = str(bot_cfg.get("microsoft_app_id", ""))
    # Bot Framework 用のアプリ パスワードを bot セクションから取得し、未設定なら空文字列を用いる
    microsoft_app_password = str(bot_cfg.get("microsoft_app_password", ""))

    # ローカル LLM ベース URL を llm セクションから取得し、未設定ならデフォルト URL を利用
    llm_base_url = str(llm_cfg.get("base_url", "http://localhost:1234"))
    # チャット補完エンドポイントパスを llm セクションから取得し、未設定なら標準パスを利用
    llm_chat_path = str(llm_cfg.get("chat_path", "/v1/chat/completions"))
    # モデル名を llm セクションから取得し、未設定なら汎用的なモデル名を利用
    llm_model = str(llm_cfg.get("model", "local-model"))

    # HTTP サーバーのホスト名を server セクションから取得し、未設定なら 0.0.0.0 を利用
    host = str(server_cfg.get("host", "0.0.0.0"))
    # HTTP サーバーのポート番号を server セクションから取得し、未設定なら 3978 を利用
    port_value = server_cfg.get("port", 3978)
    # port 値が文字列か数値かに関わらず int に変換して扱えるようにする
    port = int(port_value)

    # 収集した値を用いて Settings データクラスのインスタンスを生成し、そのまま返す
    return Settings(
        microsoft_app_id=microsoft_app_id,
        microsoft_app_password=microsoft_app_password,
        llm_base_url=llm_base_url,
        llm_chat_path=llm_chat_path,
        llm_model=llm_model,
        host=host,
        port=port,
    )


# アプリ全体で共有して利用する Settings インスタンスを定数として定義
settings: Final[Settings] = load_settings()

