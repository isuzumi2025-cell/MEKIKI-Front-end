import re
import statistics
from typing import List, Dict, Any, Tuple

class StructurePropagator:
    """
    Template Propagation Engine (Genius Edition)
    ユーザーが指定した「正解領域（テンプレート）」のレイアウト/構造特徴を学習し、
    ページ全体から類似する領域を自動検出・正規化するエンジン。
    """

    def __init__(self):
        pass

    def propagate(self, 
                  template_region: Dict[str, Any], 
                  raw_words: List[Dict[str, Any]], 
                  page_size: Tuple[int, int],
                  threshold: float = 0.6,
                  image: Any = None,
                  clusters: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        テンプレート領域の特徴をページ全体に伝播させる
        
        Args:
            template_region: ユーザーが手動調整した正解領域 {rect: [x1,y1,x2,y2], text: "..."}
            raw_words: ページ全体の全単語データ (OCR生データ)
            page_size: (width, height)
            threshold: 類似度閾値 (0.0 - 1.0)
            
        Returns:
            List[Dict]: 検出・正規化された領域リスト (テンプレート自身も含む)
        """
        print(f"[Propagator] Template Rect: {template_region['rect']}")
        
        # 1. テンプレートの特徴抽出
        t_rect = template_region['rect']
        t_width = t_rect[2] - t_rect[0]
        t_height = t_rect[3] - t_rect[1]
        t_center_x = (t_rect[0] + t_rect[2]) / 2
        t_center_y = (t_rect[1] + t_rect[3]) / 2
        
        # テキスト特徴 (先頭の数字パターンなど)
        header_pattern = self._detect_header_pattern(template_region['text'])
        print(f"[Propagator] Header Pattern: {header_pattern}")

        # 2. アンカー候補の探索
        # テキストブロックの中から、テンプレートのヘッダーに似た特徴を持つものを探す
        anchors = []
        
        # 全単語またはブロックを走査
        # ここでは簡易的に raw_words を使用
        sorted_words = sorted(raw_words, key=lambda w: w['rect'][1]) # Y座標順
        
        processed_flags = [False] * len(raw_words)
        new_regions = []

        # テンプレート自体は常に採用（ただしID等は再割り当て）
        # しかし「検出」ロジックで再発見されるのが理想
        
        # 3. スキャン
        for i, word in enumerate(sorted_words):
            if processed_flags[i]: continue
            
            # アンカー判定
            if self._is_potential_anchor(word, header_pattern):
                # アンカーが見つかったら、そこを起点（左上 or 中央）としてテンプレート枠を適用
                # 注: アンカーが「枠内のどこにあったか」を考慮する必要がある
                
                # テンプレート内のアンカー（先頭の文字）の相対位置
                # 簡易実装: テンプレートは「左上」に強い特徴があると仮定
                # または、wordの座標から「仮想ボックス」を投影して、中身の充実度を測る
                
                # 仮想ボックスの構築 (WordをHeaderと仮定)
                # Wordの左上 (wx1, wy1) が、テンプレート内のヘッダー位置 (tx1, ty1) に対応すると仮定
                # dx = wx1 - tx1, dy = wy1 - ty1
                
                # しかしテンプレート内のどの文字がヘッダーか不明な場合もある
                # ここでは「数字パターン」が検出された場合、数字＝アンカーとする
                
                anchor_score = 1.0
                
                # 投影
                proj_rect = [
                    word['rect'][0] - 10, # 少しマージン
                    word['rect'][1] - 10,
                    word['rect'][0] + t_width - 10, # テンプレート幅
                    word['rect'][1] + t_height - 10
                ]
                
                # 領域内の単語を収集
                captured_indices, captured_text_len = self._capture_words_in_rect(proj_rect, raw_words)
                
                if captured_indices:
                    # 密度チェック (テンプレートと比較)
                    # テンプレートの文字数密度に近いか？
                    # ここではシンプルに「文字が含まれているか」
                    
                    # 領域生成
                    new_region = {
                        "rect": proj_rect,
                        "score": anchor_score,
                        "anchor_word": word['text']
                    }
                    new_regions.append(new_region)
                    
        # --- 4. Visual Anchoring (Added) ---
        if image:
            try:
                from app.core.visual_propagator import VisualPropagator
                
                # Crop template image
                tx1, ty1, tx2, ty2 = map(int, t_rect)
                # Bounds check
                if tx1 >= 0 and ty1 >= 0 and tx2 <= image.width and ty2 <= image.height:
                    template_img_crop = image.crop((tx1, ty1, tx2, ty2))
                    
                    vp = VisualPropagator()
                    # Use adaptive thresholds for visual match (Recall priority)
                    # Lower threshold step-by-step to gather candidates
                    thresholds = [0.85, 0.75, 0.65]
                    
                    for th in thresholds:
                        v_anchors = vp.find_anchors(template_img_crop, image, threshold=th)
                        
                        for va in v_anchors:
                            # Visual Anchor result is already a region rect
                            # Append all; _nms_merge at the end will handle duplicates
                            new_regions.append({
                                "rect": va["rect"],
                                "score": va["score"],
                                "anchor_word": f"[ICON/IMG] (th={th})"
                            })
            except Exception as e:
                print(f"[Propagator] Visual Anchor Error: {e}")
                import traceback
                traceback.print_exc()


        # 5. 重複除去 (NMS) & 整形
        # 5. 重複除去 (NMS) & 整形
        # Always run Blob/Cluster Matching as fallback/supplement (Step 2/3 parallel)
        if clusters:
            # print("[Propagator] Running Blob/Cluster Matching supplement...")
            t_area = t_width * t_height
            if t_area > 0:
                for c in clusters:
                     # c might be dict or object
                     if isinstance(c, dict):
                         rect = c.get('rect')
                         text = c.get('text', '')
                     else:
                         rect = getattr(c, 'rect', None)
                         text = getattr(c, 'text', '')
                     
                     if not rect: continue
                     
                     # 1. Whole Blob Match (Original Logic)
                     cw = rect[2] - rect[0]
                     ch = rect[3] - rect[1]
                     c_area = cw * ch
                     
                     # Check dimensions (Relaxed for Recall)
                     size_diff = abs(c_area - t_area) / t_area
                     width_diff = abs(cw - t_width) / t_width
                     height_diff = abs(ch - t_height) / t_height
                     
                     # Column Match Logic (Genius Edition)
                     # If width matches very well (within 20%), assume variable height item (allow 500% height diff)
                     is_column_match = (width_diff < 0.2 and height_diff < 5.0)
                     
                     if (size_diff < 0.8 and width_diff < 0.8 and height_diff < 0.8) or is_column_match:
                         score = 1.0 - size_diff
                         if is_column_match: score = 0.9 - width_diff # Prioritize width match
                         
                         new_regions.append({
                             "rect": rect,
                             "score": score,
                             "anchor_word": "[CLUSTER-COL]" if is_column_match else "[CLUSTER]",
                             "text": text
                         })
                         # print(f"  > Blob matched: {rect}")
            
            # 2. Implicit Sub-Anchor Search (Multi-Anchor Logic)
            # Find the largest cluster INSIDE the template region
            sub_anchors = []
            for c in clusters:
                 c_rect = c['rect'] if isinstance(c, dict) else c.rect
                 # Check if strictly inside template
                 if c_rect[0] >= t_rect[0] - 5 and c_rect[1] >= t_rect[1] - 5 and \
                    c_rect[2] <= t_rect[2] + 5 and c_rect[3] <= t_rect[3] + 5:
                     sub_anchors.append(c)
            
            # Sort by area
            sub_anchors.sort(key=lambda c: ((c['rect'][2]-c['rect'][0])*(c['rect'][3]-c['rect'][1]) if isinstance(c, dict) else (c.rect[2]-c.rect[0])*(c.rect[3]-c.rect[1])), reverse=True)
            
            # Use top 3 sub-anchors (e.g. Photo, Number, Title) to maximize recall
            # If one is missing in target (e.g. no photo), others might trigger detection.
            for idx, main_sub in enumerate(sub_anchors[:3]):
                ms_rect = main_sub['rect'] if isinstance(main_sub, dict) else main_sub.rect
                ms_w = ms_rect[2] - ms_rect[0]
                ms_h = ms_rect[3] - ms_rect[1]
                ms_area = ms_w * ms_h
                
                # Rel Offset
                off_x = ms_rect[0] - t_rect[0]
                off_y = ms_rect[1] - t_rect[1]
                
                # print(f"[Propagator] Using Sub-Anchor [{idx}]: {ms_rect}")
                
                # Scan all clusters for similar sub-anchor
                for c in clusters:
                    c_rect = c['rect'] if isinstance(c, dict) else c.rect
                    cw = c_rect[2] - c_rect[0]
                    ch = c_rect[3] - c_rect[1]
                    c_area = cw * ch
                    
                    # Similarity Check (Height is critical, Area approx)
                    h_diff = abs(ch - ms_h) / ms_h
                    a_diff = abs(c_area - ms_area) / ms_area
                    
                    if h_diff < 0.8 and a_diff < 0.9:
                        # Reconstruct Parent Rect
                        proj_x1 = c_rect[0] - off_x
                        proj_y1 = c_rect[1] - off_y
                        proj_rect = [
                            int(proj_x1), int(proj_y1),
                            int(proj_x1 + t_width), int(proj_y1 + t_height)
                        ]
                        
                        new_regions.append({
                            "rect": proj_rect,
                            "score": 0.8 * (1.0 - a_diff),
                            "anchor_word": f"[SUB-ANCHOR-{idx}]"
                        })


        print(f"[Propagator] Candidates before NMS: {len(new_regions)}")
        final_regions = self._nms_merge(new_regions, t_width, t_height)
        
        return final_regions

    def _detect_header_pattern(self, text: str) -> str:
        """テキスト先頭の特徴パターンを正規表現で返す"""
        clean_text = text.strip()
        # 数字 (01, 1., (1))
        # 数字 (01, 1., (1)) - Loosened per P-004
        if re.search(r'[0-9０-９]{1,2}', clean_text):
            return r'[0-9０-９]{1,2}'
        # アルファベット (A, B...)
        if re.match(r'^[A-Z]\d?', clean_text):
            return r'^[A-Z]\d?'
        
        # Fallback for Kanji/Text headers (e.g. "和布刈神社")
        # If short enough, use the text itself as a literal pattern
        if len(clean_text) < 15 and len(clean_text) > 0:
            return "LITERAL:" + clean_text
            
        return None

    def _is_potential_anchor(self, word: Dict, pattern: str) -> bool:
        if not pattern:
            # パターンなしの場合、フォントサイズや太字などで判定したいが
            # ここでは「ある程度大きな文字」などをトリガーにするか、
            # あるいは全単語を候補にする（重い）
            return False 
        
        if pattern.startswith("LITERAL:"):
            target_text = pattern.replace("LITERAL:", "")
            # Fuzzy match or exact startsWith
            return word['text'].strip().startswith(target_text) or target_text in word['text']
            
        return bool(re.search(pattern, word['text'].strip()))

    def _capture_words_in_rect(self, rect: List[int], all_words: List[Dict]):
        indices = []
        total_len = 0
        x1, y1, x2, y2 = rect
        
        for i, w in enumerate(all_words):
            wx1, wy1, wx2, wy2 = w['rect']
            cx = (wx1 + wx2) / 2
            cy = (wy1 + wy2) / 2
            
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                indices.append(i)
                total_len += len(w['text'])
                
        return indices, total_len

    def _nms_merge(self, regions: List[Dict], width, height) -> List[Dict]:
        """Non-Maximum Suppression的な重複統合"""
        # Scoreが高い順に採用
        regions.sort(key=lambda r: r['rect'][1]) # Y順
        
        merged = []
        while regions:
            current = regions.pop(0)
            keep = True
            
            # 既存との重複チェック
            c_rect = current['rect']
            for m in merged:
                m_rect = m['rect']
                
                # 重なり判定 (IoU)
                x_left = max(c_rect[0], m_rect[0])
                y_top = max(c_rect[1], m_rect[1])
                x_right = min(c_rect[2], m_rect[2])
                y_bottom = min(c_rect[3], m_rect[3])
                
                if x_right > x_left and y_bottom > y_top:
                    intersection = (x_right - x_left) * (y_bottom - y_top)
                    area_c = (c_rect[2]-c_rect[0])*(c_rect[3]-c_rect[1])
                    if intersection / area_c > 0.8: # 0.8: Recall priority (allow slight overlap)
                        keep = False
                        break
            
            if keep:
                # テンプレートサイズに強制統一（正規化）
                # アンカー位置基準でボックスを再設定するか、今のproj_rectをそのまま使うか
                # ここではproj_rectをそのまま使う（既にサイズはテンプレートと同じはず）
                merged.append(current)
                
        # テキスト抽出
        # ここではRectだけ返す (呼び出し元でText抽出を行う)
        return merged
