"""
PDF Ingestion Module
PDFからテキストレイヤー抽出 + ページ画像レンダリング

Created: 2026-01-11
"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import pdfminer.high_level
    from pdfminer.layout import LAParams, LTTextBox, LTTextLine, LTChar, LTFigure
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
    from pdfminer.converter import PDFPageAggregator
    PDFMINER_AVAILABLE = True
except ImportError:
    PDFMINER_AVAILABLE = False

try:
    import pypdfium2 as pdfium
    PYPDFIUM_AVAILABLE = True
except ImportError:
    PYPDFIUM_AVAILABLE = False


@dataclass
class TextBlock:
    """PDFテキストブロック"""
    text: str
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    page_num: int
    confidence: float = 1.0  # PDFテキストレイヤーは高信頼度
    font_size: Optional[float] = None
    font_name: Optional[str] = None


@dataclass
class PDFPageResult:
    """PDFページ結果"""
    page_num: int
    width: float
    height: float
    text_blocks: List[TextBlock] = field(default_factory=list)
    full_text: str = ""
    image_path: Optional[str] = None


@dataclass
class PDFCaptureResult:
    """PDFキャプチャ結果"""
    capture_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pdf_path: str = ""
    total_pages: int = 0
    pages: List[PDFPageResult] = field(default_factory=list)
    captured_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class PDFIngestor:
    """
    PDF取り込みクラス
    テキストレイヤー抽出 + ページ画像レンダリング
    """
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        dpi: int = 150,
        extract_text: bool = True,
        render_images: bool = True
    ):
        """
        初期化
        
        Args:
            storage_path: 画像保存先ディレクトリ
            dpi: レンダリング解像度
            extract_text: テキストレイヤーを抽出するか
            render_images: ページ画像をレンダリングするか
        """
        self.storage_path = Path(storage_path) if storage_path else Path("storage/runs")
        self.dpi = dpi
        self.extract_text = extract_text
        self.render_images = render_images
    
    def capture(
        self,
        pdf_path: str,
        run_id: Optional[str] = None,
        page_range: Optional[Tuple[int, int]] = None
    ) -> PDFCaptureResult:
        """
        PDFをキャプチャ
        
        Args:
            pdf_path: PDFファイルパス
            run_id: 実行ID
            page_range: 処理するページ範囲 (start, end) 1-indexed
            
        Returns:
            PDFCaptureResult
        """
        result = PDFCaptureResult(pdf_path=pdf_path)
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            result.error = f"PDF file not found: {pdf_path}"
            return result
        
        try:
            run_id = run_id or str(uuid.uuid4())[:8]
            save_dir = self.storage_path / run_id / "images"
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # PDFページ数取得
            if PDFMINER_AVAILABLE:
                with open(pdf_path, 'rb') as f:
                    pdf_pages = list(PDFPage.get_pages(f))
                    result.total_pages = len(pdf_pages)
            elif PYPDFIUM_AVAILABLE:
                # pypdfiumから取得
                pdf = pdfium.PdfDocument(str(pdf_path))
                result.total_pages = len(pdf)
                pdf.close()
            else:
                result.error = "No PDF library available (pdfminer or pypdfium2)"
                return result
            
            # ページ範囲
            start_page = 1
            end_page = result.total_pages
            if page_range:
                start_page, end_page = page_range
            
            # 各ページ処理
            for page_num in range(start_page, end_page + 1):
                page_result = PDFPageResult(page_num=page_num, width=0, height=0)
                
                # テキスト抽出
                if self.extract_text and PDFMINER_AVAILABLE:
                    blocks, full_text, width, height = self._extract_text_from_page(
                        pdf_path, page_num
                    )
                    page_result.text_blocks = blocks
                    page_result.full_text = full_text
                    page_result.width = width
                    page_result.height = height
                
                # 画像レンダリング
                if self.render_images and PYPDFIUM_AVAILABLE:
                    image_path = self._render_page(pdf_path, page_num, save_dir, result.capture_id)
                    page_result.image_path = image_path
                    
                    # 画像からサイズ取得（テキスト抽出しない場合）
                    if image_path and page_result.width == 0:
                        with Image.open(image_path) as img:
                            page_result.width = img.width
                            page_result.height = img.height
                
                # OCRフォールバック: テキストレイヤーが空の場合、画像からOCR
                if not page_result.text_blocks and page_result.image_path:
                    ocr_blocks = self._ocr_page(page_result.image_path, page_num)
                    if ocr_blocks:
                        page_result.text_blocks = ocr_blocks
                        page_result.full_text = "\n".join([b.text for b in ocr_blocks])
                        result.metadata["ocr_used"] = True
                
                result.pages.append(page_result)
            
            result.metadata = {
                "run_id": run_id,
                "dpi": self.dpi,
                "filename": pdf_path.name
            }
            
        except Exception as e:
            result.error = str(e)
        
        return result
    
    def _extract_text_from_page(
        self,
        pdf_path: Path,
        page_num: int
    ) -> Tuple[List[TextBlock], str, float, float]:
        """
        指定ページからテキストブロックを抽出
        
        Returns:
            (text_blocks, full_text, page_width, page_height)
        """
        blocks = []
        full_text_parts = []
        page_width = 0.0
        page_height = 0.0
        
        rsrcmgr = PDFResourceManager()
        laparams = LAParams(
            line_margin=0.5,
            word_margin=0.1,
            char_margin=2.0,
            boxes_flow=0.5,
            detect_vertical=True
        )
        device = PDFPageAggregator(rsrcmgr, laparams=laparams)
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        
        with open(pdf_path, 'rb') as f:
            for i, page in enumerate(PDFPage.get_pages(f)):
                if i + 1 != page_num:
                    continue
                
                # ページサイズ
                mediabox = page.mediabox
                page_width = mediabox[2] - mediabox[0]
                page_height = mediabox[3] - mediabox[1]
                
                interpreter.process_page(page)
                layout = device.get_result()
                
                for element in layout:
                    if isinstance(element, (LTTextBox, LTTextLine)):
                        text = element.get_text().strip()
                        if text:
                            # bbox: (x0, y0, x1, y1) - PDFは左下原点
                            # 上原点に変換
                            x0, y0, x1, y1 = element.bbox
                            y0_converted = page_height - y1
                            y1_converted = page_height - y0
                            
                            # フォントサイズ推定
                            font_size = None
                            for item in element:
                                if hasattr(item, '__iter__'):
                                    for char in item:
                                        if isinstance(char, LTChar):
                                            font_size = char.size
                                            break
                                if font_size:
                                    break
                            
                            blocks.append(TextBlock(
                                text=text,
                                bbox=(x0, y0_converted, x1, y1_converted),
                                page_num=page_num,
                                font_size=font_size
                            ))
                            full_text_parts.append(text)
                
                break
        
        return blocks, "\n".join(full_text_parts), page_width, page_height
    
    def _render_page(
        self,
        pdf_path: Path,
        page_num: int,
        save_dir: Path,
        capture_id: str
    ) -> Optional[str]:
        """
        PDFページを画像としてレンダリング
        
        Args:
            pdf_path: PDFファイルパス
            page_num: ページ番号 (1-indexed)
            save_dir: 保存先ディレクトリ
            capture_id: キャプチャID
            
        Returns:
            保存した画像のパス
        """
        try:
            pdf = pdfium.PdfDocument(str(pdf_path))
            page = pdf[page_num - 1]  # 0-indexed
            
            # DPIに応じたスケール
            scale = self.dpi / 72.0
            
            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil()
            
            # 保存
            image_name = f"pdf_{capture_id[:8]}_p{page_num:03d}.png"
            image_path = save_dir / image_name
            pil_image.save(str(image_path))
            
            pdf.close()
            
            return str(image_path)
            
        except Exception as e:
            print(f"[PDFIngestor] Render error page {page_num}: {e}")
            return None
    
    def _ocr_page(
        self,
        image_path: str,
        page_num: int
    ) -> List[TextBlock]:
        """
        ページ画像からOCRでテキストブロックを抽出
        
        Args:
            image_path: ページ画像のパス
            page_num: ページ番号
            
        Returns:
            TextBlockのリスト
        """
        try:
            # OCRエンジンをインポート（遅延インポート）
            from app.core.ocr_engine import OCREngine
            
            # OCRエンジン初期化
            ocr = OCREngine()
            if not ocr.initialize():
                print(f"[PDFIngestor] OCR初期化失敗")
                return []
            
            # OCR実行
            result = ocr.detect_document_text(image_path)
            
            if not result or not result.get("blocks"):
                print(f"[PDFIngestor] Page {page_num}: OCRブロック0")
                return []
            
            # TextBlockに変換
            text_blocks = []
            for block in result["blocks"]:
                text_blocks.append(TextBlock(
                    text=block["text"],
                    bbox=tuple(block["bbox"]),
                    page_num=page_num,
                    confidence=block.get("confidence", 0.9)
                ))
            
            print(f"[PDFIngestor] Page {page_num}: OCR成功 {len(text_blocks)} blocks")
            return text_blocks
            
        except ImportError:
            print("[PDFIngestor] OCREngine not available")
            return []
        except Exception as e:
            print(f"[PDFIngestor] OCR error page {page_num}: {e}")
            return []
    
    def extract_text_only(self, pdf_path: str) -> str:
        """
        PDFから全テキストを抽出（簡易版）
        """
        if not PDFMINER_AVAILABLE:
            raise ImportError("pdfminer.six is not installed")
        
        return pdfminer.high_level.extract_text(pdf_path)


# ========== Convenience Function ==========

def capture_pdf(
    pdf_path: str,
    run_id: Optional[str] = None,
    dpi: int = 150,
    **kwargs
) -> PDFCaptureResult:
    """
    PDFキャプチャ（簡易インターフェース）
    
    Args:
        pdf_path: PDFファイルパス
        run_id: 実行ID
        dpi: レンダリング解像度
        
    Returns:
        PDFCaptureResult
    """
    ingestor = PDFIngestor(dpi=dpi)
    return ingestor.capture(pdf_path, run_id=run_id, **kwargs)


def extract_pdf_text(pdf_path: str) -> str:
    """
    PDFからテキストのみ抽出
    """
    ingestor = PDFIngestor(render_images=False)
    return ingestor.extract_text_only(pdf_path)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python ingest_pdf.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    result = capture_pdf(pdf_path, run_id="test")
    
    print(f"Total pages: {result.total_pages}")
    print(f"Error: {result.error}")
    
    for page in result.pages:
        print(f"\n--- Page {page.page_num} ---")
        print(f"Size: {page.width} x {page.height}")
        print(f"Image: {page.image_path}")
        print(f"Text blocks: {len(page.text_blocks)}")
        print(f"Full text (first 200): {page.full_text[:200]}...")
