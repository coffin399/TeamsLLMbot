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

        # ローカル LLM クライアントを利用してユーザー発言に対する応答文を非同期で生成
        llm_reply_text = await llm_client.generate_reply(user_text)
        # LLM からの応答テキストを基に Bot からの返信 Activity を生成
        reply_activity = MessageFactory.text(llm_reply_text)
        # 生成した返信 Activity を現在の会話コンテキストに対して送信
        await turn_context.send_activity(reply_activity)

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

