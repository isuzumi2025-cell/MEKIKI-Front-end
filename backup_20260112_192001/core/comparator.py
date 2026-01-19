"""
原稿比較・校正機能のコアロジック
2つのテキストデータソースを比較し、シンクロ率と差異を検出する
"""
import difflib
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class ComparisonResult:
    """比較結果のデータクラス"""
    area_id: int
    source_a_text: str
    source_b_text: str
    sync_rate: float  # 0-100%
    status: str  # "完全一致", "差異あり", "片方のみ"
    diff_details: str
    has_source_a: bool
    has_source_b: bool


class TextComparator:
    """
    2つのテキストデータソースを比較し、シンクロ率と差異を検出するクラス
    """
    
    def __init__(self):
        self.area_id_counter = 1
    
    def compare_texts(
        self, 
        source_a: List[str], 
        source_b: List[str],
        similarity_threshold: float = 0.6
    ) -> List[ComparisonResult]:
        """
        2つのテキストリストを比較し、エリアアライメントを行い結果を返す
        
        Args:
            source_a: 比較元テキストのリスト（パラグラフ単位）
            source_b: 比較先テキストのリスト（パラグラフ単位）
            similarity_threshold: 類似度の閾値（これ以上でマッチングとみなす）
        
        Returns:
            比較結果のリスト
        """
        self.area_id_counter = 1
        results = []
        
        # 空データの処理
        if not source_a and not source_b:
            return results
        if not source_a:
            # source_bのみ存在
            for text_b in source_b:
                results.append(self._create_result(
                    source_a_text="",
                    source_b_text=text_b,
                    status="片方のみ"
                ))
            return results
        if not source_b:
            # source_aのみ存在
            for text_a in source_a:
                results.append(self._create_result(
                    source_a_text=text_a,
                    source_b_text="",
                    status="片方のみ"
                ))
            return results
        
        # エリアアライメント: 類似パラグラフを自動紐付け
        matched_indices_a = set()
        matched_indices_b = set()
        
        # まず、類似度が高いペアを見つける
        for i, text_a in enumerate(source_a):
            if i in matched_indices_a:
                continue
            
            best_match_idx = None
            best_similarity = 0.0
            
            for j, text_b in enumerate(source_b):
                if j in matched_indices_b:
                    continue
                
                similarity = self._calculate_similarity(text_a, text_b)
                if similarity > best_similarity and similarity >= similarity_threshold:
                    best_similarity = similarity
                    best_match_idx = j
            
            if best_match_idx is not None:
                # マッチング成功
                matched_indices_a.add(i)
                matched_indices_b.add(best_match_idx)
                
                text_b = source_b[best_match_idx]
                status = "完全一致" if best_similarity >= 0.95 else "差異あり"
                diff_details = self._get_diff_details(text_a, text_b)
                
                results.append(self._create_result(
                    source_a_text=text_a,
                    source_b_text=text_b,
                    sync_rate=best_similarity * 100,
                    status=status,
                    diff_details=diff_details
                ))
            else:
                # source_aにのみ存在
                results.append(self._create_result(
                    source_a_text=text_a,
                    source_b_text="",
                    status="片方のみ"
                ))
                matched_indices_a.add(i)
        
        # source_bにのみ存在するものを追加
        for j, text_b in enumerate(source_b):
            if j not in matched_indices_b:
                results.append(self._create_result(
                    source_a_text="",
                    source_b_text=text_b,
                    status="片方のみ"
                ))
        
        return results
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        2つのテキストの類似度を計算（0.0-1.0）
        difflib.SequenceMatcherを使用
        """
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
        
        # 空白を正規化して比較
        text1_normalized = " ".join(text1.split())
        text2_normalized = " ".join(text2.split())
        
        return difflib.SequenceMatcher(None, text1_normalized, text2_normalized).ratio()
    
    def _get_diff_details(self, text_a: str, text_b: str) -> str:
        """
        2つのテキストの具体的な差異を要約して返す
        """
        if text_a == text_b:
            return ""
        
        # difflibで差分を計算
        diff = list(difflib.unified_diff(
            text_a.splitlines(keepends=True),
            text_b.splitlines(keepends=True),
            lineterm='',
            n=0  # コンテキスト行数を0に
        ))
        
        if not diff:
            return ""
        
        # 差分のサマリーを生成（最初の数行のみ）
        diff_lines = []
        added_count = 0
        removed_count = 0
        
        for line in diff[2:]:  # ヘッダー行をスキップ
            if line.startswith('+') and not line.startswith('+++'):
                added_count += 1
                if len(diff_lines) < 5:  # 最大5行まで
                    diff_lines.append(f"追加: {line[1:].strip()[:50]}")
            elif line.startswith('-') and not line.startswith('---'):
                removed_count += 1
                if len(diff_lines) < 5:
                    diff_lines.append(f"削除: {line[1:].strip()[:50]}")
        
        summary = f"変更: {removed_count}行削除, {added_count}行追加"
        if diff_lines:
            summary += f"\n例: {diff_lines[0]}"
        
        return summary
    
    def _create_result(
        self,
        source_a_text: str,
        source_b_text: str,
        sync_rate: float = 0.0,
        status: str = "差異あり",
        diff_details: str = ""
    ) -> ComparisonResult:
        """ComparisonResultオブジェクトを作成"""
        result = ComparisonResult(
            area_id=self.area_id_counter,
            source_a_text=source_a_text or "",
            source_b_text=source_b_text or "",
            sync_rate=sync_rate,
            status=status,
            diff_details=diff_details,
            has_source_a=bool(source_a_text),
            has_source_b=bool(source_b_text)
        )
        self.area_id_counter += 1
        return result
    
    @staticmethod
    def split_into_paragraphs(text: str) -> List[str]:
        """
        テキストをパラグラフ（段落）単位に分割
        """
        if not text:
            return []
        
        # 改行で分割し、空行を除去
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        # パラグラフが空の場合は、単一行単位に分割
        if not paragraphs:
            paragraphs = [line.strip() for line in text.split('\n') if line.strip()]
        
        return paragraphs if paragraphs else [""]

