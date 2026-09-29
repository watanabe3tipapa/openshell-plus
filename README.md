# openshell-plus

**OpenShell を、ブラウザから。**

openshell-plus は [NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell) のサンドボックス管理とコマンド実行を、ブラウザだけのダッシュボードに閉じ込めた Web UI/UX です。FastAPI + Vanilla JS 製のアプリがローカル・Cloudflare Tunnel・Vercel・Google Colab のいずれでも同じコードで動きます。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v0.1.0-blue.svg)](https://github.com/watanabe3tipapa/openshell-plus/releases)
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-live-blue.svg)](https://watanabe3tipapa.github.io/openshell-plus/)
[![GitHub](https://img.shields.io/github/issues/watanabe3tipapa/openshell-plus.svg)](https://github.com/watanabe3tipapa/openshell-plus/issues)

[日本語](README.md) | [English](README_en.md)

**クイックリンク:** [公開サイト](https://watanabe3tipapa.github.io/openshell-plus/) · [Open in Colab](https://colab.research.google.com/github/watanabe3tipapa/openshell-plus/blob/main/deploy/colab/openshell_colab.ipynb) · [OpenShell 本体](https://github.com/NVIDIA/OpenShell) · [OpenShell ドキュメント](https://docs.nvidia.com/openshell/latest/)

## コンセプト

### なぜ「＋（プラス）」なのか

OpenShell は強いサンドボックス実行環境ですが、操作の入口は CLI と Clusters タブが中心で、「いま何が動いているか」を常に把握する負荷があります。openshell-plus はそこへブラウザの 1 画面を追加します。

**作る人（OpenShell）は変わらない。触る人（利用者）だけが楽になる。** それが「プラス」です。

| 営み | openshell-plus の対応物 |
|---|---|
| サンドボックスを作る | 名前・公開ポートを指定したフォームから `client.create()` |
| 状態を知る | `phase` を日本語ラベルへ変換した一覧（自動更新つき） |
| シェルで触る | WebSocket コンソールで stdout/stderr をストリーミング |
| 公開 URL を知る | 作成時に指定した公開ポートの URL を API から取得 |
| 片付ける | 確認ダイアログ付きの削除 |
| 公開する | loopback / Cloudflare Tunnel / Vercel / Colab の 4 形態 |

### 配置の選択肢

4 つのデプロイ形態は同じアプリコードから切り替わります。切り替えは `OSUI_MODE` と起動方法だけで完結し、コードの書き換えは不要です。

| 形態 | backend | 起動方法 | 用途 |
|---|---|---|---|
| ローカル | OpenShell | `./scripts/run-local.sh` → `http://127.0.0.1:8080` | 手元の gateway に実接続。ポートフォワード不要 |
| Cloudflare Tunnel | OpenShell | `./scripts/run-cloudflare.sh` | 手元の gateway を HTTPS で URL 化。トークン必須 |
| Vercel | demo | `./scripts/deploy-vercel.sh` | デモ・UI プレビュー。HTTPS 自動 |
| Google Colab | demo | ノートブック実行 → iframe 埋め込み | ブラウザだけでデモ。GPU ランタイム可 |

### ドキュメント訂正ツール

本リポジトリは「ガイドに書かれた擬似コードがそのまま動かない」という課題も扱います。`openshell-uiux-guide.html` に記載された擬似 API と実 SDK の差分を、実装コードの中に反映済みです。

- `SandboxSession(client, sandbox_id)` は存在しない（`client.create()` が `SandboxRef` を返す）
- get / list / delete / exec は `name` と `workspace` で識別する（UUID 直接指定は不可）
- `status.phase` は文字列ではなく enum（int）
- イメージは `--from` で明示する（既定は `nvcr.io/nvidia/base/ubuntu:24.04`）
- `openshell inference set` のようなコマンドは存在しない

## 主な特徴

### バックエンド

- `core/backends/base.py` に `SandboxBackend` Protocol を定義し、OpenShell SDK と in-memory demo の 2 実装を同じ契約で提供する
- `core/factory.py` が起動時に gateway へ `health` で接続し、到達できなければ demo へフォールバック（`OSUI_REQUIRE_GATEWAY=true` で fail-fast に切り替え可能）
- 同期 SDK を `asyncio.to_thread` でラップし、UI 側は完全に非同期
- `status.phase` は int enum。UI 向けに `phase_label()` で日本語ラベルへ変換

### API とトランスポート

- REST で CRUD、WebSocket でストリーミング exec、SSE で代替ストリーミングを提供
- **WebSocket が主経路**。Cloudflare Quick Tunnel が SSE 非対応のため、`OSUI_SSE_ENABLED=false` で無効化できる
- `/api/health` は認証なしで到達でき、ロードバランサの疎通確認に使える

### 認証と公開安全性

- `OSUI_AUTH_TOKEN` を設定すると全 `/api/*` と WebSocket ハンドシェイクが保護される
- **loopback 以外の bind ではトークンなし起動を拒否する**（`SettingsError`）。公開設定の事故を構成時点で防ぐ
- WebSocket はブラウザからヘッダを付けられないため、`Sec-WebSocket-Protocol: bearer.*` と `?token=` も受理
- mTLS と OIDC クライアント認証に対応し、loopback 以外の gateway に対する TLS 必須ルールを起動時に検証

### 同梱コンテンツ

- **[Google Colab で試すノートブック](deploy/colab/openshell_colab.ipynb)** — ブラウザだけでデモを起動。公開トンネルは意図的に無効
- **`policy/ui-policy.yaml`** — 現行スキーマ（`version: 1`）に沿った OpenShell policy
- **`deploy/Dockerfile.ui`** — OpenShell sandbox 内で UI を動かすためのイメージ
- **`deploy/cloudflared/config.yml.example`** — named tunnel の ingress 設定例
- **[LP](site/)** — GitHub Pages へ自動デプロイ
- **[構成図](site/diagrams/openshell-plus-architecture.html)** — ブラウザ → FastAPI → gateway → 隔離境界の全体像（Archify 生成、LP にも埋め込み済み）

## Colab で試す

リポジトリを clone しなくても、ブラウザだけでデモを動かせます。

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/watanabe3tipapa/openshell-plus/blob/main/deploy/colab/openshell_colab.ipynb)

- **ノートブック** [`deploy/colab/openshell_colab.ipynb`](deploy/colab/openshell_colab.ipynb) — セルを順に実行すると、パッケージ導入 → demo モードで起動 → ポート待機 → iframe 埋め込みまで一通り動く

## インストールと起動

### 前提条件

| ツール | 必要バージョン | 確認コマンド |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | 任意（推奨） | `uv --version` |
| [OpenShell CLI](https://docs.nvidia.com/openshell/dev/about/installation) | 最新 | `openshell --version` |
| Python | >= 3.12 | `python3 --version` |
| Docker / OrbStack | 任意（sandbox 実行時） | `docker info` |
| Git | 任意（デプロイ・貢献時） | `git --version` |

OpenShell CLI はパッケージマネージャ経由でも導入できます。

```bash
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh
openshell status
```

### 基本的な手順

1. リポジトリを取得

```bash
git clone https://github.com/watanabe3tipapa/openshell-plus.git
cd openshell-plus
```

2. 依存をインストール

```bash
uv sync --all-extras
```

3. 起動

```bash
./scripts/run-local.sh
```

`http://127.0.0.1:8080` を開いてください。gateway に到達できない場合は自動的に **demo mode**（in-memory サンドボックス）に切り替わるので、UI は常に操作できます。

ビルド的概念図（処理の流れ）:

```
Browser ──REST/WS──→ FastAPI ──→ Backend（OpenShell SDK / demo）
                                       │
                                       └→ OpenShell gateway → sandbox
```

### 主要コマンド

| コマンド | 用途 |
|---|---|
| `./scripts/run-local.sh` | loopback で起動（gateway 到達不能なら demo フォールバック） |
| `./scripts/run-cloudflare.sh` | named tunnel で起動（`quick` 引数で Quick Tunnel） |
| `./scripts/deploy-vercel.sh` | Vercel に本番デプロイ（トークン設定を事前チェック） |
| `uv run python -m openshell_ui` | スクリプトを使わず直接起動 |
| `uv run pytest` | テスト実行 |
| `uv run ruff check .` | lint |
| `uv run ruff format --check .` | 整形チェック |
| `uv run pyright` | 型チェック |

### 公開

`main` ブランチへの push で `site/` が自動的に GitHub Pages へデプロイされます（`.github/workflows/pages.yml`）。

## API

| メソッド | パス | 用途 |
|---|---|---|
| GET | `/api/health` | liveness・backend 種別・gateway 到達性（認証不要） |
| GET | `/api/config` | 実行モード・capabilities・ワークスペース・認証状態 |
| GET | `/api/sandboxes` | サンドボックス一覧 |
| POST | `/api/sandboxes` | サンドボックス作成 |
| GET | `/api/sandboxes/{name}` | 単一取得 |
| DELETE | `/api/sandboxes/{name}` | 削除 |
| POST | `/api/sandboxes/{name}/exec` | コマンド実行（集約結果） |
| WS | `/api/sandboxes/{name}/exec` | ストリーミング実行（主経路） |
| GET | `/api/sandboxes/{name}/exec/stream` | SSE 版 |

`{"command": ["ls","-la"], "workdir": null, "timeout_seconds": 60}` を送信し、`{"type": "stdout"|"stderr"|"exit", "data": "...", "exit_code": null|int}` を受信します。クライアントは再接続に備えてください（Vercel は `maxDuration` で切断します）。

## 環境変数

| 変数 | 既定値 | 説明 |
|---|---|---|
| `OSUI_MODE` | 自動判定 | `local` / `cloudflare` / `vercel` / `colab` / `sandbox` |
| `OSUI_HOST` / `OSUI_PORT` | `127.0.0.1` / `8080` | バインド先。loopback 以外はトークンが必須 |
| `OSUI_AUTH_TOKEN` | （任意） | 設定すると全 API とコンソールが保護される |
| `OSUI_DEMO` | `false` | `true` で demo backend を強制 |
| `OSUI_REQUIRE_GATEWAY` | `false` | `true` で demo フォールバックを禁止 |
| `OSUI_WORKSPACE` | `default` | 操作対象ワークスペース |
| `OSUI_SSE_ENABLED` | `true` | SSE エンドポイントの公開可否 |
| `OSUI_GATEWAY_ENDPOINT` | （SDK 自動検出） | 明示的に gateway を指定する場合に使用 |
| `OSUI_GATEWAY_CA_CERT` / `_CERT` / `_KEY` | （任意） | CA 検証と mTLS。`_CERT` と `_KEY` は同時指定が必須 |
| `OSUI_OIDC_ISSUER` / `_CLIENT_ID` / `_CLIENT_SECRET` / `_AUDIENCE` | （任意） | OIDC クライアント認証 |

全項目は `.env.example` を参照してください。

## ドキュメント

初心者は次の順で読むと全体像が把握しやすいです。

1. [公開サイト（LP）](https://watanabe3tipapa.github.io/openshell-plus/) — 機能一覧・デプロイ形態・環境変数
2. `README.md`（本書）— コンセプトと運用
3. `openshell-uiux-guide.html` — 元の UI/UX ガイド
4. [DEV-MEMO.md](DEV-MEMO.md) — フェーズごとの設計判断と検証記録
## コントリビューション

コントリビューションは歓迎します。大きな変更を行う前に [Issue](https://github.com/watanabe3tipapa/openshell-plus/issues) を立てて相談してください。一般的な手順:

1. リポジトリをフォーク
2. 機能ブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. 品質ゲートをすべて通す
5. ブランチをプッシュし、Pull Request を作成

```bash
uv sync --all-extras
uv run pytest        # 147 テスト
uv run ruff check .
uv run ruff format --check .
uv run pyright       # 型チェック（エラー 0）
```

テストは demo backend を使い、gateway には接続しません。`OSUI_DEMO=true` 相当の
設定は `tests/helpers.py` の `make_settings()` が保証しています。

## 連絡先

- GitHub: https://github.com/watanabe3tipapa/openshell-plus
- 公開サイト: https://watanabe3tipapa.github.io/openshell-plus/

## ライセンス

MIT ライセンス — 詳細はリポジトリの [LICENSE](LICENSE) ファイルを参照してください。
