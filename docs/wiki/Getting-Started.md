# はじめに

## 動作環境

- **OS**: Windows 10/11、macOS、Linux
- **Python**: 3.10以上（3.12推奨）
- **メモリ**: 4GB以上推奨

## インストール

### 1. リポジトリのクローン

```bash
git clone https://github.com/yukihina1587/kototsuna-bot.git
cd kototsuna-bot
```

### 2. 依存ライブラリのインストール

```bash
pip install -r requirements.txt
```

### 3. 必要なAPIキーの取得

#### Twitch Client ID

1. [Twitch Developers](https://dev.twitch.tv/console)にアクセス
2. 「アプリケーション」→「アプリケーションを登録」
3. 以下を入力:
   - **名前**: 任意（例: `MyTranslateBot`）
   - **OAuthリダイレクトURL**: `http://localhost:8787/redirect.html`
   - **カテゴリ**: `チャットボット`
4. 作成後、**クライアントID**をコピー

#### DeepL API Key

1. [DeepL公式サイト](https://www.deepl.com/pro-api)にアクセス
2. アカウント作成（Free版でOK）
3. API Keyをコピー

### 4. 起動

```bash
python main.py
```

## 初回設定

1. GUIが起動したら、右パネルの「設定」を開く
2. **Twitch Client ID**を入力
3. **DeepL API Key**を入力
4. **トークン認証**ボタンをクリック
5. ブラウザでTwitch認証を完了
6. **チャンネル名**を入力
7. **BOT起動**ボタンをクリック

## オプション設定

### VOICEVOX（高品質読み上げ）

1. [VOICEVOX公式サイト](https://voicevox.hiroshiba.jp/)からダウンロード
2. インストール・起動
3. GUIの設定パネルでパスを設定（自動検出も可能）

### Gladia API（高品質音声認識）

1. [Gladia公式サイト](https://www.gladia.io/)でアカウント作成
2. API Keyを取得（月10時間まで無料）
3. GUIの設定パネルに入力

## 次のステップ

- [機能一覧](Features)で詳細な機能を確認
- [設定](Configuration)でカスタマイズ
