"""
Hybrid OCR Engine
Cloud Vision API + Gemini 補正によるハイブリッドOCR
最高精度を実現する魔改造エンジン
"""
from typing import Optional, Dict, Any, List
from PIL import Image

from app.core.ocr_engine import OCREngine
from app.core.llm_client import LLMClient


class HybridOCREngine:
    """
    ハイブリッドOCRエンジン
    Step 1: Cloud Vision API で高精度BBox付きOCR
    Step 2: Gemini で誤認識補正 (FASTモードではスキップ)
    
    環境変数:
        MEKIKI_FAST_OCR=1: Gemini補正をスキップして高速化
    """
    
    def __init__(self, model_name: str = "gemini-2.0-flash", fast_mode: bool = None):
        """初期化
        
        Args:
            model_name: Geminiモデル名
            fast_mode: True=Gemini補正スキップ, None=環境変数に従う
        """
        import os
        print("🔥 Hybrid OCR Engine 初期化中...")
        
        # FASTモード判定
        if fast_mode is None:
            fast_mode = os.getenv("MEKIKI_FAST_OCR", "0") == "1"
        self.fast_mode = fast_mode
        
        if fast_mode:
            print("  ⚡ FASTモード: Gemini補正スキップ")
        
        # Cloud Vision エンジン（明示的に初期化）
        self.vision_engine = OCREngine()
        vision_ok = self.vision_engine.initialize()  # ★ 明示的初期化
        
        # Gemini 補正用LLM (FASTモードでは初期化スキップ)
        if not fast_mode:
            self.llm_client = LLMClient(model_name=model_name)
            llm_ok = self.llm_client.model is not None
        else:
            self.llm_client = None
            llm_ok = True  # FASTモードではLLM不要
        
        self._is_initialized = vision_ok and llm_ok
        
        if self._is_initialized:
            mode_str = " (FASTモード)" if fast_mode else ""
            print(f"✅ Hybrid OCR Engine 初期化完了{mode_str}")
        else:
            print("⚠️ Hybrid OCR Engine 初期化失敗")
    
    def detect_document_text(
        self, 
        image_source: Any,
        enable_correction: bool = True
    ) -> Optional[Dict]:
        """
        ハイブリッドOCR実行
        
        Args:
            image_source: 画像パス または PIL.Image
            enable_correction: Gemini補正を有効にするか
            
        Returns:
            dict: {
                'full_text': str,
                'corrected_text': str (補正後),
                'blocks': list,
                'raw_blocks': list (補正前)
            }
        """
        if not self._is_initialized:
            print("⚠️ Hybrid OCR Engine が初期化されていません")
            return None
        
        # 画像パスを取得
        if isinstance(image_source, Image.Image):
            # PIL Imageの場合は一時ファイルに保存
            import tempfile
            import os
            temp_path = os.path.join(tempfile.gettempdir(), "hybrid_ocr_temp.png")
            image_source.save(temp_path)
            image_path = temp_path
        else:
            image_path = str(image_source)
        
        print(f"🔥 Hybrid OCR 処理開始: {image_path[:60]}...")
        
        # ========================================
        # Step 1: Cloud Vision OCR
        # ========================================
        print("  [Step 1/2] Cloud Vision API OCR...")
        vision_result = self.vision_engine.detect_document_text(image_path)
        
        if not vision_result:
            print("  ❌ Cloud Vision OCR 失敗")
            return None
        
        raw_text = vision_result.get('full_text', '')
        raw_blocks = vision_result.get('blocks', [])
        
        print(f"  ✅ Cloud Vision: {len(raw_text)} 文字, {len(raw_blocks)} ブロック")
        
        # 補正無効またはFASTモードの場合はそのまま返す
        if not enable_correction or self.fast_mode:
            if self.fast_mode:
                print("  ⚡ FASTモード: Gemini補正スキップ - 完了!")
            return {
                'full_text': raw_text,
                'corrected_text': raw_text,
                'blocks': raw_blocks,
                'raw_blocks': raw_blocks
            }
        
        # ========================================
        # Step 2: Gemini 補正
        # ========================================
        print("  [Step 2/2] Gemini 補正中...")
        
        # ★ Context Injection: レイアウトスケルトン生成
        layout_context = self._generate_layout_skeleton(raw_blocks)
        
        # テキストを分割して処理（長文対策）
        corrected_text = self._correct_text_with_gemini(raw_text, layout_context)
        
        if corrected_text:
            print(f"  ✅ Gemini補正完了: {len(corrected_text)} 文字")
        else:
            print("  ⚠️ Gemini補正失敗 - 元テキストを使用")
            corrected_text = raw_text
        
        # ブロック内のテキストも補正
        corrected_blocks = self._correct_blocks(raw_blocks, raw_text, corrected_text)
        
        return {
            'full_text': raw_text,
            'corrected_text': corrected_text,
            'blocks': corrected_blocks,
            'raw_blocks': raw_blocks,
            'layout_context': layout_context  # デバッグ用に保持
        }

    def detect_pages_parallel(self, pages: List[Dict], enable_correction: bool = True) -> Dict:
        """
        複数ページを並列OCR処理し、結果を結合して返す (Orchestra Async Pipeline)
        
        Args:
            pages: [{'image': PIL.Image}, ...] のリスト
            enable_correction: Gemini補正を行うか
            
        Returns:
            統合されたOCR結果 (full_text, blocks等)
        """
        import concurrent.futures
        
        if not pages:
            return None
            
        print(f"🚀 Async Pipeline: {len(pages)}ページを並列処理中...")
        
        results = [None] * len(pages)
        
        # ThreadPoolExecutorで並列実行
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(pages), 8)) as executor:
            # 各ページに対して detect_document_text を実行
            # 注意: ここで渡す画像は「単一ページ」なので、座標はページ相対になる
            future_to_idx = {
                executor.submit(self.detect_document_text, page['image'], enable_correction): i 
                for i, page in enumerate(pages)
                if page.get('image')
            }
            
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                    print(f"  ✅ Page {idx+1} 完了")
                except Exception as e:
                    print(f"  ❌ Page {idx+1} エラー: {e}")
        
        # 結果の統合 (Stitch座標系への変換)
        full_text_parts = []
        raw_blocks_combined = []
        blocks_combined = []
        
        current_y_offset = 0
        
        for i, res in enumerate(results):
            if not res: 
                # 画像サイズからオフセット計算だけ必要だが、画像がない場合はスキップ
                if pages[i].get('image'):
                    current_y_offset += pages[i]['image'].height
                continue
                
            page_image = pages[i]['image']
            
            # テキスト統合
            if res.get('full_text'):
                full_text_parts.append(res['full_text'])
                
            # ブロック座標変換 (Page Relative -> Global Stitched)
            # raw_blocks
            for block in res.get('raw_blocks', []):
                new_block = block.copy()
                rect = block['rect']
                new_block['rect'] = [rect[0], rect[1] + current_y_offset, rect[2], rect[3] + current_y_offset]
                new_block['page_index'] = i # メタデータ追加
                raw_blocks_combined.append(new_block)
                
            # blocks (Corrected)
            for block in res.get('blocks', []):
                new_block = block.copy()
                rect = block['rect']
                new_block['rect'] = [rect[0], rect[1] + current_y_offset, rect[2], rect[3] + current_y_offset]
                new_block['page_index'] = i
                blocks_combined.append(new_block)
                
            current_y_offset += page_image.height
            
        # 最終結果構築
        combined_text = "\n\n".join(full_text_parts)
        
        # 全体に対するGemini補正 (Optional: ページ単位で補正済みなら不要だが、
        # ページをまたぐ文脈補正が必要ならここで行う。
        # 今回は「ページ単位並列」で補正も済ませているため、結合のみで返す)
        
        return {
            'full_text': combined_text,
            'corrected_text': combined_text, # 個別補正済みテキストの結合
            'blocks': blocks_combined,
            'raw_blocks': raw_blocks_combined,
            'layout_context': "Async Combined"
        }
        """レイアウト構造のスケルトンを生成（幻覚防止用）"""
        if not blocks:
            return "レイアウト情報なし"
            
        skeleton = ["【ページレイアウト構造】"]
        
        # Y座標でソート
        sorted_blocks = sorted(blocks, key=lambda b: (b['rect'][1], b['rect'][0]))
        
        # 主要ブロックの概略を抽出（トークン節約のため最大20ブロック）
        for i, block in enumerate(sorted_blocks[:20]):
            rect = block['rect']
            # ブロックの代表テキスト（最初の20文字）
            text_preview = block['text'][:20].replace('\n', '') 
            if len(block['text']) > 20:
                text_preview += "..."
                
            # 位置情報のヒント
            skeleton.append(f"- Block {i+1} [y={rect[1]}]: {text_preview}")
            
        if len(blocks) > 20:
            skeleton.append(f"... 他 {len(blocks)-20} ブロック")
            
        return "\n".join(skeleton)
    
    def _correct_text_with_gemini(self, text: str, layout_context: str = "") -> Optional[str]:
        """Geminiでテキスト補正（並列処理対応 + コンテキスト認識）"""
        if not text or len(text) < 10:
            return text
        
        # 長文は分割処理
        max_chunk = 3000
        if len(text) <= max_chunk:
            return self._call_gemini_correction(text, layout_context)
        
        # 分割して並列処理
        chunks = [text[i:i+max_chunk] for i in range(0, len(text), max_chunk)]
        
        # 並列処理を試みる
        try:
            import concurrent.futures
            
            print(f"    🚀 並列処理モード: {len(chunks)} チャンク")
            
            # ThreadPoolExecutorで並列実行
            # 注意: layout_contextは全チャンクに渡すが、トークン課金に注意
            # ここでは「レイアウト崩れ防止」が最優先のため渡す
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(chunks), 4)) as executor:
                futures = {executor.submit(self._call_gemini_correction, chunk, layout_context): i 
                          for i, chunk in enumerate(chunks)}
                
                corrected_chunks = [None] * len(chunks)
                for future in concurrent.futures.as_completed(futures):
                    idx = futures[future]
                    try:
                        result = future.result()
                        corrected_chunks[idx] = result if result else chunks[idx]
                    except Exception as e:
                        print(f"    ⚠️ チャンク{idx}エラー: {e}")
                        corrected_chunks[idx] = chunks[idx]
            
            print(f"    ✅ 並列処理完了")
            return "\n".join(corrected_chunks)
            
        except Exception as e:
            print(f"    ⚠️ 並列処理失敗、直列処理にフォールバック: {e}")
            # フォールバック: 直列処理
            corrected_chunks = []
            for i, chunk in enumerate(chunks):
                print(f"    補正中 [{i+1}/{len(chunks)}]...")
                corrected = self._call_gemini_correction(chunk, layout_context)
                if corrected:
                    corrected_chunks.append(corrected)
                else:
                    corrected_chunks.append(chunk)
            
            return "\n".join(corrected_chunks)
    
    def _call_gemini_correction(self, text: str, layout_context: str = "") -> Optional[str]:
        """Gemini API呼び出し (Layout-Aware)"""
        if not text: return None
        
        prompt = f"""以下のOCR結果を校正してください。

【コンテキスト情報（レイアウト構造）】
{layout_context}
※この構造を参考に、離れたブロックのテキストを無理に結合しないでください。

【指示】
1. 明らかな誤認識を修正してください（例: 「豐」→「豊」、「會」→「倉」）
2. 日本語として不自然な文字を正しい文字に修正してください
3. 段落構造と改行はそのまま維持してください
4. 補正後のテキストのみを出力してください（説明は不要）

【OCR結果】
{text}

【補正後】"""
        
        try:
            result = self.llm_client.generate_content(prompt)
            return result.strip() if result else None
        except Exception as e:
            print(f"    ⚠️ Gemini補正エラー: {e}")
            return None
    
    def _correct_blocks(
        self, 
        blocks: List[Dict], 
        original_text: str, 
        corrected_text: str
    ) -> List[Dict]:
        """ブロック内のテキストを補正（簡易マッピング）"""
        # 簡易的な置換マップを作成
        # 本格的な実装では文字単位のアライメントが必要
        
        corrected_blocks = []
        for block in blocks:
            new_block = block.copy()
            block_text = block.get('text', '')
            
            # 簡易的な補正（同じ位置の文字を置換）
            # TODO: より高度なアライメント実装
            new_block['original_text'] = block_text
            
            corrected_blocks.append(new_block)
        
        return corrected_blocks
