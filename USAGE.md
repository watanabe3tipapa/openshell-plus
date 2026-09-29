# USAGE

「何のためにこのツールを使うか」を目的別にまとめた運用ドキュメントです。構想・機能一覧・全環境変数は [`README.md`](README.md)、設計判断の背景は [`DEV-MEMO.md`](DEV-MEMO.md) を参照してください。

- **[公開サイト（LP）](https://watanabe3tipapa.github.io/openshell-plus/)** — 画面デモ・構成図
- **[構成図](site/diagrams/openshell-plus-architecture.html)** — ブラウザ → FastAPI → gateway → 隔離境界の全体像

## 目次

1. [まず 5 分で触る](#1-まず-5-分で触る)
2. [実行モードの選び方](#2-実行モードの選び方)
3. [実 gateway に接続する](#3-実-gateway-に接続する)
4. [認証と公開の安全性](#4-認証と公開の安全性)
5. [ブラウザ UI の制約（先に読む）](#5-ブラウザ-ui-の制約先に読む)
6. [目的別の活用レシピ](#6-目的別の活用レシピ)
7. [demo backend の正体](#7-demo-backend-の正体)
8. [トラブルシューティング](#8-トラブルシューティング)
9. [やってはいけないこと](#9-やってはいけないこと)
10. [検証コマンド](#10-検証コマンド)
11. [関連ドキュメント](#11-関連ドキュメント)
12. [今後の用例・アイデア](#12-今後の用例アイデア)

---

## 1. まず 5 分で触る

OpenShell を導入していなくても動きます。gateway に到達できない場合は demo backend に自動で落ちます。

```bash
uv sync --all-extras
uv run python -m openshell_ui
```

ブラウザで <http://127.0.0.1:8080> を開き、次を試します。

1. 「新規作成」で `demo-box` を作る
2. 一覧から選択し、コンソールに `ls` を入力して「実行」
3. 出力に `pyproject.toml` が並ぶ（demo backend の擬似応答）
4. 「削除」で片付ける

実際にどの backend が動いているかは `/api/health` で確認できます。

```bash
curl -s http://127.0.0.1:8080/api/health | python3 -m json.tool
```

`backend` が `demo` なら gateway 未接続、`openshell` なら接続済みです。

## 2. 実行モードの選び方

`OSUI_MODE` を空にすると自動判定されます（`VERCEL` → `OPENSHELL_SANDBOX_ID` → Colab → `local` の順）。**勘で選ぶより、下表の「誰に見せるか」で決めてください。**

| やりたいこと | モード | 起動方法 | backend | 主な制約 |
|---|---|---|---|---|
| 手元の gateway を自分で操作 | `local` | `./scripts/run-local.sh` | 実 gateway | 自分しか見ない |
| 自分のドメインで HTTPS 公開 | `cloudflare` | `./scripts/run-cloudflare.sh` | 実 gateway | tunnel とドメインの準備が必要 |
| URL を共有してデモを見せる | `vercel` | `./scripts/deploy-vercel.sh` | demo 固定 | Vercel から手元の gateway へは到達できない |
| Colab の GPU 上で動かす | `colab` | ノートブックを順に実行 | demo 固定 | 公開トンネルは開始しない |

**named tunnel と Quick Tunnel は別物です。** Quick Tunnel は `./scripts/run-cloudflare.sh quick` で起動し、URL が実行ごとに変わる・SSE が使えない・同時接続が 200 リクエスト上限、という制約があります。短い確認やデモには向き、長時間の検証には named tunnel を使ってください。

Vercel 形態はトークンを設定してから deploy します（スクリプトが未設定なら中断します）。

```bash
vercel link
vercel env add OSUI_AUTH_TOKEN production
./scripts/deploy-vercel.sh
```

## 3. 実 gateway に接続する

### 3.1 前提の確認

```bash
openshell status
```

パッケージ既定の gateway TLS ポートは **17670** です（`gateway add` の例では 18080 が使われることもあります）。接続先の自動検出に任せるなら `OSUI_GATEWAY_ENDPOINT` は空のままにしてください。

### 3.2 接続先を明示する

```bash
export OSUI_GATEWAY_ENDPOINT=127.0.0.1:17670
export OSUI_REQUIRE_GATEWAY=true
uv run python -m openshell_ui
```

**`OSUI_REQUIRE_GATEWAY=true` は常用してください。** 既定の `false` だと、gateway 側の障害が「demo に落ちた無関係な一覧」として見え、失敗が静かに Cher まります。`true` にすると接続できないまま起動が失敗し、原因がそのまま分かります。

### 3.3 mTLS / OIDC を組み合わせる

```bash
export OSUI_GATEWAY_CA_CERT=/path/ca.pem
export OSUI_GATEWAY_CERT=/path/client.pem
export OSUI_GATEWAY_KEY=/path/client.key

export OSUI_OIDC_ISSUER=https://idp.example.com
export OSUI_OIDC_CLIENT_ID=openshell-ui
export OSUI_OIDC_CLIENT_SECRET=...
export OSUI_OIDC_AUDIENCE=...
```

起動時に検証される約束:

- `OSUI_GATEWAY_CERT` と `OSUI_GATEWAY_KEY` は両方同時に指定する
- `OSUI_OIDC_ISSUER` には `OSUI_OIDC_CLIENT_ID` が必要。`OSUI_OIDC_CLIENT_SECRET` には `OSUI_OIDC_ISSUER` が必要
- **loopback 以外の gateway で OIDC を使う場合、TLS（`OSUI_GATEWAY_CA_CERT`）が必須**
- `OSUI_EXEC_DEFAULT_TIMEOUT` は `OSUI_EXEC_MAX_TIMEOUT` を超過できない

### 3.4 UI を使わずにローカルから繋ぐ

短時間の確認なら、UI より CLI の転送命令のほうが軽いです。

```bash
openshell forward start 8000 my-sandbox
```

## 4. 認証と公開の安全性

`OSUI_AUTH_TOKEN` を設定すると、コンソールと全 API が保護されます。

- **`/api/health` だけは認証対象外**です（ロードバランサや監視の疎通確認を想定して意図的に開いています）
- loopback 以外の bind でトークン未設定だと、起動そのものが拒否されます
- トークンを受け取れる場所は 3 か所です
  - `Authorization: Bearer <token>`（REST と WebSocket の主経路）
  - `Sec-WebSocket-Protocol: bearer.<token>`（ブラウザの WebSocket はヘッダーを自定义できないため）
  - `?token=<token>`（SSE と event source）
- WebSocket の認証に失敗すると close code **4401** で切断されます
- トークンは画面上でセッション内だけ保持されます（タブを閉じると消えます）
- 静的アセットはトークンなしで配信されます（機密情報は含まれません）

トークンを受け取った者は、その認証情報ひとつで管理対象の全 sandbox を操作できます。他の sandbox も見える点を確認してから共有してください。

## 5. ブラウザ UI の制約（先に読む）

コンソールに入力した文字列は、**空白で分割されるだけ**です。shell として解釈されません。

```js
// src/openshell_ui/ui/assets/app.js
const parts = command.split(/\s+/).filter(Boolean);
```

したがって次の制限があります。

| 入力 | 実際の動き |
|---|---|
| `ls -la` | 正常。`["ls", "-la"]` として実行 |
| `ls \| wc -l` | パイプは無視され、`\|` が引数として渡るだけ |
| `echo a > out.txt` | リダイレクトは効きません |
| `python -c "print(1)"` | 引用符がそのまま引数に含まれ、`print(1)` が二重引用符付きで渡る |
| `ls *.py` | グロブ展開されません |

**この制約は API 経由なら回避できます。** exec の `command` は argv の配列なので、shell を明示的に挟めばよいです。

```json
{ "command": ["bash", "-lc", "ls | wc -l"] }
```

引数 1 個にスクリプト一式を入れる形なので空白や記号をそのまま渡せます。ブラウザから做不到処理は、REST API に切り替えてください。

その他の UI の仕様:

- **作業ディレクトリ（`workdir`）の入力欄はありません**（API でのみ指定可能）
- **WebSocket 経路のタイムアウトは 60 秒固定**です。REST 経路は `OSUI_EXEC_DEFAULT_TIMEOUT`（既定 60、上限 `OSUI_EXEC_MAX_TIMEOUT` 既定 1800）が効きます
- 一覧の自動更新は 8 秒ごとで、exec の実行中は一時停止します
- exec の `env` は未実装です。渡すと 422 で拒否されます（黙って無視はしません）

## 6. 目的別の活用レシピ

### 6.1 使い捨ての検証環境

「作って試して捨てる」を繰り返す用途です。名前は一意である必要があります。

```bash
TOKEN=your-token
BASE=http://127.0.0.1:8080

curl -s -X POST "$BASE/api/sandboxes" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"try-01","labels":{"purpose":"smoke"}}'

curl -s -X POST "$BASE/api/sandboxes/try-01/exec" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"command":["bash","-lc","uname -a && python3 -V"]}'

curl -s -X DELETE "$BASE/api/sandboxes/try-01" -H "Authorization: Bearer $TOKEN"
```

同じ名前は作れません（作成は 409）。使い回すなら手順の最初に削除を挟むか、末尾に連番を振ってください。

### 6.2 workspace で分けて並列に扱う

同じ名前を別 workspace に作れます。用途ごとに分けておくと、一覧が混ざりません。

```bash
# 起動時に固定
OSUI_WORKSPACE=team-a

# リクエスト単位“上書き”（クエリ、POST は JSON の workspace）
curl -s "$BASE/api/sandboxes?workspace=team-b" -H "Authorization: Bearer $TOKEN"
```

同じ名前で team-a と team-b に 1 個ずつ作っても衝突しません。`GET /api/sandboxes/{name}?workspace=…` でも切り替えられます。

### 6.3 ポートを公開してサービス URL を受け取る

作成時にポートを指定すると、後から URL を取得できます。

```bash
curl -s -X POST "$BASE/api/sandboxes" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"web","service_port":8000,"service_name":"web"}'

curl -s "$BASE/api/sandboxes/web/service-urls" -H "Authorization: Bearer $TOKEN"
```

返るのは gateway 側で解決された値です。`service_urls` が空の gateway では空のオブジェクトが返ります。CLI 側では同じことを `openshell service expose web 8000` で行い、解除は `openshell service delete` です。

### 6.4 長時間処理を実行する

60 秒を超える処理は、ブラウザのコンソールではなく API から実行します。

```bash
curl -s -X POST "$BASE/api/sandboxes/web/exec" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"command":["bash","-lc","uv sync && pytest -q"],"timeout_seconds":1200}'
```

`timeout_seconds` は `OSUI_EXEC_MAX_TIMEOUT`（既定 1800）で丸められます。標準出力を逐次見たい場合は WebSocket か SSE を使ってください。

```bash
curl -N -s "$BASE/api/sandboxes/web/exec/stream?command=ls&token=$TOKEN"
```

SSE は Quick Tunnel で無効化しているため、その場合は 404 になります（WebSocket を使ってください）。

### 6.5 スクリプトや CI から叩く

`/api/health` は認証不要なので、起動確認と公開前のチェックに使えます。

```bash
curl -fsS http://127.0.0.1:8080/api/health | grep -q '"ok": true'
```

Bash だけで扱う場合の最小構成です。

```bash
#!/usr/bin/env bash
set -euo pipefail
BASE=https://ui.example.com
TOKEN="${OSUI_AUTH_TOKEN:?set OSUI_AUTH_TOKEN}"

curl -fsS -X POST "$BASE/api/sandboxes" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"ci-box"}' >/dev/null

curl -fsS -X POST "$BASE/api/sandboxes/ci-box/exec" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"command":["bash","-lc","pytest -q"],"timeout_seconds":900}'

curl -fsS -X DELETE "$BASE/api/sandboxes/ci-box" \
  -H "Authorization: Bearer $TOKEN" >/dev/null
```

**CI では trap で後始末をしてください。** 失敗しても sandbox を残すと quota とコストが残ります。

### 6.6 policy と provider を整えて実際の agent を動かす

UI から操作できるのは作成と実行だけです。sandbox の中で実際の agent を動かす場合は、`policy` と `provider profile` の準備が別途必要です。次の順で整備します。

1. `deploy/` 配下の `policy/ui-policy.yaml` を参考に、网络規則を記述する
2. `openshell profile import --url <URL>` で provider profile を投入する
3. agent が出そうになる接続は、承認の前に `openshell rule get` で一覧する
4. `openshell rule approve` / `openshell rule reject` で判断する

同梱の policy は次の構造です。緩める判断をする際は、どこを緩めるかが threat model のどこに対応するかを確認してください。

```yaml
version: 1
filesystem_policy:
  include_workdir: true
  read_only: [/usr, /lib, /lib64, /etc]
  read_write: [/tmp]
landlock:
  compatibility: best_effort
process:
  run_as_user: sandbox
network_policies:
  nvidia_inference:
    endpoints:
      - { host: integrate.api.nvidia.com, port: 443, access: read-write }
    binaries:
      - path: /usr/bin/uv
```

`network_policies` の各エントリは宛先（`endpoints`）と、その接続を行えるバイナリ（`binaries`）の組です。**宛先だけを広くしてもバイナリを制限すれば通るが、バイナリだけを広げると宛先も開いてしまう**、という向き合いになるので、両方を-review します。

## 7. demo backend の正体

gateway に接続できないときの代替です。**画面と操作は本物ですが、データは捏造されています。**

- 作成直後は `provisioning`、0.8 秒後に `ready` になります
- 応答するのは次のコマンドだけです: `ls` / `dir` / `pwd` / `whoami` / `hostname` / `uname` / `python` / `python3` / `node` / `uv` / `echo`
- それ以外は `demo: executed '<コマンド>' without a real sandbox` を返すだけです。**終了コードは常に 0** なので、失敗したコマンドを察觉できません
- sandbox の内容・ファイル・ネットワークは実在しません

用途は「UI が壊れていないかの確認」「デモ」「Colab や Vercel での見た目確認」までです。**demo backend で成功したコマンドを、実 gateway で成功した証拠として扱わないでください。** 接続できたかどうかは `/api/health` の `backend` フィールドで必ず確認します。

## 8. トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `refusing to bind ...` で起動しない | loopback 以外の bind でトークン未設定 | `OSUI_AUTH_TOKEN` を設定するか `OSUI_HOST=127.0.0.1` に戻す |
| 一覧が demo の内容に見える | gateway に接続できていない | `openshell status` を確認。`OSUI_REQUIRE_GATEWAY=true` にして原因を露出させる |
| すべて 401 | トークン未設定または不一致 | トークンを再確認。画面上の認証パネルの値と `OSUI_AUTH_TOKEN` を比較 |
| WebSocket がすぐ切断される | close code 4401 | トークンが一致していません |
| SSE が 404 | `OSUI_SSE_ENABLED=false` | Quick Tunnel では意図的に無効です。WebSocket を使ってください |
| `must be set together` | mTLS の CERT / KEY が片方だけ | 両方指定する |
| `requires OSUI_OIDC_ISSUER` | OIDC の設定が片方だけ | ISSUER と CLIENT_ID をセットで指定する |
| `requires TLS` | loopback 以外の gateway で OIDC を TLS 無しで使用 | `OSUI_GATEWAY_CA_CERT` を指定する |
| `the openshell SDK is not installed` | OpenShell 別の依存が未導入 | `uv sync --extra openshell` |
| Colab で `pip install failed` | リポジトリが public かつ push 済みでない | 公開して push してから再実行 |
| Docker に接続できない | Docker や OrbStack の daemon が停止 | コンテナ環境を起動してからやり直す |
| 名前を作れない（409） | 同名・同 workspace で既存 | 削除するか、名前を分ける |
| Quick Tunnel が 200 を超える | 同時接続数の上限 | named tunnel を使う |

ログの詳しさは `OSUI_LOG_LEVEL=debug` で上げられます。gateway 接続の失敗理由はこのログに出ます。

## 9. やってはいけないこと

- **`OSUI_AUTH_TOKEN` を設定せずに `0.0.0.0` へ bind する** — 起動は拒否されますが、`--host` の直接指定などで回避されないよう、意図を確認してください
- **トークンを URL に埋め込んだまま共有する** — `?token=` は各省のアクセスログや履歴に残ります。SSE 以外の用途では `Authorization` を使ってください
- **Vercel から手元の gateway に届く Simulac と期待する** — 到達できません。Vercel は demo の確認用です
- **Colab で公開トンネルを張る** — Colab の利用規約に抵触します。ノートブック内の該当セルはコメントアウトされています
- **demo backend の成功を実 gateway の成功として扱う** — 擬似応答です
**exec に `env` を渡して設定を期待する** — 未実装で 422 になります。環境変数はイメージや entrypoint で仕込んでください。
- **UI のコンソールでパイプやリダイレクトを使う** — 効きません。REST API の `command` 配列で `bash -lc` を挟んでください
- **policy を理由なく緩める** — 緩めた量为そのまま攻撃面です。`read_only` に追加するより `read_write` を増やす方が影響範囲が広いです

## 10. 検証コマンド

変更を加えたときは次を通してください。

```bash
uv sync --all-extras
uv run pytest                 # 149 tests
uv run ruff check .
uv run ruff format --check .
uv run pyright                # 0 errors
```

| ゲート | 現在の結果 |
|---|---|
| `uv run pytest` | 149 passed |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 30 files already formatted |
| `uv run pyright` | 0 errors |

テストは demo backend を使い、gateway には接続しません。`OSUI_DEMO=true` 相当の設定は `tests/helpers.py` の `make_settings()` が保証しています。

## 11. 関連ドキュメント

| 内容 | 場所 |
|---|---|
| 公開サイト・画面デモ・構成図 | <https://watanabe3tipapa.github.io/openshell-plus/> |
| 構想、機能一覧、全環境変数 | [`README.md`](README.md) |
| 英語版 | [`README_en.md`](README_en.md) |
| 設計判断と検証の記録 | [`DEV-MEMO.md`](DEV-MEMO.md) |
| 出発点の UI/UX ガイド（拟似 API） | `openshell-uiux-guide.html` |
| OpenShell 公式ドキュメント | <https://docs.nvidia.com/openshell/latest/> |
| OpenShell 本体 | <https://github.com/NVIDIA/OpenShell> |

## 12. 今後の用例・アイデア

**この節はユースケースとアイデアの置き場です。** 実際に有効だった組み合わせが見つかるたびに、ここへ追記していきます。未確定の内容も仮説として残し、検討できる形にまとめてください。

### 12.1 追記の目安

追記が expedient なケースです。

- 特定の目的（GPU 検証、脆弱性再現、複数テナント運用、CI での回帰など）で実際に使った手順
- UI の制約を回避する実用的なパターン（`bash -lc` への置き換え、値の渡し方など）
- gateway 側の仕様変更や SDK の更新で消えた、または変わった手順
- 失敗モードと、その切り分け方

### 12.2 1 件の書き方

次の見出しで 1 件ずつ追記します。

```markdown
### <用例名>（<日付>）

**目的** — 何をしたくてこの構成にしたか

**前提** — gateway、認証、policy など要先に用意する条件

**手順**

1. ...

**碰到了こと / 制約** — 実際に詰まった点。制約であれば UI 側の制限か API 側の回避策か

**検証** — どう確かめたか（コマンド・確認先）
```

### 12.3 記録済みの用例

まだ条目はありません。以下は候補として Truth です。

- [ ] GPU fermware の検証を Colab + API exec で行う
- [ ] Quick Tunnel と named tunnel の使い分けの基準
- [ ] 複数 workspace を組み合わせた運用例
- [ ] policy の変更を安全に行う手順（差分 → 検証 → 承認）

### 12.4 提案の送り方

用例の追加や修正は通常の Pull Request でどうぞ。上記 12.2 の形に、実測した値と推測を混ぜずに書いてください。確定していない内容は 12.3 のチェックリストに置いてください。
