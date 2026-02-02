"""FastAPI を用いて Bot Framework / Teams からのリクエストを受け付けるサーバーモジュール。"""

from __future__ import annotations

import json  # Bot Framework の JSON ペイロードを扱うために json モジュールをインポート
from typing import Any  # 任意の型を表すために Any をインポート

from fastapi import (  # FastAPI 本体と HTTP 関連の機能をインポート
    FastAPI,
    HTTPException,
    Request,
)
from fastapi.responses import JSONResponse  # JSON レスポンス生成用のクラスをインポート
from botbuilder.core import (  # Bot Framework 用のアダプターや Bot 実行用クラスをインポート
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
    TurnContext,
)
from botbuilder.schema import Activity  # 受信したリクエストを Bot Activity に変換するためのクラスをインポート

from .settings import settings  # 共通設定オブジェクトをインポート
from .teams_bot import TeamsLLMBot  # 実際の Bot 実装クラスをインポート


# FastAPI アプリケーションインスタンスを生成
app = FastAPI(title="Teams LLM Bot")

# Bot Framework アダプターの設定オブジェクトを生成
adapter_settings = BotFrameworkAdapterSettings(
    app_id=settings.microsoft_app_id,
    app_password=settings.microsoft_app_password,
)
# 設定を渡して BotFrameworkAdapter のインスタンスを生成
adapter = BotFrameworkAdapter(adapter_settings)

# Teams からのメッセージを処理する Bot 実装インスタンスを生成
bot = TeamsLLMBot()


@app.post("/api/messages")
async def messages(request: Request) -> JSONResponse:
    """Bot Framework / Teams から送られてくるメッセージリクエストを処理するエンドポイント。"""

    # リクエストヘッダーから Content-Type を取得し、小文字に変換して比較しやすくする
    content_type = request.headers.get("Content-Type", "").lower()
    # 受信した Content-Type が application/json を含まない場合は 415 エラーを返す
    if "application/json" not in content_type:
        # FastAPI の HTTPException を送出してクライアントにエラーを通知
        raise HTTPException(
            status_code=415,
            detail="Content-Type must be application/json.",
        )

    # リクエストボディの JSON を Python オブジェクトとして非同期に取得
    body: dict[str, Any] = await request.json()
    # 取得したボディを Activity.from_dict で Bot Framework の Activity オブジェクトに変換
    activity = Activity().deserialize(body)
    # リクエストのクエリパラメータから auth ヘッダー相当の値を取得（本番環境では認証に利用）
    auth_header = request.headers.get("Authorization", "")

    # BotFrameworkAdapter.process_activity はコールバックベースの API のため、
    # 内部でコールバック関数を定義し、その中で Bot の on_turn を呼び出す
    async def aux_func(turn_context: TurnContext) -> None:
        """アダプターから呼び出されるコールバック関数。"""

        # TeamsLLMBot インスタンスの on_turn メソッドを呼び出し、標準のディスパッチ処理を実行
        await bot.on_turn(turn_context)

    # adapter.process_activity を await して Bot の処理が完了するまで待機
    response = await adapter.process_activity(
        activity,
        auth_header,
        aux_func,
    )

    # adapter.process_activity の戻り値は HTTP レスポンスオブジェクト互換のため、
    # ステータスコードとボディを FastAPI の JSONResponse に詰め替えて返却
    if response:
        # レスポンスのボディを JSON 文字列として取得
        body_text = response.body.decode("utf-8") if response.body else ""
        # ボディが空でない場合は JSON 文字列を Python オブジェクトに変換し、空なら空辞書とする
        json_body: Any = json.loads(body_text) if body_text else {}
        # ステータスコードと JSON ボディを指定して JSONResponse を生成しクライアントに返却
        return JSONResponse(status_code=response.status, content=json_body)

    # Bot から特に明示的なレスポンスが無い場合は 204 No Content を返す
    return JSONResponse(status_code=204, content=None)

