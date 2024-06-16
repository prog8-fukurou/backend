# FastAPI+Lambdaサーバーレステンプレート

# 初めに

FastAPIを使いつつサーバーレスをAWSで構築します。

## 動作手順

- このレポジトリをダウンロード
- Local上でのAPIテストとPyTestの実行
- githubにPushし、Actionsを確認する
- IAMでAPIキーを取得し、GithubのRepository Secretsに設定
- Lambda作成
- APIGateway作成
- 接続確認

## ディレクトリ構成

```commandline
<your_project>
    |- .github/workflows/main.yml
    |- pytests
        |- __init__.py
         -  test_main.py

    |- .gitignore
    |- main.py
    |- localrun.py
    |- requirements.txt
```

# さっそく実装

## 1. レポジトリをダウンロード

git依存は自身のレポジトリでやるためにZIPでダウンロードするのが良いと思います。
リンク先: https://github.com/foasho/fastapi-lambda

コマンドでやる場合は以下
```commandline
git clone https://github.com/foasho/fastapi-lambda.git
```

プロジェクト直下に置いた際には、自身のレポジトリ（プライベート）を作成してください。

## 2. ローカルホストで実行とテスト実行
ローカルホストで実行
```commandline
pip install -r requirements.txt
python localrun.py

>> INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

http://127.0.0.1:8000
につなぎ、"Success"と表示されればをOKです。

テスト実行
```commandline
pytest -s
```

## 3. GithubにPushし、Actionsを確認

自身のレポジトリ欄Actionsの”CI/CD Pipeline”を確認し、
最新のコミット名のものをクリックすると、Actions時のビルドの失敗成功およびエラーログを確認できます。

continous-integrationは成功し、continuous-deploymentは失敗するかと思います。
continuous-deploymentを成功させるには、
IAMでAPIキー作成後、AWS側でLambdaの作成と、S3のバケット作成をしなければなりません。

## 4. IAMでAPIキーを取得し、GithubのRepository Secretsに設定
※今回のリージョンはオハイオ(us-east-2)を使用を想定で記述しています。

1. AWSにアクセスし、IAMページに遷移

2. 新しいユーザーを作成し、ポリシーを追加。
ここでは新しいユーザーをgithub-action-lambdaとしています。
「ポリシーを直接アタッチする」より"AmazonS3FullAccess"と"AWSLambda_FullAccess"を選択し、『次へ』。
※FullAccessはそこそこ大きい権限なので、気になる方は絞った方がいいかもしれません。

作成後、IAM -> ユーザー -> github-action-lambda(ユーザー名) -> 「セキュリティ認証情報」からアクセスキーを生成します。


作成後、アクセスキーとシークレットキーが画面に表示されるので、
どこかにコピーしてメモしておきましょう。
※絶対に誰かに見られないように厳重に管理してください。

Githubの自分のレポジトリに戻り、「Settings」からSecurityの"Secrets and variables"のActionsより、
New repositiory secretで先ほど入手したアクセスキーをAWS_ACCESS_KEY_IDとして、
シークレットキーをAWS_SECRET_ACCESS_KEYとして入力してください。

リージョンは, オハイオの場合はus-east-2なので、
AWS_DEFAULT_REGIONにus-east-2を入力してください。


## 5. S3の作成とLambdaの作成

S3の作成
S3にアクセスし、「バケットを作成」
任意のバケットを選択し、作成ボタンを押すだけです。

Lambdaの作成
Lambdaにアクセスし、「関数を作成」から、
任意の関数名を作成し、ランタイムはPython3.8を選択しましょう。
アーキテクチャはx86_64のままでOKです。あとはそのまま作成するだけです。

作成後、ランタイム設定の編集ボタンを押し、ハンドラを「main.handler」に設定して保存ください。

## 6. main.ymlの編集

main.ymlの87行目と95行目を
自分の作成した関数名およびバケット名に変更して、プッシュしましょう。

```yaml
name: CI/CD Pipeline

on:
  push:
    # "master"は自身のブランチを選択して入力
    branches: [ master ]

jobs:
  continous-integration:
    runs-on: ubuntu-latest

    steps:
      # Step1
      - uses: actions/checkout@v2

      # Step2 Pythonのセットアップ (Pythonは3.8)
      - name: Python Setup
        uses: actions/setup-python@v2
        with:
          python-version: 3.8
          architecture: x64

      # Step3　venv環境のインストール
      - name: Install Python Virtual Env
        run: pip3 install virtualenv

      # Step4
      - name: Setup Virtual env
        uses: actions/cache@v2
        id: cache-venv
        with:
          path: venv
          key: ${{ runner.os }}-venv-${{ hashFiles('**/requirements.txt') }}
          restore-keys: |
            ${{ runner.os }}-venv-

      # Step5 venvに依存ライブラリのインストール
      - name: Activate and Install Depencies into Virtual env
        run: python -m venv venv && source venv/bin/activate && pip3 install -r requirements.txt
        if: steps.cache-venv.outputs.cache-hit != 'true'

      # Step6 作成した実行環境でPytestを行う
      - name: Activate venv and Run Test
        run: . venv/bin/activate && pytest

      # Step7　依存関係をZIPファイル化
      - name: Create Zipfile archive of Dependencies
        run: |
          cd ./venv/lib/python3.8/site-packages
          zip -r9 ../../../../temp.zip .

      # Step8 アプリケーションをZipファイル化
      - name: Add App to Zip file
        run: unzip temp.zip && zip -g api.zip -r .

      # Step9 GithubActionのストレージにapi.zipとしてアップロード
      - name: Upload zip file artifact
        uses: actions/upload-artifact@v2
        with:
          name: api
          path: api.zip

  # api.zipをs3にPutする
  continuous-deployment:
    runs-on: ubuntu-latest
    needs: [continous-integration]
    # refs/heads/masterの"master"部分は自身のブランチを選択して変更
    if: github.ref == 'refs/heads/master'
    steps:
      # Step 1
      - name: Install AWS CLI
        uses: unfor19/install-aws-cli-action@v1
        with:
          version: 1
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: ${{ secrets.AWS_DEFAULT_REGION }}
      # Step 2
      - name: Download Lambda api.zip
        uses: actions/download-artifact@v2
        with:
          name: api
      # Step 3
      - name: Upload to S3
        # <YourS3Bucket>の部分は自身のS3のバケット名を入れる
        run: aws s3 cp api.zip s3://<YourS3Bucket>/api.zip
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: ${{ secrets.AWS_DEFAULT_REGION }}
      # Step 4
      - name: Deploy new Lambda
        # # <YourLambdaName>の部分は自身の作成したLambda名を入れる, <YourS3Bucket>の部分は自身のS3のバケット名を入れる
        run: aws lambda update-function-code --function-name <YourLambdaName> --s3-bucket <YourS3Bucket> --s3-key api.zip
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: ${{ secrets.AWS_DEFAULT_REGION }}
```

プッシュ後、デプロイが完了してるか確認できます。
完了していれば、S3に指定したバケットの直下にapi.zipが作成され、
Lambdaにも反映がされているはずです。

## 6. APIGatewayの作成
API Gatewayのサービスページにアクセスし、
APIタイプ選択から、RESTAPIで「構築」をします。

新しいAPIを選択し、自由にAPI名を入れましょう。

上部の「アクション」から「メソッドの作成」
→Anyを選択

ANYセットアップを以下のように行ってください
- Lambda関数を選択
- Lambdaプロキシ統合の使用にチェック
- Lambda関数に関数名を記入
- 右下部の「保存」ボタンをクリック

次に、アクションより「リソースの作成」を選択
最上部のチェックボックスにチェックを入れると、
自動でproxy設定を入力してくれるので、そのまま「リソースの作成」

最後に、アクションから、「APIのデプロイ」を選択し、以下を設定してください
- 「新しいステージ」
- ステージ名：任意（例: main）
「デプロイ」で完了です。

ステージページからURLが表示されるので、そのURLにアクセスし、
"Success!"と自分のFastAPIのResponseがかえってこれば成功です。


お疲れ様でした。