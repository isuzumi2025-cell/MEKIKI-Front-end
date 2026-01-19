import os
import io
import math
import statistics
from PIL import Image
from google.cloud import vision
from google.oauth2 import service_account
from app.core.interface import OCREngineStrategy

# Optional preprocessing
try:
    from app.core.image_preprocessor import ImagePreprocessor
    PREPROCESSOR_AVAILABLE = True
except ImportError:
    PREPROCESSOR_AVAILABLE = False

class CloudOCREngine(OCREngineStrategy):
    """
    Google Cloud Vision API (Raw Data Return Mode)
    GUI側で編集可能にするため、画像への描画は行わず、
    「クラスタリング結果」と「全文字の生データ」を返します。
    """

    def __init__(self, preprocess: bool = False, preprocess_binarize: bool = False):
        """
        初期化
        
        Args:
            preprocess: 前処理を有効にするか（ノイズ多い画像向け）
            preprocess_binarize: 二値化を有効にするか
        """
        self.preprocess = preprocess
        self.preprocess_binarize = preprocess_binarize
        
        key_path = "service_account.json"
        if os.path.exists(key_path):
            credentials = service_account.Credentials.from_service_account_file(key_path)
            self.client = vision.ImageAnnotatorClient(credentials=credentials)
        else:
            self.client = vision.ImageAnnotatorClient()

    def extract_text(self, image: Image.Image):
        """
        Returns: 
            clusters (list): 自動解析されたエリア情報のリスト
            raw_words (list): 全文字の生データ（手動修正時の再計算用）
        """
        try:
            # ★ 元の画像サイズを最初に保存（座標逆変換用）
            original_width = image.width
            original_height = image.height
            preprocess_scale = 1.0  # 前処理による拡大倍率
            
            # ★ 前処理オプション（ノイズ多い画像向け）
            if self.preprocess and PREPROCESSOR_AVAILABLE:
                print("🔧 前処理適用中 (ImagePreprocessor)...")
                preprocess_scale = 2.0  # ImagePreprocessorの拡大倍率
                preprocessor = ImagePreprocessor(
                    scale_factor=preprocess_scale,
                    denoise_strength=10,
                    gamma=0.7,
                    enable_binarize=self.preprocess_binarize
                )
                processed = preprocessor.process(image)
                if processed.mode == 'L':
                    image = processed.convert('RGB')
                else:
                    image = processed
                print(f"  → 前処理後サイズ: {image.size} (元: {original_width}x{original_height})")
            
            scale_ratio = 1.0  # API送信時のリサイズ比率
            
            # 画像モード変換 (RGBA/P → RGB)
            if image.mode in ('RGBA', 'P', 'LA'):
                rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'RGBA' or image.mode == 'LA':
                    rgb_image.paste(image, mask=image.split()[-1])
                else:
                    rgb_image.paste(image)
                image = rgb_image
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            # 画像サイズ制限とリサイズ戦略
            max_dimension = 4096
            min_width = 800  # OCR精度のための最小幅
            
            # アスペクト比を確認
            aspect_ratio = image.height / image.width
            
            if aspect_ratio > 5:
                # 非常に縦長の画像: チャンク分割してOCR
                print(f"📐 縦長画像検出 (アスペクト比: {aspect_ratio:.1f}) - チャンクOCRモード")
                return self._ocr_tall_image_chunks(image)
            elif image.width > max_dimension or image.height > max_dimension:
                # 通常のリサイズ (最小幅を確保)
                scale_ratio = min(max_dimension / image.width, max_dimension / image.height)
                new_width = int(image.width * scale_ratio)
                
                # 最小幅を確保
                if new_width < min_width:
                    scale_ratio = min_width / image.width
                    new_width = min_width
                
                new_height = int(image.height * scale_ratio)
                # 高さが4096を超える場合はチャンク分割
                if new_height > max_dimension:
                    print(f"📐 縦長画像検出 - 最小幅維持のためチャンクOCRモード")
                    return self._ocr_tall_image_chunks(image)
                
                new_size = (new_width, new_height)
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                print(f"📐 画像リサイズ: {new_size[0]}x{new_size[1]} (比率: {scale_ratio:.3f})")
            
            # 逆変換比率を計算 (OCR座標 → 元画像座標)
            # ★ 前処理の拡大も考慮する必要がある
            total_scale = scale_ratio * preprocess_scale  # 全体の拡大率
            inverse_ratio = 1.0 / total_scale if total_scale != 0 else 1.0
            print(f"🔄 座標変換: scale_ratio={scale_ratio:.3f}, preprocess_scale={preprocess_scale:.1f}, inverse_ratio={inverse_ratio:.3f}")
            
            # ★ PNG形式で送信 (品質維持 - Legacy互換)
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')  # JPEG → PNG に変更
            content = img_byte_arr.getvalue()
            
            # サイズ確認
            size_mb = len(content) / (1024 * 1024)
            print(f"📤 OCR送信サイズ: {size_mb:.2f}MB")
            
            vision_image = vision.Image(content=content)
            response = self.client.document_text_detection(image=vision_image)
            
            if response.error.message:
                raise RuntimeError(f"Cloud Vision API Error: {response.error.message}")

            # --- 1. 生データの取得 ---
            raw_blocks = [] # クラスタリング用
            raw_words = []  # 手動編集用（全単語の座標とテキスト）

            for page in response.full_text_annotation.pages:
                for block in page.blocks:
                    # クラスタリング用のブロック情報構築
                    block_text_parts = []
                    symbol_heights = []
                    
                    for paragraph in block.paragraphs:
                        for word in paragraph.words:
                            word_text = "".join([symbol.text for symbol in word.symbols])
                            block_text_parts.append(word_text)
                            
                            # 単語単位の情報を保存（手動編集用）
                            wv = word.bounding_box.vertices
                            wx = [v.x for v in wv]
                            wy = [v.y for v in wv]
                            raw_words.append({
                                "text": word_text,
                                "rect": [min(wx), min(wy), max(wx), max(wy)],
                                "center": ((min(wx)+max(wx))/2, (min(wy)+max(wy))/2)
                            })

                            for symbol in word.symbols:
                                v = symbol.bounding_box.vertices
                                h = v[3].y - v[0].y
                                symbol_heights.append(h)
                    
                    # ブロック情報
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

            # --- 2. 自動クラスタリング実行 ---
            vertical_clusters = self._vertical_stack_clustering(raw_blocks)
            final_clusters = self._orphan_absorption(vertical_clusters)

            # ソート
            def sort_key(cluster):
                x0, y0, _, _ = cluster["rect"]
                row = round(y0 / 60) * 60
                return (row, x0)
            final_clusters.sort(key=sort_key)

            # 辞書形式で整形して返す
            # GUI側で扱いやすいように ID を付与
            # ★ 座標を元の画像サイズに逆変換
            formatted_clusters = []
            for i, c in enumerate(final_clusters):
                rect = c["rect"]
                scaled_rect = [
                    int(rect[0] * inverse_ratio),
                    int(rect[1] * inverse_ratio),
                    int(rect[2] * inverse_ratio),
                    int(rect[3] * inverse_ratio)
                ]
                # デバッグ: 最初のクラスタの座標変換をログ
                if i == 0:
                    print(f"[OCR] First cluster: OCR rect={rect} → scaled rect={scaled_rect} (inverse_ratio={inverse_ratio:.3f})")
                    print(f"[OCR] original_size=({original_width}x{original_height})")
                formatted_clusters.append({
                    "id": i + 1,
                    "paragraph_id": f"P-{i+1:03d}",  # ★ Phase 3: ユニークID付与
                    "rect": scaled_rect,
                    "text": "\n".join(c["texts"])
                })

            # raw_wordsも逆変換
            scaled_raw_words = []
            for w in raw_words:
                rect = w["rect"]
                center = w["center"]
                scaled_raw_words.append({
                    "text": w["text"],
                    "rect": [
                        int(rect[0] * inverse_ratio),
                        int(rect[1] * inverse_ratio),
                        int(rect[2] * inverse_ratio),
                        int(rect[3] * inverse_ratio)
                    ],
                    "center": (center[0] * inverse_ratio, center[1] * inverse_ratio)
                })

            print(f"🔄 座標逆変換適用 (inverse_ratio: {inverse_ratio:.3f})")
            return formatted_clusters, scaled_raw_words

        except Exception as e:
            raise RuntimeError(str(e))

    # --- 以下、前回のロジック（そのまま利用） ---
    def _vertical_stack_clustering(self, blocks):
        if not blocks: return []
        blocks.sort(key=lambda b: b["rect"][1])
        
        clusters = [{
            "rect": b["rect"], 
            "texts": [b["text"]],
            "width": b["width"],
            "center_x": b["center_x"],
            "avg_font_size": b["font_size"]
        } for b in blocks]
        
        has_merged = True
        while has_merged:
            has_merged = False
            new_clusters = []
            skip_indices = set()

            for i in range(len(clusters)):
                if i in skip_indices: continue
                current = clusters[i]
                
                for j in range(i + 1, len(clusters)):
                    if j in skip_indices: continue
                    target = clusters[j]
                    
                    # 結合判定 - リサイズ後の画像座標に適用
                    x_overlap = min(current["rect"][2], target["rect"][2]) - max(current["rect"][0], target["rect"][0])
                    min_width = min(current["width"], target["width"])
                    overlap_ratio = x_overlap / min_width if min_width > 0 else 0
                    left_diff = abs(current["rect"][0] - target["rect"][0])
                    # 元の設定に戻す
                    is_aligned = overlap_ratio > 0.6 or left_diff < 30
                    
                    if not is_aligned: continue

                    gap_y = target["rect"][1] - current["rect"][3]
                    base_size = max(current["avg_font_size"], target["avg_font_size"])
                    # 元の設定に戻す
                    threshold_y = max(base_size * 2.5, 50)

                    if gap_y > threshold_y: continue
                    # 元の設定に戻す
                    if current["avg_font_size"] > target["avg_font_size"] * 2.5: continue
                    if target["avg_font_size"] > current["avg_font_size"] * 2.0: continue
                    
                    # 元の設定に戻す
                    gap_x = max(0, target["rect"][0] - current["rect"][2]) if current["rect"][0] < target["rect"][0] else max(0, current["rect"][0] - target["rect"][2])
                    if gap_x > 15: continue

                    new_rect = [
                        min(current["rect"][0], target["rect"][0]),
                        min(current["rect"][1], target["rect"][1]),
                        max(current["rect"][2], target["rect"][2]),
                        max(current["rect"][3], target["rect"][3])
                    ]
                    
                    new_texts = current["texts"] + target["texts"] if current["rect"][1] < target["rect"][1] else target["texts"] + current["texts"]
                    new_avg = max(current["avg_font_size"], target["avg_font_size"])

                    current = {
                        "rect": new_rect, "texts": new_texts,
                        "width": new_rect[2] - new_rect[0],
                        "center_x": (new_rect[0] + new_rect[2]) / 2,
                        "avg_font_size": new_avg
                    }
                    skip_indices.add(j)
                    has_merged = True
                
                new_clusters.append(current)
            clusters = new_clusters
        return clusters

    def _orphan_absorption(self, clusters):
        if not clusters: return []
        areas = [(c["rect"][2]-c["rect"][0]) * (c["rect"][3]-c["rect"][1]) for c in clusters]
        avg_area = statistics.mean(areas) if areas else 0
        orphan_threshold = avg_area * 0.1 
        
        final_clusters = []
        orphans = []
        
        for c in clusters:
            area = (c["rect"][2]-c["rect"][0]) * (c["rect"][3]-c["rect"][1])
            text_len = sum(len(t) for t in c["texts"])
            if area < orphan_threshold or text_len < 3:
                orphans.append(c)
            else:
                final_clusters.append(c)

        if not final_clusters: return clusters

        for orphan in orphans:
            best_parent = None
            min_dist = float('inf')
            r1 = orphan["rect"]
            for parent in final_clusters:
                r2 = parent["rect"]
                dx = max(0, r2[0] - r1[2]) if r1[0] < r2[0] else max(0, r1[0] - r2[2])
                dy = max(0, r2[1] - r1[3]) if r1[1] < r2[1] else max(0, r1[1] - r2[3])
                dist = dx + dy
                if dist < 200 and dist < min_dist:
                    min_dist = dist
                    best_parent = parent
            
            if best_parent:
                r_p = best_parent["rect"]
                r_o = orphan["rect"]
                best_parent["rect"] = [min(r_p[0], r_o[0]), min(r_p[1], r_o[1]), max(r_p[2], r_o[2]), max(r_p[3], r_o[3])]
                best_parent["texts"].extend(orphan["texts"])
                best_parent["width"] = best_parent["rect"][2] - best_parent["rect"][0]
                best_parent["center_x"] = (best_parent["rect"][0] + best_parent["rect"][2]) / 2
            else:
                final_clusters.append(orphan)
        return final_clusters

    def _ocr_tall_image_chunks(self, image: Image.Image):
        """
        非常に縦長の画像をチャンク分割してOCRを実行
        各チャンクの座標を元画像座標に変換して結合
        """
        from google.cloud import vision
        
        original_width = image.width
        original_height = image.height
        
        # チャンク設定
        max_chunk_height = 4000  # 各チャンクの最大高さ
        target_width = min(original_width, 1200)  # OCR用の幅
        
        # リサイズ比率
        width_scale = target_width / original_width
        scaled_height = int(original_height * width_scale)
        
        # チャンク数を計算
        num_chunks = math.ceil(scaled_height / max_chunk_height)
        chunk_height_original = math.ceil(original_height / num_chunks)
        
        print(f"📐 チャンクOCR: {num_chunks}チャンク (各{chunk_height_original}px)")
        
        all_blocks = []
        all_raw_words = []
        
        for i in range(num_chunks):
            # チャンクを切り出し
            y_start = i * chunk_height_original
            y_end = min((i + 1) * chunk_height_original, original_height)
            chunk = image.crop((0, y_start, original_width, y_end))
            
            # チャンクをリサイズ
            chunk_width = target_width
            chunk_height = int(chunk.height * width_scale)
            chunk_resized = chunk.resize((chunk_width, chunk_height), Image.Resampling.LANCZOS)
            
            # RGB変換
            if chunk_resized.mode != 'RGB':
                chunk_resized = chunk_resized.convert('RGB')
            
            # OCR実行
            img_byte_arr = io.BytesIO()
            chunk_resized.save(img_byte_arr, format='PNG')  # PNG for quality
            content = img_byte_arr.getvalue()
            
            vision_image = vision.Image(content=content)
            response = self.client.document_text_detection(image=vision_image)
            
            if response.error.message:
                print(f"⚠️ チャンク{i+1}エラー: {response.error.message}")
                continue
            
            # 座標を元画像座標に変換
            inverse_scale = 1.0 / width_scale
            y_offset = y_start  # 元画像でのチャンク開始位置
            
            for page in response.full_text_annotation.pages:
                for block in page.blocks:
                    block_text_parts = []
                    symbol_heights = []
                    
                    for paragraph in block.paragraphs:
                        for word in paragraph.words:
                            word_text = "".join([symbol.text for symbol in word.symbols])
                            block_text_parts.append(word_text)
                            
                            # raw_wordsに追加
                            wv = word.bounding_box.vertices
                            wx = [v.x for v in wv]
                            wy = [v.y for v in wv]
                            all_raw_words.append({
                                "text": word_text,
                                "rect": [
                                    int(min(wx) * inverse_scale),
                                    int(min(wy) * inverse_scale + y_offset),
                                    int(max(wx) * inverse_scale),
                                    int(max(wy) * inverse_scale + y_offset)
                                ],
                                "center": (
                                    (min(wx) + max(wx)) / 2 * inverse_scale,
                                    (min(wy) + max(wy)) / 2 * inverse_scale + y_offset
                                )
                            })
                            
                            for symbol in word.symbols:
                                v = symbol.bounding_box.vertices
                                h = v[3].y - v[0].y
                                symbol_heights.append(h)
                    
                    v = block.bounding_box.vertices
                    x_coords = [vertex.x for vertex in v]
                    y_coords = [vertex.y for vertex in v]
                    
                    all_blocks.append({
                        "text": "".join(block_text_parts),
                        "rect": [
                            int(min(x_coords) * inverse_scale),
                            int(min(y_coords) * inverse_scale + y_offset),
                            int(max(x_coords) * inverse_scale),
                            int(max(y_coords) * inverse_scale + y_offset)
                        ],
                        "center_x": (min(x_coords) + max(x_coords)) / 2 * inverse_scale,
                        "width": (max(x_coords) - min(x_coords)) * inverse_scale,
                        "font_size": statistics.mean(symbol_heights) * inverse_scale if symbol_heights else 10
                    })
            
            print(f"  チャンク{i+1}/{num_chunks}: {len(all_blocks)}ブロック検出")
        
        # クラスタリング
        vertical_clusters = self._vertical_stack_clustering(all_blocks)
        final_clusters = self._orphan_absorption(vertical_clusters)
        
        # ソート
        def sort_key(cluster):
            x0, y0, _, _ = cluster["rect"]
            row = round(y0 / 60) * 60
            return (row, x0)
        final_clusters.sort(key=sort_key)
        
        # 整形
        formatted_clusters = []
        for i, c in enumerate(final_clusters):
            formatted_clusters.append({
                "id": i + 1,
                "rect": list(map(int, c["rect"])),
                "text": "\n".join(c["texts"])
            })
        
        print(f"✅ チャンクOCR完了: {len(formatted_clusters)}クラスタ, {len(all_raw_words)}単語")
        return formatted_clusters, all_raw_words

