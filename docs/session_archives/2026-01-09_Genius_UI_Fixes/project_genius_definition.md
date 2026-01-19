# Project Definition: MEKIKI Genius Edition (Final Consensus Draft)

**Version:** 1.0
**Date:** 2026-01-09

## 1. Vision & Core Philosophy
**"Beyond OCR" (OCRを超える視覚的知能)**

これまでの「テキスト一致」に依存した校正システムから脱却し、ユーザーご提示の **「融合アーキテクチャ（Fusion Architecture）」** 図にある通り、
**「テキスト抽出」と「構造抽出」を統合し、最終的な「融合スコア」を算出する** 真のマルチモーダル校正システム（Genius Edition）を構築します。
ユーザーが「ここをこうしたい」と一度教えれば、システムが「あ、なら他もこうですね」と意図を汲み取って全ページを自動調整する——それが我々の目指すゴールです。

---

## 2. Definitive Features (作り上げるもの)

これまでの対話に基づき、以下の3つの柱を「Genius Edition」の必須機能として定義します。

### A. Visual Anchor Engine (VAE) - 「見た目」の理解
テキストだけでなく、**画像（アイコン、写真、ロゴ）やレイアウト** を基準点（アンカー）として認識します。
- **機能:**
  - **画像マッチング:** OpenCVを用いて、OCRでは文字化けするアイコンや写真をピクセルレベルで認識し、ズレのない位置合わせを実現します。
  - **スタイル認識:** 「赤い太文字」や「枠線」などを特徴量として扱い、似た見た目のブロックを同一グループとして扱います。
- **ユーザーベネフィット:** 文字がない（または誤認識された）グラフィカルな領域でも、完璧な自動同期が可能になります。

### B. Structure Propagator - 「構造」の展開
「1箇所直せば、全て直る」。ユーザーの修正操作を学習し、ドキュメント全体にその変更ルールを波及させます。
- **機能:**
  - **類似検出（Template Propagation）:** ユーザーが手動で定義した「正解領域」をテンプレートとして、ページ内の類似構造（リスト項目、商品カードなど）を一括検出・正規化します。
  - **One-Click Consistency:** 編集画面内の「✨ 類似検出」ボタン一つで、何百ページあるドキュメントでも瞬時にレイアウト修正を適用します。
- **実装状況:** プロトタイプ完了（Web/PDF対応）、Visual Anchor連携へ移行中。
- **アーキテクチャ対応:** 図中の「構造抽出」→「調整テンプレート」フェーズに該当。

### C. Unified Comparison Matrix - 「思考」の可視化
WebとPDFの比較状況を、ただ並べるだけでなく「意味のある対」として管理・表示します。
- **機能:**
  - **Fusion Score:** テキスト類似度と構造類似度を統合した最終スコア（融合スコア）を算出します。
- **機能:**
  - **Real-time Sync:** 編集画面（Editor）での変更が、即座に比較表（Spreadsheet）と全体ビュー（Canvas）に反映されます。
  - **Single Source of Truth:** 内部データ構造を統一し、「画面ごとに結果が違う」という矛盾を根絶します。

### D. Visual Match Simulator (New) - 「推論」のシミュレーション
ユーザーが提案された「オニオンスキン」と「LLM構文推論」を具現化するデバッグ/検証環境です。
- **機能:**
  - **Onion Skin Overlay:** WebとPDFの領域を半透明で重ね合わせ、ズレを視覚的に確認・調整可能にします。
  - **LLM Syntax Inference:** 単純な文字列一致ではなく、LLMに「文脈的に同じ意味か？」を問うことで、OCR誤読やレイアウト違いを吸収したロバストな判定を行います。
  - **Dynamic Scaling:** 縮尺を変えながら最適なマッチングポイントを探索します。
  - **Unified Editor Integration:** (User Request) シミュレーターと詳細エディタを統合し、検証しながらその場で修正可能な「Unified Inspection Editor」へと進化させます。

---

  - **Single Panel Reversion:** (User Feedback) 2画面分割（Dual Panel）をやめ、1画面に戻しつつ、必要に応じて「Region Editor」内でWeb/PDFを同時確認できるUIに刷新します。
  - **Integrated Region Editor:** 「領域エディタ」にシミュレーター機能（テキスト比較、オニオンスキン、LLM推論）を完全統合します。

## 3. Implementation roadmap (実現への道筋)

### Phase 1: Foundation (完了)
*   [x] モノリシックな `AdvancedComparisonView` の整理とモジュール化準備
*   [x] GUIコンポーネントの分離（Spreadsheet, Editor）
*   [x] 基本的な構造伝播（Propagator）の実装（テキスト/座標ベース）

### Phase 2: Visual Intelligence (現在地)
*   [ ] **OpenCV Integration:** `cv2` を導入し、テキスト特徴量が弱い箇所を画像マッチングで補完する。
*   [ ] **Visual Propagator:** 「このアイコンがある場所」を起点に領域を特定するロジックの実装。
*   [ ] **Style Matching:** テンプレートの「アスペクト比」「密度」などを学習し、高精度な類似検索を実現。

### Phase 3: Autonomous Refinement
*   [ ] **AI Logic:** LLMを活用し、「数値の食い違い」や「文脈的な矛盾」を指摘する意味的校正機能。

---

## 4. Agreement (合意形成)

**「テキストだけでなく、画像認識（OpenCV）と構造理解を組み合わせ、人間の直感に近い補正を行うシステム」**

これが我々の作り上げる "MEKIKI Genius" の正体です。
この定義で合意いただけますでしょうか？
合意いただければ、直ちに **Phase 2: Visual Intelligence** の実装（OpenCVを用いた画像アンカー実装）へ進みます。
