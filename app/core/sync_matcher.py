"""
Sync Matcher - パラグラフ類似度マッチング
Web/PDF間で対応するパラグラフを検出し、共通のSync番号を付与

Features:
- ファジーストリングマッチング
- 類似度スコア計算
- Sync番号生成
"""
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from difflib import SequenceMatcher
import re


@dataclass
class AreaCode:
    """エリアコード (P-Seq-Sync形式)"""
    page: int  # ページ番号
    seq: int   # ページ内連番
    sync: Optional[int] = None  # シンクロ番号 (マッチしてない場合None)
    
    @property
    def code(self) -> str:
        """P1-2 S3 形式のコード文字列"""
        base = f"P{self.page}-{self.seq}"
        if self.sync is not None:
            return f"{base} S{self.sync}"
        return f"{base} --"
    
    @property
    def short_code(self) -> str:
        """P1-2 形式の短いコード"""
        return f"P{self.page}-{self.seq}"


@dataclass
class SyncPair:
    """マッチしたペア"""
    web_area: AreaCode
    pdf_area: AreaCode
    sync_number: int
    similarity: float  # 0-1
    web_text: str
    pdf_text: str
    
    @property
    def match_status(self) -> str:
        """マッチ状態のアイコン"""
        if self.similarity >= 0.95:
            return "✅"
        elif self.similarity >= 0.70:
            return "⚠️"
        else:
            return "❌"


@dataclass
class ClusterWithArea:
    """エリアコード付きクラスタ"""
    cluster: Dict
    area_code: AreaCode
    page_y_offset: int = 0  # ページ内でのY座標オフセット


class SyncMatcher:
    """
    パラグラフ類似度マッチング
    Web/PDF間で対応するテキストを検出
    """
    
    def __init__(
        self,
        similarity_threshold: float = 0.5,
        normalize_text: bool = True
    ):
        """
        Args:
            similarity_threshold: マッチと判定する最小類似度
            normalize_text: テキスト正規化を行うか
        """
        self.similarity_threshold = similarity_threshold
        self.normalize_text = normalize_text
        self._sync_counter = 0
    
    def _normalize(self, text: str) -> str:
        """テキスト正規化"""
        if not self.normalize_text:
            return text
        
        # 空白の正規化
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # 全角→半角（数字、英字）
        text = text.translate(str.maketrans(
            'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ０１２３４５６７８９',
            'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        ))
        
        return text
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        2つのテキストの類似度を計算
        
        Returns:
            float: 0-1の類似度
        """
        if not text1 or not text2:
            return 0.0
        
        norm1 = self._normalize(text1)
        norm2 = self._normalize(text2)
        
        # SequenceMatcherで類似度計算
        matcher = SequenceMatcher(None, norm1, norm2)
        return matcher.ratio()
    
    def assign_area_codes(
        self,
        clusters: List[Dict],
        page_breaks: List[Tuple[int, int]]  # [(y_start, y_end), ...]
    ) -> List[ClusterWithArea]:
        """
        クラスタにエリアコードを付与
        
        Args:
            clusters: OCRクラスタリスト
            page_breaks: ページ区切り [(y_start, y_end), ...]
        
        Returns:
            エリアコード付きクラスタのリスト
        """
        result = []
        
        # ページごとにクラスタを振り分け
        page_clusters: Dict[int, List[Tuple[Dict, int]]] = {}  # page -> [(cluster, y_offset)]
        
        for cluster in clusters:
            y_center = (cluster['rect'][1] + cluster['rect'][3]) // 2
            
            # どのページに属するか判定
            page_num = 1
            y_offset = 0
            
            for i, (y_start, y_end) in enumerate(page_breaks):
                if y_start <= y_center < y_end:
                    page_num = i + 1
                    y_offset = y_start
                    break
            
            if page_num not in page_clusters:
                page_clusters[page_num] = []
            
            page_clusters[page_num].append((cluster, y_offset))
        
        # 各ページ内で連番を付与
        for page_num in sorted(page_clusters.keys()):
            # Y座標でソート
            sorted_clusters = sorted(
                page_clusters[page_num],
                key=lambda x: x[0]['rect'][1]
            )
            
            for seq, (cluster, y_offset) in enumerate(sorted_clusters, start=1):
                area_code = AreaCode(page=page_num, seq=seq, sync=None)
                result.append(ClusterWithArea(
                    cluster=cluster,
                    area_code=area_code,
                    page_y_offset=y_offset
                ))
        
        return result
    
    def match_paragraphs(
        self,
        web_clusters: List[ClusterWithArea],
        pdf_clusters: List[ClusterWithArea]
    ) -> Tuple[List[SyncPair], List[ClusterWithArea], List[ClusterWithArea]]:
        """
        Web/PDF間でパラグラフをマッチング
        
        Returns:
            (matched_pairs, unmatched_web, unmatched_pdf)
        """
        # エントリーログ - メソッドが呼ばれているか確認
        log_path = r"c:\Users\raiko\OneDrive\Desktop\26\OCR\sync_debug.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"=== match_paragraphs called: Web={len(web_clusters)}, PDF={len(pdf_clusters)} ===\n\n")
            f.flush()
        
        self._sync_counter = 0
        matched_pairs = []
        used_pdf_indices = set()
        
        # 各Webクラスタに対してベストマッチを探す
        for web_item in web_clusters:
            web_text = web_item.cluster.get('text', '')
            best_match = None
            best_similarity = 0.0
            best_idx = -1
            
            # デバッグ: 長文（20文字以上）のマッチング状況をログ
            is_long_text = len(web_text) >= 20
            top_similarity = 0.0
            top_pdf_text = ""
            
            for idx, pdf_item in enumerate(pdf_clusters):
                if idx in used_pdf_indices:
                    continue
                
                pdf_text = pdf_item.cluster.get('text', '')
                similarity = self.calculate_similarity(web_text, pdf_text)
                
                # 最高類似度を追跡
                if similarity > top_similarity:
                    top_similarity = similarity
                    top_pdf_text = pdf_text
                
                if similarity > best_similarity and similarity >= self.similarity_threshold:
                    best_similarity = similarity
                    best_match = pdf_item
                    best_idx = idx
            
            # デバッグ: 全ての長文についてログ出力
            if is_long_text:
                log_path = r"c:\Users\raiko\OneDrive\Desktop\26\OCR\sync_debug.log"
                with open(log_path, "a", encoding="utf-8") as f:
                    status = "✓ MATCHED" if best_match else "✗ NO MATCH"
                    f.write(f"[{status}] sim={best_similarity:.0%} (top={top_similarity:.0%})\n")
                    f.write(f"  Web({len(web_text)}): {web_text[:60]}...\n")
                    if best_match:
                        f.write(f"  PDF: {best_match.cluster.get('text', '')[:60]}...\n")
                    else:
                        f.write(f"  Best PDF candidate ({top_similarity:.0%}): {top_pdf_text[:60]}...\n")
                    f.write("\n")
                    f.flush()
            
            if best_match:
                self._sync_counter += 1
                sync_num = self._sync_counter
                
                # 両方のエリアコードにSync番号を設定
                web_item.area_code.sync = sync_num
                best_match.area_code.sync = sync_num
                
                pair = SyncPair(
                    web_area=web_item.area_code,
                    pdf_area=best_match.area_code,
                    sync_number=sync_num,
                    similarity=best_similarity,
                    web_text=web_text,
                    pdf_text=best_match.cluster.get('text', '')
                )
                matched_pairs.append(pair)
                used_pdf_indices.add(best_idx)
        
        # マッチしなかったものを収集
        unmatched_web = [
            item for item in web_clusters
            if item.area_code.sync is None
        ]
        unmatched_pdf = [
            item for idx, item in enumerate(pdf_clusters)
            if idx not in used_pdf_indices
        ]
        
        return matched_pairs, unmatched_web, unmatched_pdf
    
    def get_sync_summary(
        self,
        pairs: List[SyncPair],
        unmatched_web: List[ClusterWithArea],
        unmatched_pdf: List[ClusterWithArea]
    ) -> Dict:
        """
        マッチング結果のサマリーを取得
        """
        total_matched = len(pairs)
        total_unmatched_web = len(unmatched_web)
        total_unmatched_pdf = len(unmatched_pdf)
        
        avg_similarity = (
            sum(p.similarity for p in pairs) / total_matched
            if total_matched > 0 else 0.0
        )
        
        high_match = sum(1 for p in pairs if p.similarity >= 0.95)
        medium_match = sum(1 for p in pairs if 0.70 <= p.similarity < 0.95)
        low_match = sum(1 for p in pairs if p.similarity < 0.70)
        
        return {
            'total_matched': total_matched,
            'unmatched_web': total_unmatched_web,
            'unmatched_pdf': total_unmatched_pdf,
            'average_similarity': avg_similarity,
            'high_match_count': high_match,
            'medium_match_count': medium_match,
            'low_match_count': low_match,
            'overall_sync_rate': (
                total_matched / (total_matched + total_unmatched_web + total_unmatched_pdf)
                if (total_matched + total_unmatched_web + total_unmatched_pdf) > 0
                else 0.0
            )
        }


# テスト用
if __name__ == "__main__":
    matcher = SyncMatcher()
    
    # テストテキスト
    text1 = "おトクなきっぷで九州の寺社めぐりをしよう！"
    text2 = "おトクなきっぷで九州の寺社めぐりをしよう!"  # 末尾が少し違う
    
    similarity = matcher.calculate_similarity(text1, text2)
    print(f"類似度: {similarity:.2%}")
    
    # テストコード
    code = AreaCode(page=1, seq=2, sync=3)
    print(f"エリアコード: {code.code}")  # P1-2 S3
