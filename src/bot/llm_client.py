"""ローカルで動作する LLM サーバーと通信するクライアントモジュール。"""

from __future__ import annotations

from typing import Any  # 任意の型を表現するために Any をインポート

import httpx  # 非同期 HTTP クライアントとして httpx をインポート

from .settings import settings  # アプリ共通設定をインポート


class LocalLLMClient:
    """ローカル LLM とのチャット補完 API を呼び出すクライアントクラス。"""

    def __init__(self) -> None:
        """クライアントの初期化を行うコンストラクタ。"""

        # ベース URL とエンドポイントパスを結合して完全なエンドポイント URL を作成
        self._endpoint_url = f"{settings.llm_base_url.rstrip('/')}{settings.llm_chat_path}"
        # 共通で利用する HTTP タイムアウト秒数を属性として保持
        self._timeout_seconds = 60.0

    async def generate_reply(self, user_message: str) -> str:
        """ユーザーからのメッセージをローカル LLM に渡し、返信テキストを返す非同期メソッド。"""

        # OpenAI 互換のチャット補完 API 形式に従ってリクエストボディを構築
        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": [
                {
                    "role": "user",
                    "content": user_message,
                }
            ],
        }
        # 非同期 HTTP クライアントコンテキストを開き、リクエスト完了後に自動クローズさせる
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            # POST メソッドで LLM エンドポイントにリクエストを送信
            response = await client.post(self._endpoint_url, json=payload)
            # ステータスコードがエラーの場合は例外を送出して呼び出し元で処理させる
            response.raise_for_status()
            # レスポンスボディを JSON としてパースし辞書型として取得
            data: dict[str, Any] = response.json()

        # OpenAI 互換レスポンスを想定し、choices 配列の先頭要素から message.content を取り出す
        choices = data.get("choices", [])
        # choices 配列が空の場合は LLM 側で応答生成に失敗しているためデフォルトメッセージを返す
        if not choices:
            # 呼び出し元で扱いやすいよう、ユーザー向けの簡潔なエラーメッセージを返却
            return "ローカル LLM から応答を取得できませんでした。"
        # 最初の choice 要素を取り出す
        first_choice = choices[0]
        # choice 内の message 辞書を取得し、存在しない場合は空辞書を返す
        message: dict[str, Any] = first_choice.get("message", {})
        # message から content フィールドを取り出し、存在しない場合は空文字列とする
        content = message.get("content", "")
        # content が空文字列の場合は LLM から意味のある応答が返ってきていないためプレースホルダを返す
        if not content:
            # 呼び出し元の UX を考慮し、ユーザーにも理解しやすいメッセージにする
            return "ローカル LLM の応答内容が空でした。"
        # 正常に取得したコンテンツ文字列をそのまま返す
        return str(content)


# アプリ全体で共有して使い回すためのクライアントインスタンスを生成
llm_client = LocalLLMClient()

