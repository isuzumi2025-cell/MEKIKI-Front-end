"""
Ultimate Sync - ParagraphMatcher
パラグラフ単位でWeb/PDF間のテキスト類似度を計算し、マッチングを行う

Ultrathink: The edge of real value :)
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher


@dataclass
class ParagraphEntry:
    """パラグラフ情報を保持"""
    id: str                    # "W-001" or "P-001"
    source: str                # "web" or "pdf"
    text: str                  # 抽出テキスト
    rect: List[int]            # [x1, y1, x2, y2]
    page: int = 1              # ページ番号
    sync_id: Optional[str] = None      # マッチしたパラグラフのID
    similarity: float = 0.0    # 類似度 (0.0-1.0)
    sync_color: str = "red"    # 色コード
    
    @property
    def preview(self) -> str:
        """テキストプレビュー (50文字)"""
        text = self.text.replace('\n', ' ')
        return text[:50] + "..." if len(text) > 50 else text
    
    @property
    def similarity_percent(self) -> str:
        """類似度をパーセント表示"""
        return f"{self.similarity * 100:.1f}%"


@dataclass
class SyncPair:
    """マッチしたパラグラフペア"""
    web_id: str
    pdf_id: str
    similarity: float
    color: str
    
    @classmethod
    def get_color(cls, similarity: float) -> str:
        """類似度に応じた色を返す"""
        if similarity >= 0.5:
            return "#4CAF50"  # 緑 (50%+)
        elif similarity >= 0.3:
            return "#FF9800"  # オレンジ (30-50%)
        else:
            return "#F44336"  # 赤 (<30%)


class ParagraphMatcher:
    """
    パラグラフマッチングエンジン
    
    Web/PDFの全パラグラフを比較し、最適なマッチングを見つける
    """
    
    SYNC_COLORS = [
        "#4CAF50",  # 緑
        "#2196F3",  # 青
        "#FF9800",  # オレンジ
        "#9C27B0",  # 紫
        "#00BCD4",  # シアン
        "#E91E63",  # ピンク
        "#CDDC39",  # ライム
        "#FF5722",  # 深オレンジ
        "#607D8B",  # ブルーグレー
        "#795548",  # 茶
    ]
    
    def __init__(self, threshold_high: float = 0.5, threshold_low: float = 0.3):
        self.threshold_high = threshold_high
        self.threshold_low = threshold_low
        
        # マルチシグナル融合用の分析器
        self._syntax_analyzer = None
        self._spatial_analyzer = None
        
        # 融合シグナル重み (承認済み)
        self.WEIGHT_TEXT = 0.40      # テキスト類似度
        self.WEIGHT_SPATIAL = 0.30   # 空間クラスター
        self.WEIGHT_IMAGE = 0.20     # 画像テンプレート
        self.WEIGHT_SYNTAX = 0.10    # 構文パターン
    
    @property
    def syntax_analyzer(self):
        """遅延初期化で構文分析器を取得"""
        if self._syntax_analyzer is None:
            from app.core.syntax_pattern_analyzer import SyntaxPatternAnalyzer
            self._syntax_analyzer = SyntaxPatternAnalyzer()
        return self._syntax_analyzer
    
    def calculate_fusion_score(
        self,
        text1: str, text2: str,
        rect1: List[int] = None, rect2: List[int] = None,
        image_similarity: float = None
    ) -> float:
        """
        マルチシグナル融合スコアを計算
        
        Args:
            text1, text2: 比較するテキスト
            rect1, rect2: 矩形座標 (空間クラスター用)
            image_similarity: 画像類似度 (事前計算済み、なければスキップ)
        
        Returns:
            融合スコア (0.0-1.0)
        """
        scores = {}
        weights_sum = 0.0
        
        # 1. テキスト類似度 (40%)
        text_score = self.calculate_similarity(text1, text2)
        scores['text'] = text_score
        weights_sum += self.WEIGHT_TEXT
        
        # 2. 空間クラスター類似度 (30%)
        if rect1 and rect2:
            spatial_score = self._calculate_spatial_similarity(rect1, rect2)
            scores['spatial'] = spatial_score
            weights_sum += self.WEIGHT_SPATIAL
        
        # 3. 画像テンプレート類似度 (20%)
        if image_similarity is not None:
            scores['image'] = image_similarity
            weights_sum += self.WEIGHT_IMAGE
        
        # 4. 構文パターン類似度 (10%)
        if text1 and text2:
            try:
                p1 = self.syntax_analyzer.extract_pattern(text1)
                p2 = self.syntax_analyzer.extract_pattern(text2)
                syntax_score = self.syntax_analyzer.compare_patterns(p1, p2)
                scores['syntax'] = syntax_score
                weights_sum += self.WEIGHT_SYNTAX
            except Exception:
                pass
        
        # 重み付き平均
        if weights_sum == 0:
            return 0.0
        
        fusion = (
            scores.get('text', 0) * self.WEIGHT_TEXT +
            scores.get('spatial', 0) * self.WEIGHT_SPATIAL +
            scores.get('image', 0) * self.WEIGHT_IMAGE +
            scores.get('syntax', 0) * self.WEIGHT_SYNTAX
        ) / weights_sum * (self.WEIGHT_TEXT + self.WEIGHT_SPATIAL + self.WEIGHT_IMAGE + self.WEIGHT_SYNTAX)
        
        return min(1.0, fusion)
    
    def _calculate_spatial_similarity(self, rect1: List[int], rect2: List[int]) -> float:
        """
        空間的類似度を計算 (位置・サイズ比較)
        """
        if not rect1 or not rect2 or len(rect1) < 4 or len(rect2) < 4:
            return 0.0
        
        x1_1, y1_1, x2_1, y2_1 = rect1
        x1_2, y1_2, x2_2, y2_2 = rect2
        
        # サイズ
        w1, h1 = x2_1 - x1_1, y2_1 - y1_1
        w2, h2 = x2_2 - x1_2, y2_2 - y1_2
        
        if w1 <= 0 or h1 <= 0 or w2 <= 0 or h2 <= 0:
            return 0.0
        
        # サイズ比類似度
        width_ratio = min(w1, w2) / max(w1, w2)
        height_ratio = min(h1, h2) / max(h1, h2)
        size_score = (width_ratio + height_ratio) / 2
        
        # アスペクト比類似度
        aspect1 = w1 / h1
        aspect2 = w2 / h2
        aspect_score = min(aspect1, aspect2) / max(aspect1, aspect2)
        
        # 相対位置の類似度 (正規化する必要があるがここでは近似)
        # 今回はサイズとアスペクト比のみ
        return (size_score * 0.6 + aspect_score * 0.4)
    
    def normalize_text(self, text: str) -> str:
        """
        日本語テキストを正規化 (高精度版)
        - 全角/半角統一
        - 空白・改行の正規化
        - カタカナ→ひらがな変換
        - 句読点・記号の統一
        """
        if not text:
            return ""
        
        # Unicode正規化 (NFKC: 全角→半角、異体字統一)
        text = unicodedata.normalize('NFKC', text)
        
        # 空白と改行の正規化
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 句読点の統一
        text = text.replace('。', '.').replace('、', ',')
        text = text.replace('！', '!').replace('？', '?')
        text = text.replace('：', ':').replace('；', ';')
        
        # カッコの統一
        text = text.replace('（', '(').replace('）', ')')
        text = text.replace('「', '"').replace('」', '"')
        text = text.replace('『', '"').replace('』', '"')
        
        # カタカナ→ひらがな変換
        result = []
        for char in text:
            code = ord(char)
            # カタカナ範囲 (U+30A1 - U+30F6) → ひらがな (U+3041 - U+3096)
            if 0x30A1 <= code <= 0x30F6:
                result.append(chr(code - 0x60))
            else:
                result.append(char)
        
        return ''.join(result).lower()
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        2つのテキスト間の類似度を計算 (複合スコア版)
        
        複数の手法を組み合わせて精度向上:
        1. SequenceMatcher (文字列全体)
        2. 単語レベルJaccard類似度
        3. 文字N-gram重複率
        """
        if not text1 or not text2:
            return 0.0
        
        # 正規化
        norm1 = self.normalize_text(text1)
        norm2 = self.normalize_text(text2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # 短いテキストの場合は完全一致チェック
        if norm1 == norm2:
            return 1.0
        
        # 1. SequenceMatcherで類似度計算 (40%)
        seq_score = SequenceMatcher(None, norm1, norm2).ratio()
        
        # 2. 単語レベルJaccard類似度 (30%)
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        if words1 or words2:
            jaccard = len(words1 & words2) / len(words1 | words2) if (words1 | words2) else 0.0
        else:
            jaccard = 0.0
        
        # 3. 文字N-gram (bi-gram) 重複率 (30%)
        def get_ngrams(text, n=2):
            return set(text[i:i+n] for i in range(len(text) - n + 1))
        
        ngrams1 = get_ngrams(norm1)
        ngrams2 = get_ngrams(norm2)
        if ngrams1 or ngrams2:
            ngram_score = len(ngrams1 & ngrams2) / len(ngrams1 | ngrams2) if (ngrams1 | ngrams2) else 0.0
        else:
            ngram_score = 0.0
        
        # 複合スコア
        combined = 0.4 * seq_score + 0.3 * jaccard + 0.3 * ngram_score
        
        return combined
    
    def match_paragraphs(
        self, 
        web_paragraphs: List[ParagraphEntry], 
        pdf_paragraphs: List[ParagraphEntry]
    ) -> Tuple[List[ParagraphEntry], List[ParagraphEntry], List[SyncPair]]:
        """
        Web/PDFパラグラフをマッチング
        
        アルゴリズム:
        1. 全ペアの類似度を計算
        2. 類似度が高い順にソート
        3. 1対1マッチングを行う（貪欲法）
        4. 閾値以上のペアをSyncとしてマーク
        
        Returns:
            (更新済みwebパラグラフ, 更新済みpdfパラグラフ, マッチペアリスト)
        """
        if not web_paragraphs or not pdf_paragraphs:
            return web_paragraphs, pdf_paragraphs, []
        
        print(f"[ParagraphMatcher] マッチング開始: Web {len(web_paragraphs)}件 x PDF {len(pdf_paragraphs)}件")
        
        # 全ペアの融合スコアを計算 (マルチシグナル)
        pairs = []
        for w in web_paragraphs:
            for p in pdf_paragraphs:
                # 融合スコア計算 (テキスト40% + 空間30% + 構文10%)
                # 画像類似度 (20%) は事前計算が必要なので後で追加可能
                sim = self.calculate_fusion_score(
                    text1=w.text,
                    text2=p.text,
                    rect1=w.rect,
                    rect2=p.rect,
                    image_similarity=None  # TODO: 画像比較を統合
                )
                if sim > 0.1:  # 最低閾値
                    pairs.append((w.id, p.id, sim))
        
        # 類似度が高い順にソート
        pairs.sort(key=lambda x: x[2], reverse=True)
        
        # 1対1マッチング（貪欲法）
        matched_web = set()
        matched_pdf = set()
        sync_pairs = []
        color_index = 0
        
        for web_id, pdf_id, sim in pairs:
            if web_id in matched_web or pdf_id in matched_pdf:
                continue
            
            # マッチ確定
            matched_web.add(web_id)
            matched_pdf.add(pdf_id)
            
            # 色割り当て
            if sim >= self.threshold_high:
                color = self.SYNC_COLORS[color_index % len(self.SYNC_COLORS)]
                color_index += 1
            elif sim >= self.threshold_low:
                color = "#FF9800"  # オレンジ (部分マッチ)
            else:
                color = "#F44336"  # 赤 (低マッチ)
            
            sync_pairs.append(SyncPair(
                web_id=web_id,
                pdf_id=pdf_id,
                similarity=sim,
                color=color
            ))
        
        # パラグラフにSync情報を付与
        sync_map_web = {sp.web_id: sp for sp in sync_pairs}
        sync_map_pdf = {sp.pdf_id: sp for sp in sync_pairs}
        
        for w in web_paragraphs:
            if w.id in sync_map_web:
                sp = sync_map_web[w.id]
                w.sync_id = sp.pdf_id
                w.similarity = sp.similarity
                w.sync_color = sp.color
            else:
                w.sync_id = None
                w.similarity = 0.0
                w.sync_color = "#F44336"  # 未マッチは赤
        
        for p in pdf_paragraphs:
            if p.id in sync_map_pdf:
                sp = sync_map_pdf[p.id]
                p.sync_id = sp.web_id
                p.similarity = sp.similarity
                p.sync_color = sp.color
            else:
                p.sync_id = None
                p.similarity = 0.0
                p.sync_color = "#F44336"  # 未マッチは赤
        
        # 統計出力
        high_matches = sum(1 for sp in sync_pairs if sp.similarity >= self.threshold_high)
        mid_matches = sum(1 for sp in sync_pairs if self.threshold_low <= sp.similarity < self.threshold_high)
        low_matches = sum(1 for sp in sync_pairs if sp.similarity < self.threshold_low)
        
        print(f"[ParagraphMatcher] マッチング完了:")
        print(f"  🟢 高マッチ (50%+): {high_matches}件")
        print(f"  🟡 部分マッチ (30-50%): {mid_matches}件")
        print(f"  🔴 低マッチ (<30%): {low_matches}件")
        print(f"  ⚪ 未マッチ Web: {len(web_paragraphs) - len(matched_web)}件, PDF: {len(pdf_paragraphs) - len(matched_pdf)}件")
        
        return web_paragraphs, pdf_paragraphs, sync_pairs
    
    def calculate_sync_rate(self, sync_pairs: List[SyncPair], web_count: int, pdf_count: int) -> float:
        """
        全体のSync率を計算
        """
        if web_count == 0 and pdf_count == 0:
            return 0.0
        
        total_paragraphs = max(web_count, pdf_count)
        matched_weight = sum(sp.similarity for sp in sync_pairs)
        
        return matched_weight / total_paragraphs if total_paragraphs > 0 else 0.0


def create_paragraph_entries_from_clusters(
    clusters: List[Dict], 
    source: str,
    page_regions: List[Tuple[int, int]] = None
) -> List[ParagraphEntry]:
    """
    OCRクラスターからParagraphEntryリストを生成
    
    Args:
        clusters: OCR結果のクラスターリスト
        source: "web" or "pdf"
        page_regions: ページ領域リスト [(y_start, y_end), ...]
    """
    entries = []
    prefix = "W" if source == "web" else "P"
    
    for i, c in enumerate(clusters):
        # ページ番号を決定
        page_num = 1
        if page_regions:
            y_center = (c['rect'][1] + c['rect'][3]) // 2
            for j, (y_start, y_end) in enumerate(page_regions):
                if y_start <= y_center < y_end:
                    page_num = j + 1
                    break
        
        entry = ParagraphEntry(
            id=f"{prefix}-{i+1:03d}",
            source=source,
            text=c.get('text', ''),
            rect=c['rect'],
            page=page_num
        )
        entries.append(entry)
    
    return entries


def create_paragraph_entries_with_spatial_clustering(
    clusters: List[Dict], 
    source: str,
    image = None,
    page_regions: List[Tuple[int, int]] = None,
    use_spatial_clustering: bool = True
) -> List[ParagraphEntry]:
    """
    OCRクラスターからParagraphEntryリストを生成 (空間クラスタリング付き)
    
    既存のロジックに空間比率クラスタリングを追加
    
    Args:
        clusters: OCR結果のクラスターリスト
        source: "web" or "pdf"
        image: PIL Image (空間クラスタリング用、オプション)
        page_regions: ページ領域リスト [(y_start, y_end), ...]
        use_spatial_clustering: 空間クラスタリングを使用するか
    """
    # 基本のパラグラフ生成
    entries = create_paragraph_entries_from_clusters(clusters, source, page_regions)
    
    # 空間クラスタリングを追加適用
    if use_spatial_clustering and image is not None:
        try:
            from app.core.spatial_cluster_analyzer import enhance_paragraph_detection
            
            # OCR結果を辞書形式に変換
            ocr_dicts = [{'text': c.get('text', ''), 'rect': c['rect']} for c in clusters]
            
            # 空間クラスタリング実行
            enhanced = enhance_paragraph_detection(ocr_dicts, image)
            
            # ログ出力
            spatial_count = sum(1 for p in enhanced if p.get('source') == 'spatial_cluster')
            template_count = sum(1 for p in enhanced if p.get('source') == 'template_match')
            print(f"[SpatialClustering] 空間クラスター: {spatial_count}件, テンプレートマッチ: {template_count}件")
            
            # 統合結果を返す (既存+空間クラスタリング情報)
            # ※ 現在は既存結果をそのまま返し、空間情報はメタデータとして保持
            for entry in entries:
                entry_rect = entry.rect
                for p in enhanced:
                    p_rect = p.get('rect', (0,0,0,0))
                    # 重なり判定
                    if _rects_overlap(entry_rect, p_rect):
                        if p.get('source') == 'template_match':
                            # テンプレートマッチ情報を付加 (将来的にUIで利用)
                            pass
            
        except Exception as e:
            print(f"[SpatialClustering] エラー: {e}")
    
    return entries


def _rects_overlap(rect1, rect2) -> bool:
    """2つの矩形が重なっているか判定"""
    x1_1, y1_1, x2_1, y2_1 = rect1
    x1_2, y1_2, x2_2, y2_2 = rect2
    
    return not (x2_1 < x1_2 or x2_2 < x1_1 or y2_1 < y1_2 or y2_2 < y1_1)
