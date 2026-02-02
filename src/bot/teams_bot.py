"""Microsoft Teams からのメッセージを処理する Bot 実装モジュール。"""

from __future__ import annotations

from typing import Any  # 任意の型を扱うために Any をインポート

from botbuilder.core import (  # Bot Framework のコア機能を提供するクラス群をインポート
    ActivityHandler,
    MessageFactory,
    TurnContext,
)
from botbuilder.schema import (  # アクティビティ種別などのスキーマ定義をインポート
    Activity,
    ChannelAccount,
    Entity,
)

from .llm_client import llm_client  # ローカル LLM クライアントをインポート


class TeamsLLMBot(ActivityHandler):
    """Teams からのメッセージを受け取りローカル LLM で応答を生成する Bot クラス。"""

    def __init__(self) -> None:
        """Bot インスタンスの初期化処理を行うコンストラクタ。"""

        # 親クラス ActivityHandler の初期化処理を呼び出し、基底の状態を正しく設定
        super().__init__()
        # 会話単位でメッセージ履歴を保持するための辞書を初期化
        # キー: 会話 ID、値: role / content を持つメッセージ辞書のリスト
        self._conversation_histories: dict[str, list[dict[str, str]]] = {}

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        """ユーザーからメッセージが送信された際に呼び出されるハンドラ。"""

        # 現在のアクティビティに含まれるエンティティ一覧を取得し、存在しない場合は空リストを利用
        entities = turn_context.activity.entities or []
        # メンション対象を表すエンティティだけを抽出するためのリスト内包表現
        mention_entities = [
            entity for entity in entities if isinstance(entity, Entity) and entity.type == "mention"
        ]
        # Bot 自身が明示的にメンションされているかどうかを示すフラグを初期化
        is_mentioned = False
        # 抽出したメンションエンティティごとにループ処理を行う
        for entity in mention_entities:
            # entity の mentioned 属性からメンション対象情報を取得し、存在しない場合は None のまま扱う
            mentioned = getattr(entity, "mentioned", None)
            # mentioned が存在し、かつその id が Bot 自身の id と一致するかを確認
            if mentioned and mentioned.id == turn_context.activity.recipient.id:
                # 条件を満たした場合はメンション済みフラグを True に変更
                is_mentioned = True
                # 以降のループは不要なため break で抜ける
                break
        # Bot がメンションされていないメッセージの場合は何も応答せず早期 return する
        if not is_mentioned:
            # グループチャットやチームチャネルで他メッセージに干渉しないよう無応答で終了
            return

        # 現在のターンにおける Activity からユーザーの発言テキストを取得
        user_text = turn_context.activity.text or ""
        # ユーザーの発言が空文字列の場合は処理を継続しても意味がないためガードする
        if not user_text:
            # 空メッセージに対しては簡易的な注意喚起メッセージを返す
            empty_text_reply = "メッセージ内容が空のようです。何か質問やメッセージを送ってください。"
            # 注意喚起メッセージを Activity として生成
            empty_activity = MessageFactory.text(empty_text_reply)
            # 生成した Activity をユーザーに送信
            await turn_context.send_activity(empty_activity)
            # これ以上の処理は不要なため早期 return でハンドラを終了
            return

        # 会話 ID を取得し、履歴辞書から該当会話のメッセージ履歴を取り出す
        conversation_id = turn_context.activity.conversation.id
        # 指定された会話 ID に対する履歴が存在しなければ空リストを利用
        history = self._conversation_histories.get(conversation_id, [])
        # 直近 10 往復分（ユーザーと Bot のセット）に相当する 20 件だけを LLM に渡すためにスライス
        limited_history = history[-20:] if len(history) > 20 else history

        # first response として簡易メッセージを送信し、その Activity を後から上書き更新する
        initial_text = "考えています..."  # ユーザーに処理中であることを伝えるプレースホルダテキスト
        # MessageFactory.text を利用して初期メッセージ Activity を生成
        reply_activity = MessageFactory.text(initial_text)
        # 生成した Activity を送信し、その結果として返る ResourceResponse から ID を取得
        resource = await turn_context.send_activity(reply_activity)
        # 後続の update_activity で利用するため、送信した Activity に ID を設定
        reply_activity.id = resource.id

        # LLM から受信したチャンクを結合していくためのバッファ文字列を初期化
        accumulated_text = ""
        # ローカル LLM クライアントのストリーミングメソッドを利用して疑似ストリーミングを実現
        async for chunk in llm_client.stream_reply(
            user_message=user_text,
            history_messages=limited_history,
        ):
            # 新たに受信したチャンク文字列をバッファ末尾に追加
            accumulated_text += chunk
            # Activity のテキスト部分を現在までの全文に更新
            reply_activity.text = accumulated_text
            # update_activity を呼び出して既存メッセージを上書き更新し、画面上で伸びていくように見せる
            await turn_context.update_activity(reply_activity)

        # 最終的な応答テキストとして、蓄積された全文を変数に保存
        final_text = accumulated_text or initial_text

        # 今回のユーザーメッセージと LLM 応答を履歴リストの末尾に追加
        new_history = history + [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": final_text},
        ]
        # 履歴が 10 往復分（20 メッセージ）を超える場合は末尾 20 件だけ残す
        if len(new_history) > 20:
            new_history = new_history[-20:]
        # 更新済みの履歴を会話 ID をキーとして辞書に保存
        self._conversation_histories[conversation_id] = new_history

    async def on_turn(
        self,
        turn_context: TurnContext,
    ) -> None:
        """各ターン（リクエストごと）の共通前処理・後処理を行うオーバーライドメソッド。"""

        # 親クラス ActivityHandler の on_turn 実装を呼び出し、標準のディスパッチ処理を実行
        await super().on_turn(turn_context)

    async def on_turn_activity(
        self,
        activity: Activity,
        turn_context: TurnContext,
    ) -> None:
        """アクティビティ単位での拡張用フック（今回は必要最低限の処理に留める）。"""

        # ActivityHandler の既定実装に処理を委譲し、余計なロジックを追加しない
        await super().on_turn_activity(activity, turn_context)

