# openshell-plus

**OpenShell を、ブラウザから。**

openshell-plus は [NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell) のサンドボックス管理とコマンド実行を、ブラウザだけのダッシュボードに閉じ込めた Web UI/UX です。FastAPI + Vanilla JS 製のアプリがローカル・Cloudflare Tunnel・Vercel・Google Colab のいずれでも同じコードで動きます。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-v0.1.1-blue.svg)](https://github.com/watanabe3tipapa/openshell-plus/releases)
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-live-blue.svg)](https://watanabe3tipapa.github.io/openshell-plus/)
[![GitHub](https://img.shields.io/github/issues/watanabe3tipapa/openshell-plus.svg)](https://github.com/watanabe3tipapa/openshell-plus/issues)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/watanabe3tipapa/openshell-plus/blob/main/deploy/colab/openshell_colab.ipynb)

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
- **[USAGE.md](USAGE.md)** — 目的別の活用レシピ・制約・トラブルシューティング
- **[構成図](site/diagrams/openshell-plus-architecture.html)** — ブラウザ → FastAPI → gateway → 隔離境界の全体像（Archify 生成、LP にも埋め込み済み）

## Colab で試す（3 ステップ・clone 不要）

ブラウザだけでデモを動かせます。ローカルへの clone もビルドも不要です。

| 手順 | 操作 | 目安 |
|---|---|---|
| 1 | 下のバッジをクリックして Colab でノートブックを開く | 数秒 |
| 2 | メニュー「ランタイム」から「すべてのセルを実行」を選ぶ | 1〜2 分 |
| 3 | 出力セルの下に iframe でダッシュボードが現れる | 画面はそのまま |

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/watanabe3tipapa/openshell-plus/blob/main/deploy/colab/openshell_colab.ipynb)

3 が完了したら、一覧の「新規作成」で `demo-box` を作り、コンソールに `ls` を入力して「実行」を押してください。demo 応答が返れば起動は成功です。

セルは依存順に並んでおり、個別に選ぶ必要はありません。各セルが内部で行っていることは次の 4 つです。

1. `git+https://github.com/watanabe3tipapa/openshell-plus` からパッケージを導入
2. `OSUI_DEMO=true` と `OSUI_MODE=colab` を設定して uvicorn を起動
3. `127.0.0.1:8080` が接続を受けるまで最大 30 秒待つ
4. ダッシュボードを iframe に埋め込む

**実行前に知っておいてください**

- **ランタイムはアイドルで自動終了し、VM がリセットされても消えます。** 続きから試すときは「すべてのセルを実行」をもう一度実行してください
- Colab には Docker daemon も OpenShell gateway もないため、demo backend で起動します。実 sandbox の操作は発生しません
- 公開トンネルは意図的に無効です。Colab の利用規約に抵触するため（理由は [USAGE.md](USAGE.md) とノートブック内に記載）
- ファイル: [`deploy/colab/openshell_colab.ipynb`](deploy/colab/openshell_colab.ipynb)

GPU ランタイムでも同じ手順で動きます。デモの画面と応答は GPU に依存しません。

## インストールと起動

### 前提条件

| ツール | 必要バージョン | 確認コマンド |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | 任意（推奨） | `uv --version` |
| [OpenShell CLI](https://docs.nvidia.com/openshell/dev/about/installation) | 最新 | `openshell --version` |
| Python | >= 3.12 | `python3 --version` |
| Docker Engine | 任意（sandbox 実行時。OpenShell は 28.0 以降を要求） | `docker version` |
| [OrbStack](https://orbstack.dev/) | 任意（macOS で Docker を使う場合の推奨手段） | `orb version` |
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

## macOS + OrbStack での環境構築

macOS で sandbox を実際に動かす場合、[OrbStack](https://orbstack.dev/) を Docker ランタイムに使うと手順が最も短くなります。Docker Desktop と同じ `docker` コマンドをそのまま使えます。

### 1. OrbStack を導入する

```bash
brew install orbstack
open -a OrbStack
```

GUI を使わずに起動・停止する場合は `orb` コマンドを使います（CI やヘッドレス環境向け）。

```bash
orb            # 起動（orb start と同じ）
orb stop       # 停止
```

GUI が無いと自動更新は動きません。CLI だけで運用する場合は Homebrew 側から更新します。

```bash
brew upgrade --greedy orbstack
```

### 2. Docker engine の稼働を確かめる

```bash
orb version
docker context ls
docker info
```

OrbStack は `orbstack` という Docker context を作り、ターミナルからの `docker` コマンドは自動的にそれを使います。`docker context ls` に `orbstack` が無い場合は明示的に切り替えます。

```bash
docker context use orbstack
```

`docker info` が応答しない場合は engine が停止しています。

```bash
orb start
orb restart docker
orb logs docker
```

**OpenShell は Docker Engine 28.0 以降を要求します。** バージョンを確認します。

```bash
docker version --format 'server: {{.Server.Version}}'
```

### 3. socket のパスを確かめる（macOS で最も失敗しやすい箇所）

OpenShell の Docker driver は `socket_path` を指定しなければ自動でソケットを探し、`/var/run/docker.sock` を優先します。しかし OrbStack が `/var/run/docker.sock` の symlink を作るのは**管理者権限が使える場合だけ**です。権限がない環境ではこの symlink が作られず、OpenShell 側がソケットを見つけられずに sandbox 作成へ進めません。

```bash
ls -l /var/run/docker.sock 2>/dev/null || echo '未作成'
```

`未作成` と表示された場合は、gateway の設定ファイルで OrbStack のソケットを明示します。gateway はまず `~/.config/openshell/gateway.toml` を読み、無ければ Homebrew の設定先（`$(brew --prefix)/var/openshell/gateway.toml`）を使います。`~/.config/openshell/gateway.toml` を置けば確実です。

```bash
mkdir -p ~/.config/openshell
```

`~/.config/openshell/gateway.toml`:

```toml
[openshell]
version = 2

[openshell.gateway]
compute_driver = "docker"

[openshell.drivers.docker]
socket_path = "/Users/あなたのユーザー名/.orbstack/run/docker.sock"
```

**TOML は `~` やシェル変数を展開しません。** 絶対パスをそのまま書く必要があります。実際の値は次のコマンドで確認できます。

```bash
echo "$HOME/.orbstack/run/docker.sock"
```

編集後は gateway を再起動する前に preflight で検証します。

```bash
openshell-gateway config preflight --path ~/.config/openshell/gateway.toml
```

### 4. OpenShell gateway を導入する

```bash
curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh
openshell status
```

macOS では Homebrew 経由で導入され、gateway は Homebrew service として `https://localhost:17670` で動きます。

```bash
brew services list
brew services restart openshell
```

### 5. openshell-plus を起動する

```bash
git clone https://github.com/watanabe3tipapa/openshell-plus.git
cd openshell-plus
uv sync --all-extras

export OSUI_GATEWAY_ENDPOINT=127.0.0.1:17670
export OSUI_REQUIRE_GATEWAY=true
./scripts/run-local.sh
```

`OSUI_REQUIRE_GATEWAY=true` を付けると、接続に失敗したときに demo backend へ静かに落ちるのを防げます。実際に接続できたかは `/api/health` の `backend` が `openshell` かどうかで確認します。

```bash
curl -s http://127.0.0.1:8080/api/health | python3 -m json.tool
```

### 6. CPU アーキテクチャの確認

```bash
uname -m
```

| 出力 | 意味 | image の扱い |
|---|---|---|
| `arm64` | Apple Silicon | OrbStack が Rosetta で x86_64 image を実行します。`linux/amd64` のみの image でも動きます |
| `x86_64` | Intel Mac | `linux/amd64` が既定です。`linux/arm64` のみの image は動きません |

OpenShell の既定 sandbox イメージ `nvcr.io/nvidia/base/ubuntu:24.04` はマルチアーキテクチャ対応なので、どちらの Mac でも動きます。amd64 に固定したい場合は環境変数を使います。

```bash
export DOCKER_DEFAULT_PLATFORM=linux/amd64
```

### トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `docker info` が応答しない | engine が停止中 | `orb start` → `orb restart docker` → `orb logs docker` |
| `docker context ls` に `orbstack` が無い | CLI を単体で導入した | `brew reinstall orbstack` して context を作り直す |
| sandbox 作成が Docker 接続エラーで失敗 | `/var/run/docker.sock` が無い | §3 のとおり `socket_path` を TOML に書く |
| TOML を変えても反映されない | 設定ファイルの場所が違う | `~/.config/openshell/gateway.toml` に置く。解決順は `--config` / `OPENSHELL_GATEWAY_CONFIG` → TOML → 既定値 |
| `openshell status` が接続できない | Homebrew service が停止 | `brew services restart openshell` |
| `server: 27.x` と表示される | Engine が 28.0 未満 | OrbStack を最新版へ更新する |
| private registry への push が失敗 | credential store の差異 | OrbStack は `osxkeychain` を使います。`docker login` をやり直す |
| x86_64 のみの image が動かない（Intel Mac） | Intel Mac は arm64 を実行できない | `linux/amd64` 版がある image を選ぶ |

## OrbStack と AI エージェントの親和性

openshell-plus が扱うのはエージェントの sandbox 実行です。OrbStack はこの用途を明示的に想定した設計になっているため、他の Docker ランタイムより噛み合います。

### OrbStack 自身が AI エージェントを隔離用途の筆頭に挙げている

OrbStack の isolated machine は、macOS のファイルシステムから切り離した Linux 環境です。OrbStack のドキュメントは用途の第 1 項目に**「自分でシェルコマンドを実行する AI エージェント」**を挙げ、続けて「信頼できない依存関係やビルドスクリプト」「未知のプロジェクトのコードレビュー」「home ディレクトリに触れてほしくない実験」を示しています。依存パッケージ 1 個の `postinstall` スクリプトがファイル・SSH 鍵・環境変数を読み出せる、という供給網リスクが根拠です。

```bash
orb create --isolated ubuntu agent-sandbox
```

通常の machine と isolated machine の違いは次の 4 点です。

| 通常の machine | isolated machine |
|---|---|
| `/mnt/mac` で Mac のファイルが見える | マウントされない |
| `mac` コマンドで macOS 上の操作を呼べる | 呼べない |
| SSH agent を既定で forward する | 既定で無効 |
| USB / serial / 音が渡る | 渡らない |

一方、インターネット、`.orb.local` ドメイン、Mac からの SSH と `orb` アクセスは使えます。必要なものだけを明示的に足します。

```bash
# 作業フォルダだけを共有する
orb create --isolated --mount ~/project:/work ubuntu agent-sandbox

# 他の machine と host IP への通信も遮断し、インターネットだけ残す
orb create --isolated --isolate-network ubuntu agent-sandbox

# git push が必要な場合だけ SSH agent を許可する
orb create --isolated --forward-ssh-agent ubuntu agent-sandbox
```

既存 machine の設定は後から変えられます。

```bash
orb config set machine.agent-sandbox.isolated true
orb config set machine.agent-sandbox.isolate_network true
```

**ただし isolated machine は完全なセキュリティ境界ではありません。** すべての machine と container は単一の Linux VM 上で 1 つの kernel を共有します。OrbStack 自身が「kernel を狙って脱出を試みるコードには使わず、独立した kernel を持つ full VM を使うこと」と明記しています。信頼できない依存関係やエージェントの通常運用には十分ですが、悪意あるコードの解析には向きません。

### OpenShell の MicroVM driver と組み合わせると 2 段構えになる

OpenShell には sandbox を軽量 VM 単位で分離する `vm` driver があり、macOS では Hypervisor.framework を使います。OrbStack の isolated machine の中で gateway を動かせば、エージェントが host へ出る経路を 2 段で塞いだ構成になります。

```toml
[openshell.gateway]
compute_driver = "vm"

[openshell.drivers.vm]
default_image = "nvcr.io/nvidia/base/ubuntu:24.04"
```

`vm` は自動検出されないため明示指定が必要です（環境変数 `OPENSHELL_COMPUTE_DRIVER=vm` でも可）。注意点は 2 つあります。

- **VM sandbox にはネットワークインターフェースがありません。** すべての通信は host 上の supervisor を経由します。proxy を使う場合は `http://host.openshell.internal:<port>` を指定します
- **`--cpu` / `--memory` は効きません。** `vcpus` と `mem_mib` を設定します

### 実行速度と電池消費

OrbStack は WSL 2 と同じく、軽量 Linux VM の kernel 共有方式を採用しています。主要なサービスは Swift / Go / Rust / C で自作し、Docker engine と Linux machine を同じ VM 内で動かせます。ファイル転送は VirtioFS に加えて macOS 側の `~/OrbStack` を双方向で低遅延共有する構成です。Apple Silicon では Rosetta で x86_64 のエミュレーションを高速化し、kernel の KASLR を強化しつつ KPTI に伴うシステムコールのオーバーヘッドを避けています。

性能と電池消費のベンチマークは OrbStack 自身が公開しています。Open edX の provision、PostHog の image build、Kubernetes + Helm、Supabase、Sentry の 38 service 構成といった実開発ワークロードが対象で、測定は 2023 年 8 月、OrbStack v0.17.0 と Docker Desktop v4.22.0 の比較、M1 Max MacBook Pro で行われました。数値はワークロードに強く依存するため、[公式のベンチマーク](https://docs.orbstack.dev/benchmarks)を確認してください。

エージェントは短時間で起動と停止を繰り返すため、起動コストの小ささが実運用で効きます。machine の作成と破棄は 1 分未満で済み、コンテナを動かしていない間の CPU 使用量は M1 で約 0.1% と報告されています。

### エージェントを動かすときの運用ルール

- **engine をネットワークへ公開しないでください。** OrbStack の `hosts` 設定に `tcp://0.0.0.0:2375` を足すと、LAN や VPN 上の端末から Mac の全データを完全に制御できてしまいます。OrbStack 自身が「極めて危険」と明記しています。必要な場合は SSH か、TLS と client 認証を併用してください
- **エージェントには `read_only` を既定にしてください。** 書き込みを許可する範囲は必要なものだけ広げます
- **`bind mount` は gateway host のファイルを sandbox へ露出します。** workspace の分離とファイル policy を迂回できる経路になるため、`enable_bind_mounts` は必要な場合のみ有効にします
- **機密情報は環境変数ではなく provider 経由で渡します。** `openshell provider` を使ってください

### 使い分けのまとめ

| 目的 | 推奨 | 理由 |
|---|---|---|
| まず動かして試す | OrbStack + Docker driver | 手順が最も短く、`docker` コマンドをそのまま使える |
| 依存スクリプトを走らせたい | OrbStack + isolated machine | OrbStack が想定するエージェント用途の中心 |
| 脱出を試みるコードを解析したい | full VM（UTM など） | kernel を共有する方式では防げない |
| 本番相当の隔離 | MicroVM driver | sandbox ごとに独立した VM 境界 |

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
3. [USAGE.md](USAGE.md) — 目的別の活用レシピ・制約・トラブルシューティング
4. `openshell-uiux-guide.html` — 元の UI/UX ガイド（擬似 API。実 SDK との差分は「ドキュメント訂正ツール」節に整理してあります）
5. [DEV-MEMO.md](DEV-MEMO.md) — フェーズごとの設計判断と検証記録

## コントリビューション

コントリビューションは歓迎します。大きな変更を行う前に [Issue](https://github.com/watanabe3tipapa/openshell-plus/issues) を立てて相談してください。一般的な手順:

1. リポジトリをフォーク
2. 機能ブランチを作成 (`git checkout -b feature/amazing-feature`)
3. 変更をコミット (`git commit -m 'Add amazing feature'`)
4. 品質ゲートをすべて通す
5. ブランチをプッシュし、Pull Request を作成

```bash
uv sync --all-extras
uv run pytest        # 149 テスト
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
