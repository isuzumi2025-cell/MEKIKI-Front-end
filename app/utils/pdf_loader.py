"""
PDF一括ローダー & グローバルマスク機能（魔改造版 v3）
指定フォルダ内の全PDFを再帰的に読み込み、マスクエリアを適用
PyMuPDF (fitz) のみを使用した高速・高品質処理（外部依存なし）
OCR精度向上のための前処理機能付き
"""
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
import fitz  # PyMuPDF
import os


class PDFLoader:
    """PDF一括ローダークラス（PyMuPDF単体・高DPI対応）"""
    
    def __init__(self, global_mask: Optional[Dict] = None, dpi: int = 300):
        """
        Args:
            global_mask: グローバルマスク {"x0": int, "y0": int, "x1": int, "y1": int}
            dpi: PDF変換時のDPI（デフォルト300、OCR精度向上のため）
        """
        self.global_mask = global_mask
        self.dpi = max(dpi, 300)  # 最低300 DPI保証
        
        # DPIからPyMuPDFのzoom係数を計算 (72dpiがデフォルト)
        self.zoom_factor = self.dpi / 72.0
        
        print(f"[PDFLoader] ✅ 初期化完了 (DPI: {self.dpi}, Zoom: {self.zoom_factor:.2f}x)")
        print(f"[PDFLoader] 📦 PyMuPDF {fitz.version} (外部依存なし)")
    
    def load_pdf(self, pdf_path: str) -> List[Dict]:
        """
        単一PDFファイルを読み込む（PyMuPDF単体・高速処理）
        
        Args:
            pdf_path: PDFファイルパス
        
        Returns:
            [{"filename": str, "page_num": int, "text": str, "image_path": str, "areas": List, "page_image": Image}, ...]
        """
        print(f"\n{'='*60}")
        print(f"[PDF] 📄 Loading file: {pdf_path}")
        print(f"[PDF] 🎯 Target DPI: {self.dpi} (Zoom: {self.zoom_factor:.2f}x)")
        print(f"{'='*60}")
        
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")
        
        results = []
        
        try:
            # PyMuPDFでPDFを開く
            doc = fitz.open(str(pdf_file))
            page_count = len(doc)
            
            print(f"[PDF] 📊 Total pages: {page_count}")
            print(f"[PDF] 🚀 Processing...")
            
            # zoom係数でマトリックスを作成
            mat = fitz.Matrix(self.zoom_factor, self.zoom_factor)
            
            for page_num in range(page_count):
                page = doc.load_page(page_num)
                
                # ステップ1: 高品質画像を生成
                pix = page.get_pixmap(matrix=mat)
                
                # PIL Imageに変換
                image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # ステップ1.5: OCR精度向上のための前処理
                image_for_ocr = self._preprocess_for_ocr(image)
                
                # ステップ2: テキスト＆bboxを抽出
                text, areas = self._extract_text_with_bbox(page, (pix.width, pix.height))
                
                results.append({
                    "filename": str(pdf_file),
                    "page_num": page_num + 1,
                    "text": text,
                    "image_path": None,  # 必要に応じて保存パスを設定
                    "areas": areas,  # bbox付きテキスト領域
                    "page_image": image_for_ocr  # PIL Image（前処理済み高品質）
                })
                
                print(f"[PDF]   ✓ Page {page_num + 1}/{page_count}: {len(text)} chars, {len(areas)} areas, {pix.width}x{pix.height}px")
            
            doc.close()
            
            print(f"\n{'='*60}")
            print(f"[PDF] ✅ Load Complete: {len(results)} pages")
            print(f"[PDF] 💾 Total chars extracted: {sum(len(r['text']) for r in results)}")
            print(f"{'='*60}\n")
                
        except Exception as e:
            print(f"\n❌ [PDF] Load Error: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
        
        return results
    
    def load_pdfs_from_folder(
        self,
        folder_path: str,
        recursive: bool = True
    ) -> List[Dict]:
        """
        フォルダ内の全PDFを読み込む
        
        Args:
            folder_path: フォルダパス
            recursive: 再帰的に検索するか
        
        Returns:
            [{"filename": str, "page_num": int, "text": str, "image_path": str}, ...]
        """
        print(f"\n{'='*60}")
        print(f"[PDF] Loading folder: {folder_path}")
        print(f"{'='*60}")
        
        folder = Path(folder_path)
        if not folder.exists():
            raise FileNotFoundError(f"フォルダが見つかりません: {folder_path}")
        
        # PDFファイルを検索
        if recursive:
            pdf_files = list(folder.rglob("*.pdf"))
        else:
            pdf_files = list(folder.glob("*.pdf"))
        
        print(f"[PDF] Found {len(pdf_files)} PDF files\n")
        
        results = []
        
        for i, pdf_file in enumerate(pdf_files, start=1):
            try:
                print(f"[PDF] Processing file {i}/{len(pdf_files)}: {pdf_file.name}")
                pages = self.load_pdf(str(pdf_file))
                results.extend(pages)
            except Exception as e:
                print(f"⚠️ PDF読み込みエラー: {pdf_file} - {str(e)}")
                continue
        
        print(f"\n{'='*60}")
        print(f"[PDF] ✅ Total pages loaded: {len(results)}")
        print(f"{'='*60}\n")
        
        return results
    
    def _extract_text_with_bbox(
        self,
        page: fitz.Page,
        image_size: Tuple[int, int]
    ) -> Tuple[str, List[Dict]]:
        """
        PyMuPDFページからテキストとbboxを抽出（マスク適用）
        
        Args:
            page: fitz.Page オブジェクト
            image_size: 生成された画像のサイズ (width, height)
        
        Returns:
            (full_text, areas)
            areas: [{"text": str, "bbox": [x0, y0, x1, y1], "area_id": int}, ...]
        """
        # PDFの実サイズ
        pdf_width = page.rect.width
        pdf_height = page.rect.height
        
        # 画像サイズへのスケール比率を計算
        scale_x = image_size[0] / pdf_width
        scale_y = image_size[1] / pdf_height
        
        # テキストブロックを抽出（bbox付き）
        areas = []
        area_id_counter = 1
        full_text_parts = []
        
        try:
            # get_text("dict")でブロック情報を取得
            text_dict = page.get_text("dict")
            blocks = text_dict.get("blocks", [])
            
            for block in blocks:
                if block.get("type") == 0:  # テキストブロック
                    bbox = block.get("bbox", [])
                    if not bbox or len(bbox) != 4:
                        continue
                    
                    x0, y0, x1, y1 = bbox
                    
                    # グローバルマスクチェック
                    if self.global_mask:
                        mask_x0 = self.global_mask.get("x0", 0)
                        mask_y0 = self.global_mask.get("y0", 0)
                        mask_x1 = self.global_mask.get("x1", pdf_width)
                        mask_y1 = self.global_mask.get("y1", pdf_height)
                        
                        # マスク範囲内なら除外
                        if (x0 >= mask_x0 and y0 >= mask_y0 and
                            x1 <= mask_x1 and y1 <= mask_y1):
                            continue
                    
                    # ブロック内のテキストを結合
                    block_text = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            block_text += span.get("text", "")
                        block_text += "\n"
                    
                    block_text = block_text.strip()
                    
                    if block_text:
                        # 画像サイズに合わせてbboxをスケーリング
                        scaled_bbox = [
                            int(x0 * scale_x),
                            int(y0 * scale_y),
                            int(x1 * scale_x),
                            int(y1 * scale_y)
                        ]
                        
                        areas.append({
                            "text": block_text,
                            "bbox": scaled_bbox,
                            "area_id": area_id_counter
                        })
                        
                        full_text_parts.append(block_text)
                        area_id_counter += 1
            
            full_text = "\n\n".join(full_text_parts)
            
            if not full_text:
                print(f"⚠️ [PDF] このページはテキストを含まない可能性があります（スキャンPDFなど）")
            
            return full_text, areas
            
        except Exception as e:
            print(f"⚠️ [PDF] テキスト抽出エラー: {str(e)}")
            import traceback
            traceback.print_exc()
            return "", []
    
    def _apply_mask(self, image: Image.Image, mask: Dict) -> Image.Image:
        """
        画像にマスク（除外矩形）を適用
        マスクエリアの文字を白で塗りつぶす
        """
        img_copy = image.copy()
        draw = ImageDraw.Draw(img_copy)
        
        x0 = mask.get("x0", 0)
        y0 = mask.get("y0", 0)
        x1 = mask.get("x1", img_copy.width)
        y1 = mask.get("y1", img_copy.height)
        
        # マスクエリアを白で塗りつぶし
        draw.rectangle([x0, y0, x1, y1], fill="white")
        
        return img_copy
    
    def set_global_mask(self, x0: int, y0: int, x1: int, y1: int):
        """グローバルマスクを設定"""
        self.global_mask = {"x0": x0, "y0": y0, "x1": x1, "y1": y1}
    
    def clear_global_mask(self):
        """グローバルマスクをクリア"""
        self.global_mask = None
    
    def _preprocess_for_ocr(self, image: Image.Image) -> Image.Image:
        """
        OCR精度向上のための画像前処理
        
        広告チラシ・デザインPDFに対応:
        1. コントラスト強調
        2. シャープネス強調
        3. ノイズ軽減
        
        Args:
            image: 元画像 (PIL Image)
        
        Returns:
            前処理済み画像
        """
        try:
            # 1. コントラスト強調 (1.3倍)
            # デザインチラシの薄い文字を読みやすく
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.3)
            
            # 2. シャープネス強調 (1.5倍)
            # 文字の輪郭をくっきりと
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.5)
            
            # 3. 軽微なノイズ除去 (MedianFilter)
            # 印刷ノイズやスキャンノイズを軽減
            image = image.filter(ImageFilter.MedianFilter(size=3))
            
            return image
            
        except Exception as e:
            print(f"⚠️ [PDF] 前処理エラー: {e}")
            return image  # エラー時は元画像をそのまま返す
