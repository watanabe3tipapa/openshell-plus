# コントリビューションガイド

openshell-plus へのコントリビューションを歓迎します。PR を出す前に、このガイドと
[README.md](README.md) の「ドキュメント訂正ツール」「コントリビューション」を一読してください。

## 開発環境の構築

Python 3.12 以上と [uv](https://docs.astral.sh/uv/) が必要です。

```bash
git clone https://github.com/watanabe3tipapa/openshell-plus.git
cd openshell-plus
uv sync --all-extras
```

依存関係は `uv.lock` で固定されています。`uv sync --all-extras` で dev 依存
（pytest / ruff / pyright / pyyaml / pytest-cov）まで一式入ります。

## 品質ゲート

PR を出す前に、以下をすべて local で green にしてください。CI（`.github/workflows/test.yml`）でも同じゲートを実行します。

```bash
uv run pytest                    # テスト + カバレッジ（目標 70% 以上）
uv run ruff check .              # lint
uv run ruff format --check .     # 整形チェック
uv run pyright                   # 型チェック（エラー 0）
```

- テストは demo backend のみを使い、OpenShell gateway には接続しません。
  `tests/helpers.py` の `make_settings()` がそのための設定を保証しています。
- カバレッジの目標は **70% 以上**です。新規ロジックにはテストを追加してください。
- フォーマットの自動適用は `uv run ruff format .` で行えます。

## ブランチとコミット規約

- ブランチ名: `feature/<概要>` / `fix/<概要>` / `docs/<概要>`（例: `feature/demo-banner`）
- コミットメッセージは Conventional Commits に従ってください。
  例: `feat: demo backend 稼働時に DEMO MODE バナーを表示` / `fix: WebSocket のクエリトークン受付を既定無効化`
- 1 つの PR は 1 つの論理的な変更にまとめてください。

## PR の流れ

1. リポジトリをフォークし、機能ブランチを切る
2. 変更をコミットする（このガイドの規約に従う）
3. 品質ゲートをすべて通す
4. ブランチをプッシュし、`.github/PULL_REQUEST_TEMPLATE.md` に沿って Pull Request を作る
5. CI が green になるまで反復する

## 変更の規模が大きい場合

挙動を変える変更（API・環境変数・認証まわりなど）は、作業前に
[Issue](https://github.com/watanabe3tipapa/openshell-plus/issues) で方針を相談してください。

## ドキュメントを更新するとき

- ユーザー向けの新機能・設定は `README.md` / `README_en.md` / `USAGE.md` / `.env.example` に反映する
- 環境変数は `Settings` のフィールドと 1 対 1 を保つ
- 設計判断の根拠・検証記録は `DEV-MEMO.md` に追記する
- リリース時の変更は `CHANGELOG.md` に追記する

## ライセンス

コントリビューションは MIT ライセンス（`LICENSE`）の下で提供されたものとみなします。