# Prog8ハッカソン フクロウチームバックエンド

[テンプレート]("https://github.com/foasho/fastapi-lambda")

## エンドポイント

### HTTP

#### POST /prompt → str

| param | type | desc |
| -- | -- | -- |
| purpose | str | optional: 目的 |
| category | str | optional: リゾート、温泉地 etc |
| overnight | bool | optional: 泊り(True) 日帰り(False) |
| background_color | str | optional: ex. #FFFFFF |
| belongings | str | optional: 持ち物 |

#### POST /image → str

| param | type | desc |
| -- | -- | -- |
| body | str | しおりの本文(/promptで生成したもの) |

### Websocket

| param | type | desc |
| -- | -- | -- |
| room_id | int | optional |
| client_id | str | タブごとの固有の値(クライアント側で任意の値を設定) |

#### WS: /ws?client_id={}&room_id={}

ルームの作成、参加

#### 固定コマンド

##### game-start:{role}

role: Master or Player

サーバー→全クライアント
クライアント側で時間計ってほしい

##### game-end

クライアント→サーバー

#### vote-start

サーバー→全クライアント

マスターが投票できるようにする
画像データを全クライアントに配信したい

#### vote-end:{client_id}

サーバー側処理なし

## サーバー側で保持するデータ

### ws接続関連

client_id, room_id
ソース参照

### ゲーム本体関係

```python
{
    "{client_id}": {
        "playing": bool,
        "image": str,
        "master": bool
    }
}
```
