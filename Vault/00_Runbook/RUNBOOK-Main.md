# Runbook: Obsidian横断RAG × Antigravity開発 × マルチエージェント運用
最終更新: 2026-01-12

## 0. 目的
- **Obsidian Vaultを「プロジェクト共通の知識基盤」**として運用し、横断的にRAGで参照できる状態を作る
- **Antigravity（VS Code系IDE）を実行環境**として、開発・コンテンツ制作を複数AIエージェントで高速に回す
- 広告案件向け「校正・検版／クリエイティブ評価ツール」の品質を、**再現性のある開発フロー**で継続改善する
- 現在のボトルネック：**長文比較のためのパラグラフ自動検出**を安定させる

---

## 1. システム全体像（レイヤ設計）
### 1.1 レイヤ
1) **Knowledge Layer（Obsidian Vault）**  
   - 仕様・議事録・ADR・実験ログ・評価データ・プロンプトを一元管理（Markdown + YAML frontmatter）
2) **Index Layer（RAG Indexer / MCP Server）**  
   - Vaultをchunk→embed→vector storeへ。IDE/エージェントが検索APIで参照
   - MCP（Model Context Protocol）で「Obsidian検索」をツール化し、どのエージェントからでも同じ窓口で呼べる
3) **Execution Layer（Antigravity + Repo）**  
   - 実装・テスト・ビルド・デプロイ・データ処理はコードリポジトリ側で実行
4) **Agent Layer（役割分担）**  
   - 企画/要件/設計、実装、レビュー、評価、ドキュメント更新を分業して自動化

---

## 2. Vault（Obsidian）運用規約
### 2.1 推奨フォルダ構成
```
/00_Runbook/              # 本Runbookや運用ルール
/10_Projects/
  /<project_key>/         # プロジェクト単位の仕様・議事録・チケット
/20_Design/               # 共通設計（データモデル、アルゴリズム、UI/UX）
/30_Prompts/              # エージェント指示書、テンプレ、禁止事項
/40_Evals/                # 評価データ、指標、回帰テスト結果
/50_Logs/                 # 実験ログ、障害記録、決定理由（ADR）
/99_Archive/
```

### 2.2 すべてのノートに付けるYAML（最低限）
```yaml
---
type: spec | adr | log | prompt | eval | ticket
project: <project_key>
status: draft | active | done
created: 2026-01-12
updated: 2026-01-12
tags: [rag, ocr, proofreading]
---
```

### 2.3 命名ルール（差分・検索に強い）
- 仕様：`SPEC-<topic>-YYYYMMDD.md`
- ADR：`ADR-YYYYMMDD-<decision>.md`
- 実験ログ：`EXP-YYYYMMDD-<hypothesis>.md`
- チケット：`TKT-<ulid>-<short>.md`

---

## 3. RAG化（Index Layer）の実装方針
### 3.1 2つの実装案（どちらか、または併用）
A) **Obsidian向けRAGプラグイン/バックエンド系**  
- Vaultを自動でchunk/embedして問い合わせできる構成（例：ObsidianRAG系）

B) **MCP Serverで「Vault検索」をツール化**  
- 例：ObsidianノートRAGのMCPサーバ（OpenAI embeddings or Ollamaローカル、ChromaDB等）

> 機密性が高い場合は **ローカル埋め込み（Ollama等）** を優先。クラウド埋め込みは情報区分と承認フローを決めてから。

### 3.2 Chunking戦略（重要：段落検出とも連動）
- 既定：**見出し単位（H1/H2）＋段落単位**  
- ルール：
  - 1チャンク = 300〜800トークン目安
  - 連続段落は「論点が同一なら結合」、違うなら分割
  - コードやログは別チャンク（`type: log`や`type: prompt`でフィルタ可能に）

### 3.3 インデックス更新ポリシー
- `git commit` または `file watcher` で差分更新（フル再計算を避ける）
- `updated` が更新されたノートのみ再embedding
- embeddingの再現性確保のため、**モデル名・次元・正規化・チャンクID**を保存

---

## 4. マルチエージェント運用設計（Agent Layer）
### 4.1 役割（推奨）
- **Planner（要件/設計）**：仕様化、タスク分割、受入条件作成
- **Implementer（実装）**：Claude Code推奨（大規模コードの実装・テスト生成・リファクタ）
- **Reviewer（レビュー/QA）**：差分レビュー、セキュリティ観点、回帰テスト
- **Evaluator（指標/実験）**：段落検出のF1、校正検出精度、false positive率
- **Documenter（ドキュメント）**：仕様・ADR・Runbook更新、再現手順の整備

### 4.2 エージェント共通の「運用憲法」テンプレ（/30_Prompts/に保存）
- 参照する知識源の優先順位：  
  1) /00_Runbook 2) /10_Projects/<project> 3) /20_Design 4) /40_Evals 5) /50_Logs
- 変更の出力先：  
  - コード：Gitブランチ（例：`feat/<ticket>`）  
  - ドキュメント：該当ノート＋必要ならADR追加  
  - 実験結果：/40_Evals と /50_Logs に必ず残す
- 禁止事項：  
  - 機密情報をプロンプトやログに貼らない  
  - “動いてそう”でマージしない（受入条件・回帰テスト必須）

---

## 5. 開発フロー（Antigravity × Claude Code中心）
### 5.1 推奨：Antigravityを「統合コンソール」として使う
- AntigravityはVS Code系IDEとして運用（拡張/ターミナル/差分レビューを活用）
- Claude Codeは **CLIでもVS Code拡張でも運用可能**。互換性が怪しい場合はまずCLIで回す。

### 5.2 1チケットの標準フロー（Definition of Done込み）
1) **TKT作成**（Obsidian）
   - 問題、背景、制約、受入条件、テスト観点、サンプル入力を記載
2) **Plan**（Planner）
   - アルゴリズム案、実装手順、リスク、計測方法をSPEC/ADRに落とす
3) **Implement**（Implementer / Claude Code）
   - 実装 + 単体テスト + ログ（再現手順）
4) **Review**（Reviewer）
   - 差分レビュー、性能・セキュリティ、回帰テスト
5) **Eval**（Evaluator）
   - 指標を更新（F1、誤検出率、処理時間、メモリ）
6) **Document**（Documenter）
   - Runbookに「学び」「次の改善」「落とし穴」を追記

---

## 6. 段落（パラグラフ）自動検出：実装の設計指針
> 目的：**長文の比較校正**で、段落単位の対応付け（alignment）と差分抽出を安定化する。

### 6.1 まず結論：段落は「改行」ではなく「レイアウト＋文脈」で決める
媒体ごとにソースが違うため、段落検出は次の共通表現へ落とし込むのが安定します。

#### 共通ドキュメントモデル（推奨）
- `Document`
  - `Page[]`
    - `Region[]`（カラム/枠/画像/表/本文など）
      - `Line[]`
        - `Token/Word[]`
- 各要素に `bbox(x0,y0,x1,y1)` と `style(font_size, weight, color, indent)` を持たせる
- 段落は `Line` の集合として表現し、`paragraph_id` を付与

### 6.2 媒体別の取り込み戦略
#### Web（HTML）
- **DOM構造を一次情報**として使う（`p`, `li`, `blockquote`, `h1-6` 等）
- 可能ならヘッドレスブラウザで **要素bbox** を取得し、見た目順（reading order）を確定

#### PDF
- 可能なら **PDFのテキスト抽出（座標付き）を優先**（OCRはフォールバック）
- 抽出結果から
  - 行クラスタリング（y近接）
  - カラム推定（x分布クラスタ）
  - 行→段落のマージ（縦間隔・インデント・句読点・箇条書き）
  を行う

#### OCR（画像化されたPDF/スクショ）
- OCRが返す **word bbox** から line→block→paragraph を復元
- reading orderは「左上→右下」ではなく、**カラム分割→各カラム内top-down**を基本にする

### 6.3 段落生成の具体ルール（強い順）
段落境界のスコアリング（例：0〜1）を作り、閾値でsplit/mergeします。

**段落を分けるシグナル**
- 縦ギャップが大きい（`gap > k * median_line_height`）
- 先頭インデントが変わる
- 箇条書き/番号付き（`^(\d+[\.\)]|[・\-•])`）
- 見出しスタイル（font_size↑, bold, all caps など）
- 罫線・枠・背景の切り替わり（Region境界）

**段落を結合するシグナル**
- 行末が禁則/ハイフネーションで次行へ継続している
- 行間が一定で、インデントも一定
- 同一Regionでstyleが連続

### 6.4 “比較校正”のための段落ID設計（ここが差分精度を決める）
- `paragraph_id` を **位置＋内容の指紋**で作る
  - `page_index`
  - `region_id`
  - `bbox_quantized`
  - `simhash(normalized_text)`
- バージョン間の対応付け（alignment）は
  1) 同ページ/同regionの近傍候補を列挙
  2) テキスト類似（埋め込みcosine + ngram Jaccard）
  3) bbox近傍（位置が近いほど加点）
  で最良マッチを取る

### 6.5 UI（手動補正）前提の設計にする
- 自動段落は100%になりません。**最小コストで直せるUI**が勝ちます。
- 操作：Split / Merge / Move / Ignore（段落単位）
- 操作結果は `paragraph_overrides.json` として保存し、次回以降の自動処理に反映（学習データ化も可能）

---

## 7. 評価（Evals）と回帰テスト
### 7.1 段落検出の評価指標（最小セット）
- **Paragraph Boundary F1**（境界が一致した割合）
- **Over-split率 / Over-merge率**
- **Reading order一致率**（段落列がどれだけ正しい順序か）
- 実運用指標：**手動修正回数/ページ**、修正に要した時間

### 7.2 回帰テストセット
- PDF：チラシ、カタログ、規約、台割り、2カラム、表、縦組み混在
- Web：LP、記事、EC、SPA、レスポンシブ崩れ
- “最悪ケース”を必ず含める（画像PDF、低解像度、斜傾き、影、背景模様）

---

## 8. Claude Codeを導入する判断基準（あなたの状況だと「使う価値あり」）
### 向いている用途
- 段落検出アルゴリズムの実装・テスト自動生成・デバッグ
- コードベース横断のリファクタ（データモデル統合、I/O層分離）
- “回帰テスト駆動”で品質を積み上げる運用

### 使い分け（推奨）
- Antigravity内蔵のエージェント：設計の叩き台、探索、UIモック、素早い分解
- Claude Code：実装・テスト・コマンド実行・差分レビュー中心

---

## 9. すぐ着手する「最小の次アクション」（48時間プラン）
1) Vaultに `/00_Runbook/` と `/40_Evals/` を作り、Runbookをコミット
2) 代表サンプル（PDF/Web/OCR）を各10件集め、手動で“正解段落”を作る（JSONでもOK）
3) PDFは「座標付きテキスト抽出→行→段落」までを先に安定させる（OCRは後）
4) 段落検出のBoundary F1を計測する小さな評価スクリプトを用意（回帰の起点）
5) Claude Codeで「テスト→実装→評価ログ出力」のループを確立

---

## 付録A：チケットテンプレ（コピーして /10_Projects/<project>/ に保存）
```markdown
---
type: ticket
project: <project_key>
status: active
created: 2026-01-12
updated: 2026-01-12
tags: [paragraph, diff, ocr]
---

# TKT-<ulid>-<short>

## Problem
（何が壊れているか／何が足りないか）

## Context
（媒体：PDF/Web/OCR、現状パイプライン、再現手順、ログ）

## Constraints
- 処理時間: <target>
- 精度: <target>
- 互換: <env>

## Acceptance Criteria
- [ ] Boundary F1 >= 0.xx（サンプルセットで）
- [ ] 手動修正回数/ページ <= x
- [ ] 回帰テストに追加済み

## Test Data
- sample ids / paths / urls

## Notes
- 参考仕様（SPEC/ADRリンク）
```

---

## 付録B：ADRテンプレ
```markdown
---
type: adr
project: <project_key>
status: active
created: 2026-01-12
updated: 2026-01-12
---

# ADR-20260112-<decision>

## Decision
（何を採用するか）

## Context
（なぜ今それが必要か）

## Options
- A:
- B:
- C:

## Consequences
- Pros:
- Cons:
- Mitigations:
```
