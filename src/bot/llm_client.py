"""ローカルで動作する LLM サーバーと通信するクライアントモジュール。"""

from __future__ import annotations

import json  # LLM ストリーミングレスポンスの JSON 部分をパースするために json モジュールをインポート
from typing import Any, AsyncIterator  # 任意の型および非同期イテレータ型を表現するためにインポート

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

    def _build_messages(
        self,
        user_message: str,
        history_messages: list[dict[str, Any]] | None,
        image_urls: list[str] | None,
    ) -> list[dict[str, Any]]:
        """system / 履歴 / 画像情報 / 現在のユーザーメッセージをまとめて LLM に渡すメッセージ配列を構築するヘルパー関数。"""

        # LLM に渡すメッセージ一覧を初期化するための空リストを用意
        messages: list[dict[str, Any]] = []
        # 設定でシステムプロンプトが指定されている場合は最初のメッセージとして追加
        if settings.llm_system_prompt:
            # system 役割のメッセージ辞書を作成し messages リストに追加
            messages.append(
                {
                    "role": "system",
                    "content": settings.llm_system_prompt,
                },
            )
        # 呼び出し元から渡された会話履歴メッセージがあれば順番どおりに追加
        if history_messages:
            # 履歴メッセージは既に role / content を含むと想定し、そのまま extend する
            messages.extend(history_messages)
        # ユーザーからの入力メッセージを role=user のメッセージとしてリストに追加
        # 画像入力に対応しているモデルの場合は text + image_url の複合メッセージ形式を組み立てる
        if settings.llm_supports_vision and image_urls:
            # Vision 対応モデル向けに、テキストと画像 URL を両方含む content 配列を構築する
            content_parts: list[dict[str, Any]] = [
                {
                    "type": "text",
                    "text": user_message,
                },
            ]
            # 添付されている全ての画像 URL を image_url タイプとして追加
            for url in image_urls:
                # OpenAI 互換の image_url 形式に従った要素を content 配列に追加
                content_parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": url,
                        },
                    },
                )
            # 構築した content 配列を持つ user メッセージを messages リストに追加
            messages.append(
                {
                    "role": "user",
                    "content": content_parts,
                },
            )
        else:
            # Vision 非対応、または画像が無い場合は従来どおりテキストのみの user メッセージを追加
            messages.append(
                {
                    "role": "user",
                    "content": user_message,
                },
            )
        # 構築したメッセージ配列を呼び出し元に返却
        return messages

    async def stream_reply(
        self,
        user_message: str,
        history_messages: list[dict[str, Any]] | None = None,
        image_urls: list[str] | None = None,
    ) -> AsyncIterator[str]:
        """ローカル LLM からのストリーミングレスポンスをチャンクごとに返す非同期イテレータメソッド。"""

        # LLM へ送信する messages 配列をヘルパー関数で構築
        messages = self._build_messages(user_message, history_messages, image_urls)
        # OpenAI 互換ストリーミング API を想定し、stream フラグを True に設定したペイロードを構築
        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "stream": True,
        }
        # 非同期 HTTP クライアントコンテキストを開き、ストリーミングレスポンスを扱えるようにする
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            # client.stream を用いてストリーミングモードで POST リクエストを送信
            async with client.stream("POST", self._endpoint_url, json=payload) as response:
                # ステータスコードがエラーの場合は例外を送出して呼び出し元で処理させる
                response.raise_for_status()
                # レスポンスボディを 1 行ずつ非同期に読み取り処理する
                async for line in response.aiter_lines():
                    # 行が None または空文字列の場合はスキップして次の行へ進む
                    if not line:
                        continue
                    # 前後の空白文字を削除して判定しやすくする
                    line = line.strip()
                    # OpenAI 互換のストリーミングでは "data:" で始まる行に JSON が含まれるためそれ以外は無視
                    if not line.startswith("data:"):
                        continue
                    # 先頭の "data:" を取り除いた文字列部分を取り出す
                    data_str = line[len("data:") :].strip()
                    # [DONE] はストリーム終了を意味するためループを抜けて処理を終了
                    if data_str == "[DONE]":
                        break
                    try:
                        # 文字列として受け取った JSON 片を辞書オブジェクトに変換
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        # JSON のパースに失敗した場合はその行をスキップして次に進む
                        continue
                    # choices 配列から先頭要素を取得し、存在しなければ次の行へ進む
                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    first_choice = choices[0]
                    # OpenAI 互換ストリームでは delta 内に差分トークンが入るため delta を取得
                    delta: dict[str, Any] = first_choice.get("delta", {})
                    # delta から content フィールドを取り出し、存在しなければ空文字列とする
                    content_piece = delta.get("content", "")
                    # content_piece が空の場合は何もユーザーに返すべきテキストが無いためスキップ
                    if not content_piece:
                        continue
                    # 非空の文字列断片を呼び出し元に yield して疑似ストリーミングを実現
                    yield str(content_piece)

    async def generate_reply(
        self,
        user_message: str,
        history_messages: list[dict[str, Any]] | None = None,
        image_urls: list[str] | None = None,
    ) -> str:
        """ストリーミングメソッドを内部的に利用して最終的な全文応答を返すラッパーメソッド。"""

        # 受信したトークン断片を順番に格納するためのリストを初期化
        chunks: list[str] = []
        # stream_reply から送られてくるテキスト断片を非同期イテレータで順次取得
        async for piece in self.stream_reply(
            user_message=user_message,
            history_messages=history_messages,
            image_urls=image_urls,
        ):
            # 各テキスト断片をリストに追加していく
            chunks.append(piece)
        # 受信した断片を結合して最終的な応答全文を生成
        full_text = "".join(chunks)
        # 結合結果が空文字列の場合は LLM から意味のある応答が返ってきていないためプレースホルダを返す
        if not full_text:
            # 呼び出し元の UX を考慮し、ユーザーにも理解しやすいメッセージにする
            return "ローカル LLM の応答内容が空でした。"
        # 正常に取得したコンテンツ文字列をそのまま返す
        return full_text


# アプリ全体で共有して使い回すためのクライアントインスタンスを生成
llm_client = LocalLLMClient()

