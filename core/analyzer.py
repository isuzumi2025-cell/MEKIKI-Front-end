"""
Analyzer Module
コア分析エンジン - テキスト比較、類似度計算、自動マッチング
"""
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
from PIL import Image
import difflib
import uuid
from app.core.llm_client import LLMClient


@dataclass
class PageData:
    """
    ページ全体のデータ（画像とテキストを含む）
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_type: str = ""  # "web" or "pdf"
    source_id: str = ""  # URL or PDF filename
    page_num: Optional[int] = None  # PDFの場合はページ番号
    title: str = ""  # Webページのタイトル
    text: str = ""  # ページ全体のテキスト
    image: Optional[Image.Image] = None  # PIL Image
    image_path: Optional[str] = None  # 画像ファイルパス
    areas: List['DetectedArea'] = field(default_factory=list)  # テキストエリアのリスト
    error: Optional[str] = None  # エラーメッセージ
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "page_num": self.page_num,
            "title": self.title,
            "text": self.text,
            "image_path": self.image_path,
            "areas_count": len(self.areas),
            "error": self.error
        }


@dataclass
class DetectedArea:
    """
    検出されたテキストエリア
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    bbox: List[int] = field(default_factory=lambda: [0, 0, 0, 0])  # [x0, y0, x1, y1]
    confidence: float = 0.0
    source_type: str = ""  # "web" or "pdf"
    source_id: str = ""  # URL or PDF filename
    page_num: Optional[int] = None  # PDFの場合はページ番号
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "text": self.text,
            "bbox": self.bbox,
            "confidence": self.confidence,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "page_num": self.page_num
        }


@dataclass
class MatchedPair:
    """
    マッチングされたWebページとPDFページのペア
    """
    web_page: PageData
    pdf_page: PageData
    similarity_score: float
    match_type: str = "auto"  # "auto" or "manual"
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            "web_page": self.web_page.to_dict(),
            "pdf_page": self.pdf_page.to_dict(),
            "similarity_score": self.similarity_score,
            "match_type": self.match_type
        }


class ContentAnalyzer:
    """
    コンテンツ分析エンジン
    OCR結果の管理、自動マッチング、類似度計算
    """
    
    def __init__(self, ocr_engine=None):
        """
        Args:
            ocr_engine: OCREngineインスタンス（オプション）
        """
        self.ocr_engine = ocr_engine
        
        # ページレベルのデータ（画像付き）
        self.web_pages: List[PageData] = []
        self.pdf_pages: List[PageData] = []
        
        # エリアレベルのデータ（後方互換性のため残す）
        self.web_areas: List[DetectedArea] = []
        self.pdf_areas: List[DetectedArea] = []
        
        # マッチング結果
        self.matched_pairs: List[MatchedPair] = []

        # LLMクライアント (遅延初期化)
        self.llm_client = None

    def _get_llm_client(self):
        """LLMクライアントを取得（シングルトン的運用）"""
        if not self.llm_client:
            self.llm_client = LLMClient()
        return self.llm_client

    def analyze_semantic_difference(self, text1: str, text2: str) -> str:
        """
        2つのテキスト間の意味的な差異をLLMで分析する
        
        Args:
            text1: 比較元テキスト (Web)
            text2: 比較先テキスト (PDF)
            
        Returns:
            分析結果の文字列
        """
        if not text1 or not text2:
            return "⚠️ テキストが不足しているため分析できません。"

        client = self._get_llm_client()
        if not client or not client.model:
            return "⚠️ LLM機能が有効化されていません。APIキーを確認してください。"

        instruction = """
You are a professional proofreader ensuring the accuracy of a PDF derived from a Web page.
Compare the "Web Page Text" and "PDF Text" below.

Focus ONLY on meaningful differences:
- Content discrepancies (prices, dates, names, key facts).
- Missing disclaimers or legal text.
- Significant wording changes that alter meaning.

IGNORE:
- Extra newlines, whitespace, or tab characters.
- Simple formatting differences (bullet points vs dashes).
- Headers/Footers that appear in one but not the other (unless critical).

Output format:
- Start with a summary: "✅ Matches Semantically" or "⚠️ Significant Differences Comparison".
- Bullet points explaining key differences.
- Be concise and professional. Japanese language.
"""
        
        prompt = f"{instruction}\n\n=== Web Page Text ===\n{text1}\n\n=== PDF Text ===\n{text2}"
        
        try:
            print("🤖 LLM分析を実行中...")
            result = client.generate_content(prompt)
            if result:
                return result
            else:
                return "⚠️ 分析結果を取得できませんでした。"
        except Exception as e:
            return f"⚠️ エラーが発生しました: {str(e)}"
    
    def analyze_image(
        self,
        image_path: str,
        source_type: str,
        source_id: str,
        page_num: Optional[int] = None
    ) -> List[DetectedArea]:
        """
        画像をOCRにかけ、結果をDetectedAreaのリストに変換して保存
        
        Args:
            image_path: 画像ファイルのパス
            source_type: "web" or "pdf"
            source_id: URL or PDF filename
            page_num: PDFの場合はページ番号
        
        Returns:
            DetectedAreaのリスト
        """
        # ファイル存在確認
        if not Path(image_path).exists():
            print(f"⚠️ 画像ファイルが見つかりません: {image_path}")
            return []
        
        # OCRエンジンの確認
        if not self.ocr_engine:
            print("⚠️ OCRエンジンが初期化されていません")
            return []
        
        try:
            # OCR実行
            print(f"🔍 OCR実行中: {Path(image_path).name}")
            result = self.ocr_engine.detect_document_text(image_path)
            
            if not result:
                print(f"⚠️ OCR結果が取得できませんでした: {image_path}")
                return []
            
            # DetectedAreaに変換
            areas = []
            for block in result.get("blocks", []):
                area = DetectedArea(
                    text=block["text"],
                    bbox=block["bbox"],
                    confidence=block["confidence"],
                    source_type=source_type,
                    source_id=source_id,
                    page_num=page_num
                )
                areas.append(area)
            
            # リストに追加
            if source_type == "web":
                self.web_areas.extend(areas)
            elif source_type == "pdf":
                self.pdf_areas.extend(areas)
            
            print(f"✅ {len(areas)} エリア検出: {Path(image_path).name}")
            return areas
            
        except Exception as e:
            print(f"⚠️ 画像分析エラー: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def compute_auto_matches(
        self,
        threshold: float = 0.05,  # 業務用: 低閾値で広くマッチング
        method: str = "hybrid",
        force_match: bool = True  # 強制マッチングモード
    ) -> List[MatchedPair]:
        """
        WebページとPDFページのテキスト類似度を計算し、自動ペアリング（業務用改良版）
        
        Args:
            threshold: マッチング閾値（デフォルト: 0.05 = 5%以上の類似度）
            method: 類似度計算方法 ("difflib", "jaccard", "hybrid")
            force_match: Trueの場合、閾値に関係なく必ず最も近いページをペアリング
        
        Returns:
            MatchedPairのリスト
        """
        # ページデータを優先的に使用
        use_pages = bool(self.web_pages and self.pdf_pages)
        
        if use_pages:
            web_items = self.web_pages
            pdf_items = self.pdf_pages
            print(f"\n{'='*60}")
            print(f"🔄 [Matching] 自動マッチング開始（ページ単位）")
            print(f"  Web Pages: {len(web_items)}")
            print(f"  PDF Pages: {len(pdf_items)}")
            print(f"  Threshold: {threshold*100:.1f}%")
            print(f"  Method: {method}")
            print(f"  Force Match: {'ON' if force_match else 'OFF'}")
            print(f"{'='*60}\n")
        else:
            # 後方互換性: エリアデータを使用
            if not self.web_areas or not self.pdf_areas:
                print("⚠️ データがありません")
                return []
            web_items = self.web_areas
            pdf_items = self.pdf_areas
            print(f"🔄 自動マッチング開始（エリア単位）: Web {len(web_items)} × PDF {len(pdf_items)}")
        
        self.matched_pairs.clear()
        
        try:
            # 各Webアイテムに対して最適なPDFアイテムを探す
            for i, web_item in enumerate(web_items, start=1):
                best_match = None
                best_score = 0.0
                
                web_text = web_item.text if hasattr(web_item, 'text') else ""
                web_id = web_item.source_id if hasattr(web_item, 'source_id') else f"Web{i}"
                
                # エラーページはスキップ
                if hasattr(web_item, 'error') and web_item.error:
                    print(f"[Match] ⏭️  Skipped: {web_id[:60]} (Error page)")
                    continue
                
                # テキストが空の場合はスキップ
                if not web_text or len(web_text.strip()) < 10:
                    print(f"[Match] ⏭️  Skipped: {web_id[:60]} (Empty text)")
                    continue
                
                print(f"[Match] [{i}/{len(web_items)}] Processing: {web_id[:60]}")
                print(f"        Web text: {len(web_text)} chars")
                
                # 全PDFページとのスコアを計算
                scores = []
                for j, pdf_item in enumerate(pdf_items, start=1):
                    pdf_text = pdf_item.text if hasattr(pdf_item, 'text') else ""
                    pdf_id = f"PDF-P{pdf_item.page_num}" if hasattr(pdf_item, 'page_num') else f"PDF{j}"
                    
                    if not pdf_text or len(pdf_text.strip()) < 10:
                        continue
                    
                    # 類似度を計算
                    if method == "difflib":
                        score = self._calculate_similarity(web_text, pdf_text)
                    elif method == "jaccard":
                        score = self._calculate_jaccard(web_text, pdf_text)
                    else:  # hybrid
                        score1 = self._calculate_similarity(web_text, pdf_text)
                        score2 = self._calculate_jaccard(web_text, pdf_text)
                        score = (score1 + score2) / 2
                    
                    scores.append((score, pdf_item, pdf_id))
                    
                    # 最高スコアを記録
                    if score > best_score:
                        best_score = score
                        best_match = pdf_item
                
                # スコアでソート（降順）
                scores.sort(reverse=True, key=lambda x: x[0])
                
                # Top 3を表示
                print(f"        Top matches:")
                for rank, (score, pdf_item, pdf_id) in enumerate(scores[:3], start=1):
                    indicator = "✅" if rank == 1 and (force_match or score >= threshold) else "  "
                    print(f"        {indicator} #{rank}: {pdf_id} → {score*100:.2f}%")
                
                # マッチング判定
                if force_match:
                    # 強制マッチングモード: 必ず最も近いページをペアリング
                    if best_match:
                        pair = MatchedPair(
                            web_page=web_item,
                            pdf_page=best_match,
                            similarity_score=best_score,
                            match_type="auto_forced"
                        )
                        self.matched_pairs.append(pair)
                        print(f"        ✅ Matched (Forced): {best_score*100:.2f}%\n")
                else:
                    # 通常モード: 閾値を超えている場合のみペアリング
                    if best_match and best_score >= threshold:
                        pair = MatchedPair(
                            web_page=web_item,
                            pdf_page=best_match,
                            similarity_score=best_score,
                            match_type="auto"
                        )
                        self.matched_pairs.append(pair)
                        print(f"        ✅ Matched: {best_score*100:.2f}%\n")
                    else:
                        print(f"        ❌ No match (Best: {best_score*100:.2f}% < {threshold*100:.1f}%)\n")
            
            print(f"\n{'='*60}")
            print(f"✅ [Matching] Complete: {len(self.matched_pairs)} ペアが見つかりました")
            print(f"{'='*60}\n")
            return self.matched_pairs
            
        except Exception as e:
            print(f"⚠️ マッチング処理エラー: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        difflib を使用した類似度計算
        
        Args:
            text1: テキスト1
            text2: テキスト2
        
        Returns:
            類似度 (0.0-1.0)
        """
        if not text1 or not text2:
            return 0.0
        
        return difflib.SequenceMatcher(None, text1, text2).ratio()
    
    def _calculate_jaccard(self, text1: str, text2: str) -> float:
        """
        Jaccard係数を計算（単語ベース）
        
        Args:
            text1: テキスト1
            text2: テキスト2
        
        Returns:
            Jaccard係数 (0.0-1.0)
        """
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def find_differences(self, text1: str, text2: str) -> List[Dict]:
        """
        2つのテキスト間の差分を検出
        
        Args:
            text1: テキスト1
            text2: テキスト2
        
        Returns:
            差分リスト [{"type": "add/delete/change", "text": str, "line": int}, ...]
        """
        differences = []
        
        # 行ごとに分割
        lines1 = text1.splitlines()
        lines2 = text2.splitlines()
        
        # ndiff で差分を取得
        diff = difflib.ndiff(lines1, lines2)
        
        line_num = 0
        for item in diff:
            if item.startswith('+ '):  # 追加
                differences.append({
                    "type": "add",
                    "text": item[2:],
                    "line": line_num
                })
            elif item.startswith('- '):  # 削除
                differences.append({
                    "type": "delete",
                    "text": item[2:],
                    "line": line_num
                })
            elif item.startswith('? '):  # 変更インジケータ
                pass  # スキップ
            else:  # 同一行
                line_num += 1
        
        return differences
    
    def add_manual_pair(
        self,
        web_area: DetectedArea,
        pdf_area: DetectedArea
    ) -> MatchedPair:
        """
        手動でペアを追加
        
        Args:
            web_area: Webエリア
            pdf_area: PDFエリア
        
        Returns:
            作成されたMatchedPair
        """
        # 類似度を計算
        score = self._calculate_similarity(web_area.text, pdf_area.text)
        
        pair = MatchedPair(
            web_area=web_area,
            pdf_area=pdf_area,
            similarity_score=score,
            match_type="manual"
        )
        
        self.matched_pairs.append(pair)
        print(f"✅ 手動ペア追加: スコア {score:.2%}")
        
        return pair
    
    def clear_all(self):
        """全データをクリア"""
        self.web_pages.clear()
        self.pdf_pages.clear()
        self.web_areas.clear()
        self.pdf_areas.clear()
        self.matched_pairs.clear()
        print("🗑️ 全データをクリアしました")
    
    def get_statistics(self) -> Dict:
        """統計情報を取得"""
        return {
            "web_areas_count": len(self.web_areas),
            "pdf_areas_count": len(self.pdf_areas),
            "matched_pairs_count": len(self.matched_pairs),
            "average_similarity": sum(p.similarity_score for p in self.matched_pairs) / len(self.matched_pairs) if self.matched_pairs else 0.0
        }

