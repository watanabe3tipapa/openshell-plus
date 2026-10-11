# Changelog

このプロジェクトの変更履歴です。形式は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)、
バージョンは [Semantic Versioning](https://semver.org/lang/ja/) に従います。

## [Unreleased]

## [0.1.3] - 2026-10-11

### Added

- LP に操作デモ GIF（`site/screenshots/demo.gif`）を追加。サンドボックス作成 → 一覧反映 →
  コンソールでのコマンド実行を録画（demo backend、約 9 秒）
- LP を 3 ページに分割。`site/index.html`（概要）/ `site/reference.html`（環境変数・
  API 差分・エラー対処・リポジトリ構成）/ `site/security.html`（認証方式・mTLS/OIDC・
  公開前チェックリスト）
- サイト共通ナビゲーション（現在地を `aria-current` で表示）と、各ページの目次を追加

### Changed

- README / README_en のドキュメント一覧を 3 ページ構成に更新

### Fixed

- `USAGE.md` の誤字・混入文字を修正（「各省」→「各所」、「緩めた量为」→「緩めた分が」）

## [0.1.2] - 2026-10-11

### Added

- LP（`site/index.html`）に固定ナビゲーションと目次を追加し、ページ内移動を改善
- LP にダッシュボードの実スクリーンショットを掲載（`site/screenshots/dashboard.png`）
- LP に「エラーと対処」セクションを追加（401 / 404 / 422 / 503 / WS 4401）
- 構成図に静的 SVG 版（`site/diagrams/openshell-plus-architecture.svg`）と `<noscript>` フォールバックを追加
- SEO / SNS 用メタタグ（`canonical` / `og:image` / `twitter:card` / `og:url` など）と
  `site/og-image.png`、`site/apple-touch-icon.png` を追加
- `CONTRIBUTING.md`、`CHANGELOG.md`、GitHub Issue / PR テンプレートを新設
- CI ワークフロー（`.github/workflows/test.yml`）を追加（pytest + coverage / ruff / pyright）
- カバレッジ計測（pytest-cov、目標 70%）を導入
- README に「uv を使わない場合」の pip インストール手順を追記

### Changed

- **WebSocket / REST / SSE の URL クエリトークン（`?token=`）受付を既定で無効化**
  （`OSUI_ALLOW_QUERY_TOKEN=false`）。同梱 UI の WebSocket 認証を
  `Sec-WebSocket-Protocol: bearer.*` に変更（`src/openshell_ui/ui/assets/app.js`）
- 同梱 UI に「DEMO MODE」バナーを追加。demo backend 稼働時に常時表示し実データと区別可能に

### Security

- 認証トークンがアクセスログ・ブラウザ履歴・Referer に残る `?token=` の利用を既定で禁止。
  必要な互換用途向けに `OSUI_ALLOW_QUERY_TOKEN` を用意（推奨しません）

## [0.1.1] - 2026-09-29

### Added

- `USAGE.md`（目的別レシピ・制約・トラブルシューティング）
- macOS + OrbStack の環境構築手順と AI エージェント運用の解説（README / README_en）
- 公開サイトのライトテーマ化と構成図のライトテーマ埋め込み

### Fixed

- `deploy/Dockerfile.ui` の `ENV OSUI_MODE=web` → `sandbox`（存在しない値を修正）
- README / USAGE / DEV-MEMO / ノートブックの文書と実装の食い違い 7 件を修正
- 誤字・全角記号・中国語混入（9 箇所）を修正

## [0.1.0] - 2026-09-29

### Added

- 初回リリース。FastAPI + Vanilla JS のダッシュボード（サンドボックス一覧 / 作成 / 削除 / コンソール）
- REST + WebSocket（主経路）+ SSE の 3 トランスポート
- OpenShell SDK と in-memory demo を同じ契約で扱う `SandboxBackend` 抽象化
- 認証（Bearer / `Sec-WebSocket-Protocol` / `?token=`）と loopback 以外 bind 時の token 強制
- デプロイ資産（Cloudflare Tunnel / Vercel / Colab / Dockerfile）と GitHub Pages LP
- OpenShell policy（`policy/ui-policy.yaml`）とドキュメント訂正ツール（README §差分）

[Unreleased]: https://github.com/watanabe3tipapa/openshell-plus/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/watanabe3tipapa/openshell-plus/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/watanabe3tipapa/openshell-plus/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/watanabe3tipapa/openshell-plus/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/watanabe3tipapa/openshell-plus/releases/tag/v0.1.0