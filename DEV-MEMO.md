# DEV-MEMO

このドキュメントは openshell-plus の設計意図・決定事項・進捗を作業フェーズごとに追録するメモです。
追録は各フェーズの完了時に追記します。事実の出典は「出典」節に URL で明記します。

---

## Phase 0: 要件確定とドキュメント調査（2026-09-29）

### 目的
`openshell-uiux-guide.html`（日本語の UI/UX ガイド）を出発点に、NVIDIA OpenShell をブラウザから操作する
Web UI/UX を実装する。ガイドの擬似コードが実 SDK と食い違う箇所を確定する。

### 確定した要件（ユーザー確認済み）

| # | 決定事項 |
|---|---|
| Q1 | a — demo backend ＋ 接続自動検出（フォールバック） |
| Q2 | Cloudflare Tunnel / Vercel / Google Colab の全対応 |
| Q3 | Gradio 不使用。Vanilla JS の自作コンソール |
| Q4 | `OSUI_AUTH_TOKEN` 必須。公開 bind 時はトークンなし起動を拒否 |
| Q5 | OpenShell CLI/gateway の本機導入は許可（実施前に再確認） |
| Q6 | 保留 |
| Q7 | a — LP は同一リポジトリの `site/` |
| Q8 | a — Colab は iframe のみ。公開トンネルは警告付きで無効 |
| Q9 | a — Vercel は demo backend を許容 |

### ガイドと実 SDK の差分（実装の前提）

ガイドの擬似 API は以下が誤り。実装は実 SDK に合わせた。

| ガイドの記述 | 実際の API |
|---|---|
| `SandboxSession(client, sandbox_id)` | 存在しない。`client.create()` が `SandboxRef` を返す |
| id で識別 | `name` + `workspace` で識別（UUID 直接指定は不可） |
| `status.phase` は文字列 | int enum |
| イメージ既定 | `--from` で明示。既定は `nvcr.io/nvidia/base/ubuntu:24.04` |
| `openshell inference set` | 存在しない |
| `provider profile import` | 正しくは `openshell profile import --url <URL>` |
| `service unexpose` | 正しくは `service delete` |
| gateway 既定ポート `18080` | パッケージ既定の TLS ポートは `17670`（`gateway add` の例では `18080` も使われる） |

実 SDK のシグネチャは `openshell==0.1.2` をインストールして `inspect` で確認した。

```python
SandboxClient(endpoint, *, tls=None, bearer_token=None, client_credentials=None,
              timeout=30.0, cluster_name=None)
  .create(*, workspace, spec=None, name=None, labels=None, service_exposures=None)
  .list(*, workspace, page_size=100, page_token="", label_selector=None)
  .delete(name, *, workspace, allow_missing=False)
  .exec(sandbox, command, *, workspace, stream_output=False, workdir=None,
        env=None, stdin=None, timeout_seconds=None, no_login_shell=False)
  .exec_stream(sandbox, command, *, workspace, ...) -> Iterator[ExecChunk | ExecResult]
  .list_all(*, workspace, label_selector=None)
SandboxClient.from_active_cluster(...)
```

### 環境の事実

- uv 0.11.31 / Python 3.14.7
- Docker CLI 29.4 は導入済みだが **daemon は停止中**
  （`/Users/watanabe3tipapa/.orbstack/run/docker.sock` が存在しない）
- `openshell` CLI 未導入、`~/.config/openshell` 未作成
- Vercel CLI はログイン済み（`watanabe3tipapa`）
- `cloudflared` 未導入

### 出典

- `https://github.com/NVIDIA/OpenShell`
- `https://docs.nvidia.com/openshell/latest/index.html`
- `https://docs.nvidia.com/openshell/latest/about/architecture`
- `https://docs.nvidia.com/openshell/latest/about/installation`
- `https://docs.nvidia.com/openshell/latest/how-it-works/sandboxes/overview`

---

## Phase 1: プロジェクト基盤（2026-09-29）

### 実装構造

```
openshell-plus/
  pyproject.toml              # hatchling, uv, ruff/pyright/pytest 設定, Vercel entrypoint
  .env.example                # OSUI_* 全変数の DOCUMENTED 一覧
  vercel.json                 # functions.api/index.py maxDuration=300
  api/index.py                # Vercel 用 ASGI re-export
  src/openshell_ui/
    __main__.py               # python -m openshell_ui エントリポイント
    main.py                   # create_app(), lifespan, 例外ハンドラ, 静的配信
    core/
      config.py               # Settings, is_loopback_host, validate_startup
      mode.py                 # RunMode, in_colab, detect_mode
      factory.py              # OpenShell 試行 → demo フォールバック
      backends/
        base.py               # SandboxBackend Protocol, SandboxView, ExecRequest/Event
        demo.py               # in-memory DemoBackend
        openshell_backend.py  # 同期 SDK の非同期ラッパ
    api/
      auth.py                 # Bearer / Sec-WebSocket-Protocol / ?token=
      meta.py                 # /api/health, /api/config
      sandboxes.py            # CRUD
      exec.py                 # POST / WS / SSE
    ui/                       # 同梱ダッシュボード
  deploy/                     # cloudflared/, Dockerfile.ui, colab/
  policy/ui-policy.yaml
  scripts/                    # run-local / run-cloudflare / deploy-vercel
  site/                       # GitHub Pages LP
  tests/
```

### 設計上の決定

1. **backend を Protocol で抽象化する。** OpenShell SDK と demo が同じ `SandboxBackend` 契約を満たすため、
   ルートや UI に `if demo` 分岐を書かない。
2. **同期 SDK を `asyncio.to_thread` でラップする。** OpenShell Python SDK は同期 API のみ。
   `exec_stream` はジェネレータなので `to_thread` の中 consuming して `async for` へ橋渡しする。
3. **`phase` は UI 層で必ず `phase_label()` を通す。** int enum をそのまま UI に出さない。
4. **公開 bind は `SettingsError` で拒否する。** `Settings.validate_startup()` を `create_app()` の先頭で呼ぶ。
5. **WebSocket を主経路にする。** Cloudflare Quick Tunnel が SSE 非対応のため。
6. **`/api/health` のみ認証対象外。** LB からの疎通確認を可能にするため。
7. **静的アセットは CDN に載せない。** `[tool.vercel.fastapi.static] cdn = false` で token 検査の迂回を防ぐ。

### 検証

- `uv sync --all-extras` 完了（`openshell==0.1.2`, `openshell-ui==0.1.0`）
- 初回は `OSError: Readme file does not exist: README.md` で失敗 → README 作成で解消
- `__init__.py` 作成前の空 wheel で `ModuleNotFoundError: No module named 'openshell_ui'`
  → `uv sync --all-extras --reinstall-package openshell-ui` で解消（editable install を確認）
- `python -m openshell_ui` での起動を確認（`__main__.py` 追加後）

---

## Phase 2: API・UI の実装とスモーク検証（2026-09-29）

### 検証した経路

`uvicorn` を起動し、以下を実際に叩いて確認した。

| 検証 | 結果 |
|---|---|
| `GET /api/health` | 200 |
| `GET /api/config` | 200 |
| `POST /api/sandboxes` | 201（`demo-agent` が `provisioning` で作成） |
| `GET /api/sandboxes` | 200（`phase=provisioning`） |
| `POST /api/sandboxes/{name}/exec` | 200 / `exit_code=0` |
| `WS /api/sandboxes/{name}/exec` | `stdout` → `stdout` → `exit` の 3 イベント |
| `GET /api/sandboxes/{name}/exec/stream` | SSE データ受信 |
| `DELETE /api/sandboxes/{name}` | 204 |
| 削除後の `GET` | 404 |
| `GET /`、`/assets/app.js`、`/favicon.svg` | 200 |

### 既知の制約

- `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated` が出るが動作する。
- `tests/` は空だった。Phase 5 で 147 テストを追加し、`pytest` / `ruff` / `pyright` を
  すべて green にした。

---

## Phase 3: デプロイ資産（2026-09-29）

### 資産

| ファイル | 役割 |
|---|---|
| `deploy/cloudflared/config.yml.example` | named tunnel の ingress 例（`ui.example.com` → `localhost:8080`） |
| `deploy/Dockerfile.ui` | OpenShell sandbox 内で UI を動かすイメージ。既定 base image は `nvcr.io/nvidia/base/ubuntu:24.04` |
| `deploy/colab/openshell_colab.ipynb` | Colab で demo モード起動 → iframe 埋め込み |
| `policy/ui-policy.yaml` | `version: 1` の policy（filesystem / landlock / process / network_policies） |
| `scripts/run-local.sh` | loopback 起動。非 loopback なら token を自動生成 |
| `scripts/run-cloudflare.sh` | named / quick tunnel 起動。quick では `OSUI_SSE_ENABLED=false` を自動設定 |
| `scripts/deploy-vercel.sh` | `OSUI_AUTH_TOKEN` 未設定を事前チェックしてから `vercel deploy --prod` |

### Colab で公開トンネルを使わない理由

Colab の FAQ は次を禁じている。

- インタラクティブな計算と無関係なファイルホスティング／Web サービス提供
- 無料枠での「ノートブック UI を迂回して Web UI を主眼として操作すること」
- リモートプロキシへの接続

加えて恒久トンネルは VM リセットで切れ、アイドルでランタイムも終了する。
notebook 内には tunnel cell を**コメントアウトで残置**し、既定では実行しない。

### 残課題

- `policy/ui-policy.yaml` の `access: read-only` / `allow_encoded_slash` などのフィールドが
  現行スキーマに厳密適合するか未検証（gateway 起動後に確認が必要）。
- `deploy/Dockerfile.ui` の `ARG BASE_IMAGE` は MicroVM ドキュメントの値をそのまま使っている。
  公式ページで既定 workload イメージは `nvcr.io/nvidia/base/ubuntu:24.04` と確認済み。

---

## Phase 4: LP・README（2026-09-29）

### README の構成

`watanabe3tipapa/quarto-plus` の README 構成に倣う。

- `README.md` … 日本語（メイン）
- `README_en.md` … 英語（サブ）
- バッジ 4 枚（License / Version / GitHub Pages / GitHub Issues）
- 言語切替行 `[日本語](README.md) | [English](README_en.md)`
- クイックリンク行
- `## コンセプト`（なぜ「＋」か／配置の選択肢／ドキュメント訂正ツール）
- `## 主な特徴` → `## Colab で試す` → `## インストールと起動` → `## API`
  → `## 環境変数` → `## ドキュメント` → `## コントリビューション` → `## 連絡先` → `## ライセンス`
- `LICENSE` は MIT / Copyright (c) 2026 watanabe3tipapa

### GitHub Pages

`.github/workflows/pages.yml` は quarto-plus と同じ構成（`actions/checkout@v5`、
`actions/configure-pages@v6`、`actions/upload-pages-artifact@v5`、`actions/deploy-pages@v4`、
`concurrency: group: pages`）。ビルドは `site/` を `_site/` にコピーするだけ。
ビルド不要なので `paths:` フィルタは付けず、`main` への push で常に実行する（quarto-plus と同一方針）。

### LP に「OpenShell とは何か」を追加した経緯

初版の LP は機能紹介が中心で、前提知識がなかった読者に OpenShell が何なのか伝わりなかった。
`docs.nvidia.com/openshell/latest/index.html` と `about/architecture` を根拠に、
脅威と対策・多層防御・構成要素・ネットワーク要求の流れ・ランタイム別の境界の作り方・
コンポーネント間の認証を、根拠付きで書き起こした。

### タイポ／整合性の総点検で発見した誤り

| 種別 | 内容 |
|---|---|
| 簡体字混入 | 「対話」の簡体字表記（対话）を「対話」に修正。※本表は誤りの実例を意図的に引用しているため、混入スキャンの検出対象 |
| 生成ノイズ | `エージェント群（fleets of autonomous AI agents）` など 6 箇所 |
| 述語漏れ | `構築。判断はしない` / `渡す` / `記述する` / `CI で使える` |
| 見出し不一致 | `3 つのデプロイ形態` だがテーブルは 4 行 |
| 実装との不一致 | 作成フォームにイメージ欄が無いのに LP に「イメージ指定」と書いていた |
| 実装との不一致 | `ExecRequest` に `env` が無いのに LP に `env` 指定と書いていた |
| 実装との不一致 | `__main__.py` が無いのに `python -m openshell_ui` と書いていた |
| 実装との不一致 | 停止 API が無いのに「停止・削除」と書いていた |
| 欠落アセット | `og:image` が指す `ogp.png` / `site/favicon.svg` が未作成 |
| CSS 未定義 | `.muted` を 9 箇所で使用しているが `style.css` に定義なし |
| 壊れるリンク | `README_en.md` / `DEV-MEMO.md` が未作成なのにリンク済み |
| 機械翻訳調 | `reach 不達` / `loophole なし` / `ホーム不要` / `sample データ` |

点検スクリプト（簡体字・Cyrillic・Hangul 混入 Detector、HTML タグ整合性、
相対参照の欠落）で全ファイルを走査し、最終的に **混入 0 件・タグ不整合 0 件・欠落参照 0 件** を確認。

---

## Phase 5: 構成図と品質ゲート（2026-09-29）

### 構成図（Archify）

- `site/diagrams/openshell-plus-architecture.html` を Archify の `architecture`
  タイプで生成し、`site/index.html` の「構成図」節に iframe と全画面リンクを埋め込んだ。
- 12 ノード（browser / edge / app / auth / sdk / factory / demo / gateway /
  supervisor / approved / sandbox / agent）、11 接続、3 つの境界。
- 初回 validate でラベル 17 件の重なりが出たので、**行間と列間を拡張して通路幅を
  広めに確保** → 一部ラベルの語数を圧縮 → 縦方向ラベルの `labelDy` 調整、の順に直した。
- 最終結果: `checks 9/9`、`composition: showcase / errors 0 / warnings 0`、
  `minLabelRouteClearance 48.5`。
- `visual-check` は 1440x900 と 1600x1000 の縦はみ出し（scrollHeight 979）で落ちたため、
  行間を 4 段 × 200px から 4 段 × 160px に詰めて合格させた。
- **残制約**: `visualReview` は `pending` のまま。自動ブラウザ計測は通っているが、
  人が目視確認する工程は未実施（`visual-check` は画像を読まないため）、
  **没入時の動き（trace motion）は未検証**。

### 品質ゲート

| ゲート | 結果 |
|---|---|
| `uv run pytest` | 147 passed |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 30 files already formatted |
| `uv run pyright` | 0 errors, 0 warnings |

- `tests/` を新設。`helpers.py` に `make_settings()` / `make_client()`、
  `conftest.py` に `open_client` / `secured_client` fixture と環境変数の隔離を分離した。
- 追加した `pyyaml` dev 依存は `policy/ui-policy.yaml` を実際にパースして検証するため。

### テスト実行中に発見したバグと修正

1. **`openshell_backend.py:197` — `ref.created_from_workload_template` を未防御アクセス。**
   同じファイルでは他の任意フィールドをすべて `getattr(..., None)` で守って
   いるのに、ここだけ直属性で古い SDK の ref では `AttributeError` → 502 になっていた。`getattr` に統一。
2. **`api/exec.py` / `api/sandboxes.py` — 未実装フィールドを黙って捨てていた。**
   pydantic の既定は `extra="ignore"` なので、`env` を渡しても 200 で受理していた。
   README・LP は「`env` は未実装」と明記しているのに API は受理していたという齟齬がある。
   `ConfigDict(extra="forbid")` で 422 に変更。
3. **`api/auth.py` — `Settings` の import 漏れ。**
   `from __future__ import annotations` があるため実行時は潜伏し、pyright で
   `undefined variable` として検出された。
4. **`main.py:65` — `app.state.mode: RunMode = mode` は不正な型注釈。**
   ローカル変数を `mode: RunMode = ...` として型情報を残す形に直した。

### その他の修正

- `scripts/*.sh` に実行権限（`chmod +x`）を付与。`bash -n` は 3 本とも通過。
- `deploy/colab/openshell_colab.ipynb` cell 1: GitHub からの `pip install git+` は
  リポジトリが public かつ push 済みでないと失敗する。`check=False` にして
  失敗時に原因を明示する `SystemExit` に変更（未 push 状態での失敗が黙って進まない）。
- `pyproject.toml`: `asyncio_mode = "auto"`（pytest-asyncio 不在で警告）と
  notebook を触る `ruff format` を除外。

## 未対応（設計・設定項目として残す）

- `src/openshell_ui/api/exec.py` の WebSocket ハンドシェイクで、`Sec-WebSocket-Protocol` の
  token 位置が 2 番目以降の場合に echo する subprotocol がずれる可能性がある
- `policy/ui-policy.yaml` のスキーマ適合性が未検証
- `vercel build` による `api/index.py` と `[tool.vercel] entrypoint` の優先順位が未検証
