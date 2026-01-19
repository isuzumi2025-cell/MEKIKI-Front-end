"""
高度な領域検出エンジン
既存のOCRツールで実証された近接クラスタリングと動的密度クラスタリングを移植
Web画像とPDF画像の両方に対応する汎用版

Source: OCRappBackupFile/OCR_reborn/app/core/engine_clustering.py
Ported: 2026-01-11
"""

import statistics
from typing import List, Dict, Tuple, Any


class ClusteringEngine:
    """
    画像解析結果（単語・ブロック情報）から、意味のある「領域」を自動検出する
    
    アルゴリズム:
    1. 近接クラスタリング (Proximity Clustering)
       - 縦方向に近い文字ブロックを統合
       - フォントサイズと位置関係を考慮
    
    2. 動的密度クラスタリング (Dynamic Density Clustering)
       - 孤立した小領域を近くの大きな領域に吸収
       - 平均面積に基づく閾値の動的調整
    """
    
    def __init__(self, mode: str = "normal"):
        """
        初期化
        
        Args:
            mode: "normal" (標準) or "relaxed" (広告向け緩和)
        """
        self.raw_blocks = []
        self.clusters = []
        self.mode = mode
        
        # モードに応じたパラメータ設定
        if mode == "relaxed":
            self.overlap_threshold = 0.5   # 50% (通常70%)
            self.left_diff_threshold = 40  # 40px (通常20px)
            self.y_threshold_min = 120     # 120px (通常80px)
            self.y_threshold_multiplier = 3.5  # 3.5x (通常2.5x)
            self.x_gap_threshold = 30      # 30px (通常10px)
            self.font_ratio_upper = 2.5    # 2.5x (通常2.0x)
            self.font_ratio_lower = 2.0    # 2.0x (通常1.5x)
        else:
            self.overlap_threshold = 0.7
            self.left_diff_threshold = 20
            self.y_threshold_min = 80
            self.y_threshold_multiplier = 2.5
            self.x_gap_threshold = 10
            self.font_ratio_upper = 2.0
            self.font_ratio_lower = 1.5
    
    def cluster_from_blocks(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        文字ブロックのリストからクラスタリングを実行
        
        Args:
            blocks: 各ブロックは以下の形式
                {
                    "text": str,
                    "rect": [x0, y0, x1, y1],
                    "center_x": float,
                    "width": float,
                    "font_size": float
                }
        
        Returns:
            clusters: 各クラスタは以下の形式
                {
                    "id": int,
                    "rect": [x0, y0, x1, y1],
                    "text": str (改行区切り)
                }
        """
        if not blocks:
            return []
        
        # Phase 1: 縦方向スタッククラスタリング
        vertical_clusters = self._vertical_stack_clustering(blocks)
        
        # Phase 2: 孤立エリアの吸収
        final_clusters = self._orphan_absorption(vertical_clusters)
        
        # ソート（上から下、左から右）
        def sort_key(cluster):
            x0, y0, _, _ = cluster["rect"]
            row = round(y0 / 60) * 60  # 60pxごとに同一行とみなす
            return (row, x0)
        
        final_clusters.sort(key=sort_key)
        
        # ID付与と整形
        formatted_clusters = []
        for i, c in enumerate(final_clusters):
            formatted_clusters.append({
                "id": i + 1,
                "rect": list(map(int, c["rect"])),
                "text": "\n".join(c["texts"]) if isinstance(c.get("texts"), list) else c.get("text", "")
            })
        
        return formatted_clusters
    
    def _vertical_stack_clustering(self, blocks: List[Dict]) -> List[Dict]:
        """
        【近接クラスタリング】
        縦方向に近い文字ブロックを統合する
        
        判定条件:
        - 横方向の重なり率 > 70% または 左端の差 < 20px
        - 縦方向の間隔 < フォントサイズ × 2.5（最小80px）
        - フォントサイズの差が2倍以内
        - 横方向の間隔 < 10px
        """
        if not blocks:
            return []
        
        # Y座標でソート
        blocks.sort(key=lambda b: b["rect"][1])
        
        # 初期クラスタ（各ブロックを独立したクラスタとして開始）
        clusters = [{
            "rect": b["rect"].copy() if isinstance(b["rect"], list) else list(b["rect"]),
            "texts": [b["text"]],
            "width": b["width"],
            "center_x": b["center_x"],
            "avg_font_size": b["font_size"]
        } for b in blocks]
        
        # 反復統合
        has_merged = True
        while has_merged:
            has_merged = False
            new_clusters = []
            skip_indices = set()
            
            for i in range(len(clusters)):
                if i in skip_indices:
                    continue
                
                current = clusters[i]
                
                # 後続のクラスタと結合を試みる
                for j in range(i + 1, len(clusters)):
                    if j in skip_indices:
                        continue
                    
                    target = clusters[j]
                    
                    # === 結合判定ロジック ===
                    
                    # 1. 横方向の位置合わせチェック
                    x_overlap = min(current["rect"][2], target["rect"][2]) - max(current["rect"][0], target["rect"][0])
                    min_width = min(current["width"], target["width"])
                    overlap_ratio = x_overlap / min_width if min_width > 0 else 0
                    left_diff = abs(current["rect"][0] - target["rect"][0])
                    
                    is_aligned = overlap_ratio > self.overlap_threshold or left_diff < self.left_diff_threshold
                    if not is_aligned:
                        continue
                    
                    # 2. 縦方向の間隔チェック
                    gap_y = target["rect"][1] - current["rect"][3]
                    base_size = max(current["avg_font_size"], target["avg_font_size"])
                    threshold_y = max(base_size * self.y_threshold_multiplier, self.y_threshold_min)
                    
                    if gap_y > threshold_y:
                        continue
                    
                    # 3. フォントサイズの整合性チェック
                    if current["avg_font_size"] > target["avg_font_size"] * self.font_ratio_upper:
                        continue
                    if target["avg_font_size"] > current["avg_font_size"] * self.font_ratio_lower:
                        continue
                    
                    # 4. 横方向の間隔チェック（横並び防止）
                    if current["rect"][0] < target["rect"][0]:
                        gap_x = max(0, target["rect"][0] - current["rect"][2])
                    else:
                        gap_x = max(0, current["rect"][0] - target["rect"][2])
                    
                    if gap_x > self.x_gap_threshold:
                        continue
                    
                    # === 結合実行 ===
                    new_rect = [
                        min(current["rect"][0], target["rect"][0]),
                        min(current["rect"][1], target["rect"][1]),
                        max(current["rect"][2], target["rect"][2]),
                        max(current["rect"][3], target["rect"][3])
                    ]
                    
                    # テキストの順序を保持
                    if current["rect"][1] < target["rect"][1]:
                        new_texts = current["texts"] + target["texts"]
                    else:
                        new_texts = target["texts"] + current["texts"]
                    
                    new_avg = max(current["avg_font_size"], target["avg_font_size"])
                    
                    current = {
                        "rect": new_rect,
                        "texts": new_texts,
                        "width": new_rect[2] - new_rect[0],
                        "center_x": (new_rect[0] + new_rect[2]) / 2,
                        "avg_font_size": new_avg
                    }
                    
                    skip_indices.add(j)
                    has_merged = True
                
                new_clusters.append(current)
            
            clusters = new_clusters
        
        return clusters
    
    def _orphan_absorption(self, clusters: List[Dict]) -> List[Dict]:
        """
        【動的密度クラスタリング】
        孤立した小さな領域を近くの大きな領域に吸収する
        
        孤立判定:
        - 面積が平均の10%以下
        - または、テキスト文字数が3文字未満
        
        吸収条件:
        - 最も近い親領域との距離が200px以内
        """
        if not clusters:
            return []
        
        # 平均面積の計算
        areas = [
            (c["rect"][2] - c["rect"][0]) * (c["rect"][3] - c["rect"][1])
            for c in clusters
        ]
        avg_area = statistics.mean(areas) if areas else 0
        orphan_threshold = avg_area * 0.1
        
        # 孤立エリアと通常エリアに分類
        final_clusters = []
        orphans = []
        
        for c in clusters:
            area = (c["rect"][2] - c["rect"][0]) * (c["rect"][3] - c["rect"][1])
            text_len = sum(len(t) for t in c["texts"])
            
            if area < orphan_threshold or text_len < 3:
                orphans.append(c)
            else:
                final_clusters.append(c)
        
        # 通常エリアがない場合は全て返す
        if not final_clusters:
            return clusters
        
        # 各孤立エリアを最も近い親に吸収
        for orphan in orphans:
            best_parent = None
            min_dist = float('inf')
            r1 = orphan["rect"]
            
            for parent in final_clusters:
                r2 = parent["rect"]
                
                # マンハッタン距離（矩形間）
                if r1[0] < r2[0]:
                    dx = max(0, r2[0] - r1[2])
                else:
                    dx = max(0, r1[0] - r2[2])
                
                if r1[1] < r2[1]:
                    dy = max(0, r2[1] - r1[3])
                else:
                    dy = max(0, r1[1] - r2[3])
                
                dist = dx + dy
                
                if dist < 200 and dist < min_dist:
                    min_dist = dist
                    best_parent = parent
            
            # 吸収実行
            if best_parent:
                r_p = best_parent["rect"]
                r_o = orphan["rect"]
                best_parent["rect"] = [
                    min(r_p[0], r_o[0]),
                    min(r_p[1], r_o[1]),
                    max(r_p[2], r_o[2]),
                    max(r_p[3], r_o[3])
                ]
                best_parent["texts"].extend(orphan["texts"])
                best_parent["width"] = best_parent["rect"][2] - best_parent["rect"][0]
                best_parent["center_x"] = (best_parent["rect"][0] + best_parent["rect"][2]) / 2
            else:
                # 親が見つからない場合は独立したクラスタとして残す
                final_clusters.append(orphan)
        
        return final_clusters


class BlockExtractor:
    """
    画像解析結果から、ClusteringEngineが必要とする
    ブロック情報を抽出するユーティリティクラス
    """
    
    @staticmethod
    def extract_from_vision_api(response) -> Tuple[List[Dict], List[Dict]]:
        """
        Google Cloud Vision APIのレスポンスからブロック情報を抽出
        
        Returns:
            (blocks, raw_words): クラスタリング用ブロックと手動編集用単語データ
        """
        raw_blocks = []
        raw_words = []
        
        for page in response.full_text_annotation.pages:
            for block in page.blocks:
                block_text_parts = []
                symbol_heights = []
                
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        word_text = "".join([symbol.text for symbol in word.symbols])
                        block_text_parts.append(word_text)
                        
                        # 単語単位の情報（手動編集用）
                        wv = word.bounding_box.vertices
                        wx = [v.x for v in wv]
                        wy = [v.y for v in wv]
                        raw_words.append({
                            "text": word_text,
                            "rect": [min(wx), min(wy), max(wx), max(wy)],
                            "center": ((min(wx) + max(wx)) / 2, (min(wy) + max(wy)) / 2)
                        })
                        
                        # フォントサイズ推定
                        for symbol in word.symbols:
                            v = symbol.bounding_box.vertices
                            h = v[3].y - v[0].y
                            symbol_heights.append(h)
                
                # ブロック情報構築
                v = block.bounding_box.vertices
                x_coords = [vertex.x for vertex in v]
                y_coords = [vertex.y for vertex in v]
                
                raw_blocks.append({
                    "text": "".join(block_text_parts),
                    "rect": [min(x_coords), min(y_coords), max(x_coords), max(y_coords)],
                    "center_x": (min(x_coords) + max(x_coords)) / 2,
                    "width": max(x_coords) - min(x_coords),
                    "font_size": statistics.mean(symbol_heights) if symbol_heights else 10
                })
        
        return raw_blocks, raw_words


class VisualAwareClusteringEngine(ClusteringEngine):
    """
    視覚情報を考慮した高度なクラスタリングエンジン
    背景色、罫線、ハイライトを判定条件に追加
    """
    
    def __init__(self):
        super().__init__()
        self.same_color_bonus = 0.3  # 同色の場合の結合ボーナス
        self.border_penalty = 0.5    # 罫線がある場合の結合ペナルティ
    
    def cluster_with_visual_info(
        self,
        blocks: list,
        use_color: bool = True,
        use_borders: bool = True
    ) -> list:
        """
        視覚情報を利用したクラスタリング
        
        Args:
            blocks: 視覚情報が付与されたブロックリスト
                [{
                    "text": str,
                    "rect": [x0, y0, x1, y1],
                    "background_color": "#RRGGBB",
                    "has_border": bool,
                    "is_highlighted": bool,
                    ...
                }]
            use_color: 背景色を考慮するか
            use_borders: 罫線を考慮するか
        
        Returns:
            視覚的にも意味のあるクラスタ
        """
        if not blocks:
            return []
        
        # 通常のクラスタリングを実行
        vertical_clusters = self._vertical_stack_clustering_visual(
            blocks, use_color, use_borders
        )
        
        # 孤立エリアの吸収
        final_clusters = self._orphan_absorption(vertical_clusters)
        
        # ソート（上から下、左から右）
        def sort_key(cluster):
            x0, y0, _, _ = cluster["rect"]
            row = round(y0 / 60) * 60
            return (row, x0)
        
        final_clusters.sort(key=sort_key)
        
        # ID付与と整形
        formatted_clusters = []
        for i, c in enumerate(final_clusters):
            formatted_clusters.append({
                "id": i + 1,
                "rect": list(map(int, c["rect"])),
                "text": "\n".join(c["texts"]) if isinstance(c.get("texts"), list) else c.get("text", ""),
                "background_color": c.get("background_color", "#FFFFFF"),
                "has_border": c.get("has_border", False),
                "is_highlighted": c.get("is_highlighted", False)
            })
        
        return formatted_clusters
    
    def _vertical_stack_clustering_visual(
        self,
        blocks: list,
        use_color: bool,
        use_borders: bool
    ) -> list:
        """視覚情報を考慮した縦方向クラスタリング"""
        if not blocks:
            return []
        
        # Y座標でソート
        blocks.sort(key=lambda b: b["rect"][1])
        
        # 初期クラスタ
        clusters = [{
            "rect": b["rect"].copy() if isinstance(b["rect"], list) else list(b["rect"]),
            "texts": [b["text"]],
            "width": b.get("width", b["rect"][2] - b["rect"][0]),
            "center_x": b.get("center_x", (b["rect"][0] + b["rect"][2]) / 2),
            "avg_font_size": b.get("font_size", 10),
            "background_color": b.get("background_color", "#FFFFFF"),
            "has_border": b.get("has_border", False),
            "is_highlighted": b.get("is_highlighted", False)
        } for b in blocks]
        
        # 反復統合
        has_merged = True
        while has_merged:
            has_merged = False
            new_clusters = []
            skip_indices = set()
            
            for i in range(len(clusters)):
                if i in skip_indices:
                    continue
                
                current = clusters[i]
                
                for j in range(i + 1, len(clusters)):
                    if j in skip_indices:
                        continue
                    
                    target = clusters[j]
                    
                    # === 基本判定（既存ロジック） ===
                    x_overlap = min(current["rect"][2], target["rect"][2]) - max(current["rect"][0], target["rect"][0])
                    min_width = min(current["width"], target["width"])
                    overlap_ratio = x_overlap / min_width if min_width > 0 else 0
                    left_diff = abs(current["rect"][0] - target["rect"][0])
                    
                    is_aligned = overlap_ratio > 0.7 or left_diff < 20
                    if not is_aligned:
                        continue
                    
                    gap_y = target["rect"][1] - current["rect"][3]
                    base_size = max(current["avg_font_size"], target["avg_font_size"])
                    threshold_y = max(base_size * 2.5, 80)
                    
                    # === 視覚情報による補正 ===
                    visual_score = 0.0
                    
                    # 背景色が同じ場合はボーナス
                    if use_color:
                        if current["background_color"] == target["background_color"]:
                            visual_score += self.same_color_bonus
                            threshold_y *= 1.2  # 閾値を緩和
                        elif self._colors_are_similar(
                            current["background_color"],
                            target["background_color"]
                        ):
                            visual_score += self.same_color_bonus * 0.5
                    
                    # 罫線がある場合はペナルティ
                    if use_borders:
                        if current.get("has_border") or target.get("has_border"):
                            visual_score -= self.border_penalty
                            threshold_y *= 0.8  # 閾値を厳しく
                    
                    # 最終判定
                    effective_gap = gap_y - (visual_score * 20)  # ボーナスをpxに換算
                    if effective_gap > threshold_y:
                        continue
                    
                    # フォントサイズチェック
                    if current["avg_font_size"] > target["avg_font_size"] * 2.0:
                        continue
                    if target["avg_font_size"] > current["avg_font_size"] * 1.5:
                        continue
                    
                    # 横方向の間隔チェック
                    if current["rect"][0] < target["rect"][0]:
                        gap_x = max(0, target["rect"][0] - current["rect"][2])
                    else:
                        gap_x = max(0, current["rect"][0] - target["rect"][2])
                    
                    if gap_x > 10:
                        continue
                    
                    # === 結合実行 ===
                    new_rect = [
                        min(current["rect"][0], target["rect"][0]),
                        min(current["rect"][1], target["rect"][1]),
                        max(current["rect"][2], target["rect"][2]),
                        max(current["rect"][3], target["rect"][3])
                    ]
                    
                    if current["rect"][1] < target["rect"][1]:
                        new_texts = current["texts"] + target["texts"]
                    else:
                        new_texts = target["texts"] + current["texts"]
                    
                    current = {
                        "rect": new_rect,
                        "texts": new_texts,
                        "width": new_rect[2] - new_rect[0],
                        "center_x": (new_rect[0] + new_rect[2]) / 2,
                        "avg_font_size": max(current["avg_font_size"], target["avg_font_size"]),
                        "background_color": current["background_color"],  # 最初の色を保持
                        "has_border": current["has_border"] or target["has_border"],
                        "is_highlighted": current["is_highlighted"] or target["is_highlighted"]
                    }
                    
                    skip_indices.add(j)
                    has_merged = True
                
                new_clusters.append(current)
            
            clusters = new_clusters
        
        return clusters
    
    def _colors_are_similar(self, color1: str, color2: str, threshold: int = 30) -> bool:
        """2色が類似しているかチェック"""
        try:
            r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
            r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
            
            diff = abs(r1 - r2) + abs(g1 - g2) + abs(b1 - b2)
            return diff < threshold * 3
        except:
            return False

