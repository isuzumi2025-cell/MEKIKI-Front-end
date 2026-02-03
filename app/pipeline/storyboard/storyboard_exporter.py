"""
StoryboardExporter - Excel/PowerPointエクスポーター

Phase 2.5: コンテ素材抽出ツール用のエクスポーター
- アスペクト比維持機能
- 画面比率を変えずに書き出し
- Excel (openpyxl) / PowerPoint (python-pptx) 対応
"""
import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from PIL import Image

# Excel対応
try:
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

# PowerPoint対応
try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.enum.text import PP_ALIGN
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False


@dataclass
class ExportConfig:
    """エクスポート設定"""
    # アスペクト比
    aspect_ratio: Tuple[int, int] = (16, 9)
    
    # 解像度（PowerPoint用）
    slide_width_inches: float = 13.333  # 16:9 標準
    slide_height_inches: float = 7.5
    
    # Excel設定
    image_max_width: int = 400  # ピクセル
    image_max_height: int = 300
    row_height: int = 200  # ピクセル概算
    
    # フォント
    title_font_size: int = 24
    body_font_size: int = 12
    
    # カラースキーム
    header_bg_color: str = "4472C4"  # 青
    alt_row_color: str = "E2EFDA"    # 薄緑


class StoryboardExporter:
    """
    抽出素材をExcel/PowerPointに出力するエンジン
    
    機能:
    - アスペクト比維持リサイズ
    - 複数ページ対応
    - 画像埋め込み（base64/ファイル参照）
    """
    
    def __init__(self, config: ExportConfig = None):
        self.config = config or ExportConfig()
        self._temp_images: List[str] = []  # 一時ファイルパス
    
    def export_to_excel(
        self, 
        paragraphs: List[Any],
        images: List[Any],
        output_path: str,
        title: str = "Storyboard Export"
    ) -> bool:
        """
        Excelにエクスポート
        
        Args:
            paragraphs: StoryParagraphリスト
            images: ImagePartまたはImageBlockリスト
            output_path: 出力ファイルパス
            title: シートタイトル
            
        Returns:
            成功ならTrue
        """
        if not OPENPYXL_AVAILABLE:
            print("❌ openpyxl is not installed. Run: pip install openpyxl")
            return False
        
        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Storyboard"
            
            # ヘッダースタイル
            header_fill = PatternFill(start_color=self.config.header_bg_color, 
                                       end_color=self.config.header_bg_color, 
                                       fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF", size=12)
            thin_border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            
            # ヘッダー行
            headers = ["No.", "Page", "Type", "Text", "Image"]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center', vertical='center')
                cell.border = thin_border
            
            # カラム幅設定
            ws.column_dimensions['A'].width = 8   # No.
            ws.column_dimensions['B'].width = 8   # Page
            ws.column_dimensions['C'].width = 12  # Type
            ws.column_dimensions['D'].width = 60  # Text
            ws.column_dimensions['E'].width = 50  # Image
            
            # データ行
            row = 2
            alt_fill = PatternFill(start_color=self.config.alt_row_color,
                                   end_color=self.config.alt_row_color,
                                   fill_type="solid")
            
            # パラグラフを書き込み
            for i, para in enumerate(paragraphs):
                para_id = getattr(para, 'id', f"P{i:03d}")
                page_num = getattr(para, 'page_num', 0) + 1
                para_type = getattr(para, 'paragraph_type', 'body')
                text = getattr(para, 'text', str(para))
                
                ws.cell(row=row, column=1, value=i + 1)
                ws.cell(row=row, column=2, value=page_num)
                ws.cell(row=row, column=3, value=para_type)
                
                text_cell = ws.cell(row=row, column=4, value=text)
                text_cell.alignment = Alignment(wrap_text=True, vertical='top')
                
                # 交互色
                if row % 2 == 0:
                    for col in range(1, 6):
                        ws.cell(row=row, column=col).fill = alt_fill
                
                # ボーダー
                for col in range(1, 6):
                    ws.cell(row=row, column=col).border = thin_border
                
                # 行高さ（テキスト量に応じて調整）
                line_count = max(1, text.count('\n') + 1)
                ws.row_dimensions[row].height = min(200, 20 + line_count * 15)
                
                row += 1
            
            # 画像シートを追加
            if images:
                ws_img = wb.create_sheet(title="Images")
                self._write_images_sheet(ws_img, images)
            
            # 保存
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            wb.save(output_path)
            print(f"✅ Excel exported: {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Excel export failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            self._cleanup_temp_images()
    
    def _write_images_sheet(self, ws, images: List[Any]):
        """画像シートに画像を書き込み"""
        headers = ["No.", "Label", "Size", "Preview"]
        header_fill = PatternFill(start_color=self.config.header_bg_color,
                                   end_color=self.config.header_bg_color,
                                   fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
        
        ws.column_dimensions['A'].width = 8
        ws.column_dimensions['B'].width = 20
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 60
        
        row = 2
        for i, img_obj in enumerate(images):
            img = getattr(img_obj, 'image', img_obj) if hasattr(img_obj, 'image') else img_obj
            label = getattr(img_obj, 'label', f"Image {i+1}")
            
            if isinstance(img, Image.Image):
                size_str = f"{img.width}x{img.height}"
                
                ws.cell(row=row, column=1, value=i + 1)
                ws.cell(row=row, column=2, value=label)
                ws.cell(row=row, column=3, value=size_str)
                
                # 画像をリサイズして埋め込み
                try:
                    resized = self._resize_for_excel(img)
                    temp_path = self._save_temp_image(resized, f"img_{i}")
                    
                    xl_img = XLImage(temp_path)
                    ws.add_image(xl_img, f"D{row}")
                    ws.row_dimensions[row].height = resized.height * 0.75
                    
                except Exception as e:
                    ws.cell(row=row, column=4, value=f"(Error: {e})")
                
                row += 1
    
    def _resize_for_excel(self, image: Image.Image) -> Image.Image:
        """Excel用にアスペクト比を維持してリサイズ（ImageSegmentを使用）"""
        max_w = self.config.image_max_width
        max_h = self.config.image_max_height
        
        # まずサイズをチェック
        w, h = image.size
        ratio = min(max_w / w, max_h / h)
        
        if ratio >= 1:
            return image  # リサイズ不要
        
        try:
            from app.sdk.core.segment import ImageSegment
            # max_long_edgeを計算（短い方を基準に）
            max_long_edge = max(max_w, max_h)
            segment = ImageSegment.from_image(image, max_long_edge=max_long_edge)
            return segment.resized_image if segment.resized_image else image
        except ImportError:
            # フォールバック: 従来のリサイズ
            new_w = int(w * ratio)
            new_h = int(h * ratio)
            return image.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    def export_to_pptx(
        self, 
        paragraphs: List[Any],
        images: List[Any],
        output_path: str,
        title: str = "Storyboard"
    ) -> bool:
        """
        PowerPointにエクスポート
        
        Args:
            paragraphs: StoryParagraphリスト
            images: ImagePartまたはImageBlockリスト
            output_path: 出力ファイルパス
            title: プレゼンテーションタイトル
            
        Returns:
            成功ならTrue
        """
        if not PPTX_AVAILABLE:
            print("❌ python-pptx is not installed. Run: pip install python-pptx")
            return False
        
        try:
            prs = Presentation()
            
            # スライドサイズ設定 (16:9)
            prs.slide_width = Inches(self.config.slide_width_inches)
            prs.slide_height = Inches(self.config.slide_height_inches)
            
            # タイトルスライド
            title_slide_layout = prs.slide_layouts[0]
            slide = prs.slides.add_slide(title_slide_layout)
            slide.shapes.title.text = title
            
            if len(slide.placeholders) > 1:
                subtitle = slide.placeholders[1]
                subtitle.text = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            # コンテンツスライド（パラグラフ + 画像）
            content_layout = prs.slide_layouts[5]  # 空のレイアウト
            
            # ページごとにグループ化
            pages = {}
            for para in paragraphs:
                page_num = getattr(para, 'page_num', 0)
                if page_num not in pages:
                    pages[page_num] = {'paragraphs': [], 'images': []}
                pages[page_num]['paragraphs'].append(para)
            
            for img_obj in images:
                page_num = getattr(img_obj, 'page_num', 0)
                if page_num not in pages:
                    pages[page_num] = {'paragraphs': [], 'images': []}
                pages[page_num]['images'].append(img_obj)
            
            # 各ページをスライドとして出力
            for page_num in sorted(pages.keys()):
                page_data = pages[page_num]
                slide = prs.slides.add_slide(content_layout)
                
                # ページタイトル
                title_box = slide.shapes.add_textbox(
                    Inches(0.5), Inches(0.3), Inches(12), Inches(0.5)
                )
                title_frame = title_box.text_frame
                title_frame.text = f"Page {page_num + 1}"
                title_frame.paragraphs[0].font.size = Pt(24)
                title_frame.paragraphs[0].font.bold = True
                
                # テキストエリア（左半分）
                text_top = 1.0
                for para in page_data['paragraphs']:
                    text = getattr(para, 'text', str(para))
                    para_type = getattr(para, 'paragraph_type', 'body')
                    
                    text_box = slide.shapes.add_textbox(
                        Inches(0.5), Inches(text_top), Inches(6), Inches(1)
                    )
                    tf = text_box.text_frame
                    tf.word_wrap = True
                    
                    p = tf.paragraphs[0]
                    p.text = text[:500]  # 長すぎる場合は切り詰め
                    
                    if para_type == "title":
                        p.font.size = Pt(18)
                        p.font.bold = True
                    elif para_type == "subtitle":
                        p.font.size = Pt(14)
                        p.font.bold = True
                    else:
                        p.font.size = Pt(11)
                    
                    text_top += 0.8
                    if text_top > 6.5:
                        break
                
                # 画像エリア（右半分）
                img_top = 1.0
                for img_obj in page_data['images'][:3]:  # 最大3枚
                    img = getattr(img_obj, 'image', img_obj)
                    if isinstance(img, Image.Image):
                        try:
                            temp_path = self._save_temp_image(img, f"pptx_img_{page_num}")
                            
                            # アスペクト比維持で配置
                            max_w = 5.5
                            max_h = 2.0
                            ratio = min(max_w / (img.width / 96), max_h / (img.height / 96))
                            
                            slide.shapes.add_picture(
                                temp_path,
                                Inches(7), Inches(img_top),
                                width=Inches(min(max_w, img.width / 96 * ratio))
                            )
                            img_top += 2.2
                            
                        except Exception as e:
                            print(f"⚠️ Image insert failed: {e}")
            
            # 保存
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            prs.save(output_path)
            print(f"✅ PowerPoint exported: {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ PowerPoint export failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            self._cleanup_temp_images()
    
    def _save_temp_image(self, image: Image.Image, prefix: str) -> str:
        """一時ファイルに画像を保存"""
        import tempfile
        
        fd, path = tempfile.mkstemp(suffix=".png", prefix=f"{prefix}_")
        os.close(fd)
        
        image.save(path, "PNG")
        self._temp_images.append(path)
        
        return path
    
    def _cleanup_temp_images(self):
        """一時ファイルを削除"""
        for path in self._temp_images:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
        self._temp_images = []
