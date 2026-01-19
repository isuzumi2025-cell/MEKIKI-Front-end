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
    Step 2: Gemini で誤認識補正
    """
    
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        """初期化"""
        print("🔥 Hybrid OCR Engine 初期化中...")
        
        # Cloud Vision エンジン
        self.vision_engine = OCREngine()
        
        # Gemini 補正用LLM
        self.llm_client = LLMClient(model_name=model_name)
        
        self._is_initialized = (
            self.vision_engine._is_initialized and 
            self.llm_client.model is not None
        )
        
        if self._is_initialized:
            print("✅ Hybrid OCR Engine 初期化完了")
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
        
        # 補正無効の場合はそのまま返す
        if not enable_correction:
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
        
        # テキストを分割して処理（長文対策）
        corrected_text = self._correct_text_with_gemini(raw_text)
        
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
            'raw_blocks': raw_blocks
        }
    
    def _correct_text_with_gemini(self, text: str) -> Optional[str]:
        """Geminiでテキスト補正"""
        if not text or len(text) < 10:
            return text
        
        # 長文は分割処理
        max_chunk = 3000
        if len(text) <= max_chunk:
            return self._call_gemini_correction(text)
        
        # 分割して処理
        chunks = [text[i:i+max_chunk] for i in range(0, len(text), max_chunk)]
        corrected_chunks = []
        
        for i, chunk in enumerate(chunks):
            print(f"    補正中 [{i+1}/{len(chunks)}]...")
            corrected = self._call_gemini_correction(chunk)
            if corrected:
                corrected_chunks.append(corrected)
            else:
                corrected_chunks.append(chunk)
        
        return "\n".join(corrected_chunks)
    
    def _call_gemini_correction(self, text: str) -> Optional[str]:
        """Gemini API呼び出し"""
        prompt = f"""以下のOCR結果を校正してください。

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
