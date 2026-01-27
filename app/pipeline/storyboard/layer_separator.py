"""
LayerSeparator - PDFレイヤー分離エンジン

Phase 2.5: NotebookLM等で生成されたPDFから
テキストと画像を分離抽出する

レイヤー構成:
1. 文字情報 (埋め込みテキスト + OCR)
2. 画像 (ベクター + ラスター)
3. メタデータ (ページ番号、位置情報)
"""
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from PIL import Image

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("⚠️ PyMuPDF not available. Install with: pip install PyMuPDF")


@dataclass
class TextBlock:
    """テキストブロック"""
    text: str
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    page_num: int
    font_name: str = ""
    font_size: float = 0.0
    is_bold: bool = False
    is_italic: bool = False


@dataclass
class ImageBlock:
    """画像ブロック"""
    image: Image.Image
    bbox: Tuple[float, float, float, float]
    page_num: int
    image_index: int
    original_width: int = 0
    original_height: int = 0
    xref: int = 0  # PyMuPDF内部参照


@dataclass
class TextLayer:
    """テキストレイヤー"""
    blocks: List[TextBlock] = field(default_factory=list)
    full_text: str = ""


@dataclass
class ImageLayer:
    """画像レイヤー"""
    blocks: List[ImageBlock] = field(default_factory=list)


@dataclass
class LayerResult:
    """レイヤー分離結果"""
    text_layer: TextLayer
    image_layer: ImageLayer
    page_count: int
    source_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class LayerSeparator:
    """
    PDFからテキストと画像を分離抽出するエンジン
    
    機能:
    - PyMuPDFによる高精度テキスト抽出
    - 埋め込み画像の抽出
    - フォント情報の取得
    - MEKIKIのGemini OCRによるフォールバック
    """
    
    def __init__(self, use_ocr_fallback: bool = True, force_ocr: bool = False):
        """
        Args:
            use_ocr_fallback: 埋め込みテキストがない場合にOCRを使用するか
            force_ocr: 常にOCRを使用するか（画像ベースPDF用）
        """
        self.use_ocr_fallback = use_ocr_fallback
        self.force_ocr = force_ocr
        self._ocr_engine = None
    
    def extract_layers(self, pdf_path: str) -> LayerResult:
        """
        PDFからレイヤーを抽出
        
        Args:
            pdf_path: PDFファイルパス
            
        Returns:
            LayerResult: 分離されたレイヤー
        """
        if not PYMUPDF_AVAILABLE:
            raise RuntimeError("PyMuPDF is required for layer separation")
        
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        text_blocks: List[TextBlock] = []
        image_blocks: List[ImageBlock] = []
        full_text_parts: List[str] = []
        
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        
        # force_ocrがFalseの場合のみ埋め込みテキストを抽出
        if not self.force_ocr:
            for page_num, page in enumerate(doc):
                # テキスト抽出
                page_text_blocks = self._extract_text_from_page(page, page_num)
                text_blocks.extend(page_text_blocks)
                
                # ページのフルテキスト
                page_text = page.get_text("text")
                if page_text.strip():
                    full_text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
        
        # 画像抽出は常に実行
        for page_num, page in enumerate(doc):
            page_images = self._extract_images_from_page(page, page_num)
            image_blocks.extend(page_images)
        
        doc.close()
        
        # OCR実行判定: force_ocrがTrue、または埋め込みテキストがない場合
        should_run_ocr = self.force_ocr or (not text_blocks and self.use_ocr_fallback)
        
        if should_run_ocr:
            print("🔍 OCR実行中... (MEKIKI GeminiOCREngine)")
            ocr_blocks, ocr_text = self._apply_ocr_with_mekiki(pdf_path, page_count)
            if ocr_blocks:
                text_blocks = ocr_blocks  # OCR結果で上書き
            if ocr_text:
                full_text_parts = [ocr_text]
        
        return LayerResult(
            text_layer=TextLayer(
                blocks=text_blocks,
                full_text="\n".join(full_text_parts)
            ),
            image_layer=ImageLayer(blocks=image_blocks),
            page_count=page_count,
            source_path=pdf_path,
            metadata={
                "text_block_count": len(text_blocks),
                "image_count": len(image_blocks),
                "has_embedded_text": not should_run_ocr,
                "used_ocr": should_run_ocr
            }
        )
    
    def _extract_text_from_page(self, page, page_num: int) -> List[TextBlock]:
        """ページからテキストブロックを抽出"""
        blocks = []
        
        # dict形式で詳細なテキスト情報を取得
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # テキストブロックのみ
                continue
            
            block_text_parts = []
            font_name = ""
            font_size = 0.0
            
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        block_text_parts.append(text)
                        if not font_name:
                            font_name = span.get("font", "")
                            font_size = span.get("size", 0.0)
            
            if block_text_parts:
                bbox = block.get("bbox", (0, 0, 0, 0))
                blocks.append(TextBlock(
                    text=" ".join(block_text_parts),
                    bbox=tuple(bbox),
                    page_num=page_num,
                    font_name=font_name,
                    font_size=font_size,
                    is_bold="Bold" in font_name or "bold" in font_name,
                    is_italic="Italic" in font_name or "italic" in font_name
                ))
        
        return blocks
    
    def _extract_images_from_page(self, page, page_num: int) -> List[ImageBlock]:
        """ページから画像を抽出"""
        images = []
        image_list = page.get_images(full=True)
        
        for img_index, img_info in enumerate(image_list):
            try:
                xref = img_info[0]
                base_image = page.parent.extract_image(xref)
                
                if not base_image:
                    continue
                
                image_bytes = base_image.get("image")
                if not image_bytes:
                    continue
                
                # PIL Imageに変換
                pil_image = Image.open(io.BytesIO(image_bytes))
                
                # 画像のbboxを取得（近似）
                # PyMuPDFでは画像の正確な位置取得が複雑なため、
                # ページ内の相対位置として扱う
                rect = page.rect
                bbox = (0, 0, rect.width, rect.height)
                
                images.append(ImageBlock(
                    image=pil_image,
                    bbox=bbox,
                    page_num=page_num,
                    image_index=img_index,
                    original_width=pil_image.width,
                    original_height=pil_image.height,
                    xref=xref
                ))
                
            except Exception as e:
                print(f"⚠️ Image extraction failed (page {page_num}, index {img_index}): {e}")
                continue
        
        return images
    
    def _apply_ocr_with_mekiki(
        self, 
        pdf_path: str, 
        page_count: int
    ) -> Tuple[List[TextBlock], str]:
        """MEKIKI SDK のGeminiOCREngineを使用してOCRを実行（MEKIKIと同じパターン）"""
        try:
            # MEKIKI SDK の OCR エンジンをインポート
            try:
                from app.sdk.ocr import GeminiOCREngine
                print("📦 Using MEKIKI SDK GeminiOCREngine")
            except ImportError:
                from app.core.gemini_ocr import GeminiOCREngine
                print("📦 Using app.core GeminiOCREngine (fallback)")
            
            # PDFをページ画像に変換してOCR
            doc = fitz.open(pdf_path)
            text_blocks = []
            full_text_parts = []
            
            for page_num, page in enumerate(doc):
                print(f"🔍 OCR Processing page {page_num + 1}/{page_count}...")
                
                # ページを画像としてレンダリング (最適解像度)
                mat = fitz.Matrix(1.5, 1.5)  # 1.5x scale (OCRに最適、処理速度2-3倍向上)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                pil_image = Image.open(io.BytesIO(img_data))
                
                # MEKIKIと同じパターン: 毎回新しいエンジンインスタンス
                engine = GeminiOCREngine(model="gemini-2.0-flash")
                result = engine.detect_document_text(pil_image)
                
                if result and result.get("blocks"):
                    for block in result["blocks"]:
                        bbox = block.get("bbox", [0, 0, 100, 100])
                        text = block.get("text", "").strip()
                        if text:
                            text_blocks.append(TextBlock(
                                text=text,
                                bbox=tuple(bbox),
                                page_num=page_num,
                                font_name="OCR-Gemini",
                                font_size=12.0
                            ))
                    
                    if result.get("full_text"):
                        full_text_parts.append(f"--- Page {page_num + 1} (OCR) ---\n{result['full_text']}")
                        print(f"✅ Page {page_num + 1}: {len(result['blocks'])} blocks extracted")
                else:
                    print(f"⚠️ Page {page_num + 1}: No text found")
            
            doc.close()
            print(f"✅ OCR完了: 合計 {len(text_blocks)} ブロック")
            return text_blocks, "\n".join(full_text_parts)
            
        except Exception as e:
            import traceback
            print(f"⚠️ OCR failed: {e}")
            traceback.print_exc()
            return [], ""
    
    def render_page_as_image(self, pdf_path: str, page_num: int, scale: float = 1.5) -> Optional[Image.Image]:
        """
        PDFページを画像としてレンダリング

        Args:
            pdf_path: PDFファイルパス
            page_num: ページ番号（0始まり）
            scale: 拡大率 (デフォルト1.5x: OCRに最適)

        Returns:
            PIL Image or None
        """
        if not PYMUPDF_AVAILABLE:
            return None
        
        try:
            doc = fitz.open(pdf_path)
            if page_num >= len(doc):
                doc.close()
                return None
            
            page = doc[page_num]
            mat = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            doc.close()
            
            return Image.open(io.BytesIO(img_data))
            
        except Exception as e:
            print(f"❌ Page render failed: {e}")
            return None
