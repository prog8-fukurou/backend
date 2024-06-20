# Prog8ハッカソン フクロウチームバックエンド

[テンプレート]("https://github.com/foasho/fastapi-lambda")

## エンドポイント

### HTTP

#### GET /image

| param | type | desc |
| -- | -- | -- |
| room_id | str | |
| client_id | str | optional |

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

#### room-init:{room_id}

**サーバー** → クライアント

#### user-init:{user_name}

**サーバー** → クライアント

ユーザー参加時に「client_id:user_name」の形式で送信

#### user-ready

**クライアント** → サーバー

準備ができたら送る

##### game-start:{client_id(master)}

masterに選ばれたユーザーのIDを送信

**サーバー** → クライアント
クライアント側で時間計ってほしい

##### game-end

**クライアント** → サーバー

#### vote-start

**サーバー** → 全クライアント

game-endコマンド受信時にほかのすべてのクライアントがゲームを終了していたらvote-startを配信

マスターが投票できるようにする
画像データを全クライアントに配信したい

#### vote-end:{client_id}

**クライアント** → サーバー

#### winner:{client_id}

**サーバー** → クライアント

勝者のclient_idを配信

## サーバー側で保持するデータ

### ws接続関連

client_id, room_id
ソース参照

### ゲーム本体関係
