"""
PDF Paragraph Detector (Multi-Column Aware)
広告チラシ向け精確パラグラフ検出

Features:
- マルチカラム（2段組み、3段組み）対応
- 行間距離ベースのパラグラフ分割
- 見出し・本文の区別
- Vision API OCR フォールバック
"""
import fitz  # PyMuPDF
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from PIL import Image
import io


@dataclass
class TextBlock:
    """テキストブロック情報"""
    text: str
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    font_size: float = 12.0
    is_heading: bool = False
    column: int = 0  # 0=左、1=右、etc.


@dataclass
class Paragraph:
    """パラグラフ情報"""
    id: str
    text: str
    bbox: List[int]  # [x0, y0, x1, y1]
    page: int = 1
    column: int = 0
    is_heading: bool = False
    line_count: int = 1
    
    @property
    def preview(self) -> str:
        """50文字プレビュー"""
        return self.text[:50] + "..." if len(self.text) > 50 else self.text


class ParagraphDetector:
    """
    マルチカラム対応パラグラフ検出器
    
    広告チラシの複雑なレイアウトを解析し、
    読み順序を考慮したパラグラフ抽出を行う
    """
    
    def __init__(
        self,
        min_paragraph_chars: int = 10,
        line_height_threshold: float = 1.5,
        heading_size_ratio: float = 1.2,
        column_gap_threshold: float = 0.1  # ページ幅の10%
    ):
        """
        Args:
            min_paragraph_chars: 最小パラグラフ文字数
            line_height_threshold: 行間距離閾値（通常行高の倍数）
            heading_size_ratio: 見出し判定フォントサイズ比
            column_gap_threshold: カラム間隙閾値（ページ幅比）
        """
        self.min_chars = min_paragraph_chars
        self.line_threshold = line_height_threshold
        self.heading_ratio = heading_size_ratio
        self.column_gap = column_gap_threshold
    
    def detect_from_pdf(self, pdf_path: str, page_num: int = 0) -> List[Paragraph]:
        """
        PDFページからパラグラフを検出
        
        Args:
            pdf_path: PDFファイルパス
            page_num: ページ番号（0始まり）
        
        Returns:
            パラグラフのリスト（読み順でソート済み）
        """
        doc = fitz.open(pdf_path)
        if page_num >= len(doc):
            doc.close()
            return []
        
        page = doc.load_page(page_num)
        
        # Step 1: テキストブロックを抽出
        blocks = self._extract_text_blocks(page)
        
        if not blocks:
            # 埋め込みテキストなし → OCRフォールバック
            doc.close()
            return self._fallback_to_ocr(pdf_path, page_num)
        
        # Step 2: カラムを検出
        columns = self._detect_columns(blocks, page.rect.width)
        
        # Step 3: 各カラム内でパラグラフを構築
        paragraphs = []
        for col_idx, col_blocks in enumerate(columns):
            col_paragraphs = self._build_paragraphs(col_blocks, col_idx, page_num + 1)
            paragraphs.extend(col_paragraphs)
        
        doc.close()
        
        # 読み順でソート（カラム順 → Y座標順）
        paragraphs.sort(key=lambda p: (p.column, p.bbox[1]))
        
        return paragraphs
    
    def _extract_text_blocks(self, page: fitz.Page) -> List[TextBlock]:
        """PyMuPDFからテキストブロックを抽出"""
        blocks = []
        text_dict = page.get_text("dict")
        
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # テキストブロックのみ
                continue
            
            bbox = block.get("bbox", [])
            if len(bbox) != 4:
                continue
            
            # ブロック内のテキストとフォントサイズを取得
            block_text = ""
            font_sizes = []
            
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    block_text += span.get("text", "")
                    if "size" in span:
                        font_sizes.append(span["size"])
                block_text += "\n"
            
            block_text = block_text.strip()
            if not block_text or len(block_text) < self.min_chars:
                continue
            
            avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12.0
            
            blocks.append(TextBlock(
                text=block_text,
                bbox=tuple(bbox),
                font_size=avg_font_size
            ))
        
        return blocks
    
    def _detect_columns(
        self, 
        blocks: List[TextBlock], 
        page_width: float
    ) -> List[List[TextBlock]]:
        """
        カラム（段組み）を検出
        
        X座標のクラスタリングでカラムを判定
        """
        if not blocks:
            return []
        
        # X座標の中央値でソート
        blocks_with_center = [(b, (b.bbox[0] + b.bbox[2]) / 2) for b in blocks]
        blocks_with_center.sort(key=lambda x: x[1])
        
        # カラムの境界を検出
        gap_threshold = page_width * self.column_gap
        columns = [[]]
        
        prev_right = 0
        for block, center_x in blocks_with_center:
            if columns[-1]:
                # 前のブロックとのギャップをチェック
                prev_block = columns[-1][-1]
                gap = block.bbox[0] - prev_block.bbox[2]
                
                # 大きなギャップ = 新しいカラム
                if gap > gap_threshold and center_x > page_width * 0.4:
                    columns.append([])
            
            columns[-1].append(block)
        
        # 各カラム内でY座標でソート
        for col in columns:
            col.sort(key=lambda b: b.bbox[1])
        
        # カラムインデックスを設定
        for col_idx, col_blocks in enumerate(columns):
            for block in col_blocks:
                block.column = col_idx
        
        return columns
    
    def _build_paragraphs(
        self, 
        blocks: List[TextBlock],
        column_idx: int,
        page_num: int
    ) -> List[Paragraph]:
        """
        テキストブロックからパラグラフを構築
        
        隣接するブロックをマージしてパラグラフにする
        """
        if not blocks:
            return []
        
        # 平均フォントサイズを計算（見出し判定用）
        avg_size = sum(b.font_size for b in blocks) / len(blocks)
        
        paragraphs = []
        para_id = 1
        
        for block in blocks:
            is_heading = block.font_size > avg_size * self.heading_ratio
            
            paragraphs.append(Paragraph(
                id=f"p{page_num}_{column_idx}_{para_id}",
                text=block.text,
                bbox=[int(x) for x in block.bbox],
                page=page_num,
                column=column_idx,
                is_heading=is_heading,
                line_count=block.text.count("\n") + 1
            ))
            para_id += 1
        
        return paragraphs
    
    def _fallback_to_ocr(self, pdf_path: str, page_num: int) -> List[Paragraph]:
        """
        埋め込みテキストがない場合のOCRフォールバック
        """
        try:
            from app.core.ocr_engine import OCREngine
        except ImportError:
            print("⚠️ OCREngine not available")
            return []
        
        # PDFページを画像に変換
        doc = fitz.open(pdf_path)
        page = doc.load_page(page_num)
        
        zoom = 2.0  # 高解像度
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        # PIL Imageに変換
        img_data = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_data))
        
        # 一時ファイルに保存してOCR
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            image.save(f.name)
            temp_path = f.name
        
        try:
            engine = OCREngine()
            if not engine.initialize():
                return []
            
            result = engine.detect_document_text(temp_path)
            if not result:
                return []
            
            # OCR結果をパラグラフに変換
            paragraphs = []
            for i, block in enumerate(result.get("blocks", []), 1):
                text = block.get("text", "").strip()
                bbox = block.get("bbox", [0, 0, 0, 0])
                
                if len(text) >= self.min_chars:
                    paragraphs.append(Paragraph(
                        id=f"ocr_{page_num + 1}_{i}",
                        text=text,
                        bbox=bbox,
                        page=page_num + 1
                    ))
            
            return paragraphs
            
        finally:
            import os
            os.unlink(temp_path)
            doc.close()
    
    def detect_from_image(self, image_path: str) -> List[Paragraph]:
        """
        画像からパラグラフを検出（OCR使用、マルチカラム対応）

        大きな画像は自動的にリサイズしてからOCRに送信
        (Vision API制限: 10MB, 推奨長辺: 4096px以下)
        """
        import tempfile
        import os

        try:
            from app.core.ocr_engine import OCREngine
        except ImportError:
            print("⚠️ OCREngine not available")
            return []

        engine = OCREngine()
        if not engine.initialize():
            return []

        # 画像サイズチェック & リサイズ
        ocr_path = image_path
        scale_factor = 1.0
        temp_resized_path = None

        try:
            img = Image.open(image_path)
            orig_width, orig_height = img.size
            long_edge = max(orig_width, orig_height)

            MAX_LONG_EDGE = 4096

            if long_edge > MAX_LONG_EDGE:
                # リサイズが必要
                scale_factor = MAX_LONG_EDGE / long_edge
                new_width = int(orig_width * scale_factor)
                new_height = int(orig_height * scale_factor)

                print(f"📐 画像リサイズ: {orig_width}x{orig_height} → {new_width}x{new_height} (scale: {scale_factor:.3f})")

                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # 一時ファイルに保存
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    resized_img.save(f.name, "PNG", optimize=True)
                    temp_resized_path = f.name
                    ocr_path = temp_resized_path

                resized_img.close()

            img.close()

        except Exception as e:
            print(f"⚠️ 画像読み込みエラー: {e}")
            # エラー時はそのままOCRを試行

        try:
            result = engine.detect_document_text(ocr_path)
        finally:
            # 一時ファイル削除
            if temp_resized_path and os.path.exists(temp_resized_path):
                os.unlink(temp_resized_path)

        if not result:
            return []

        # OCR結果をTextBlockに変換（座標をスケール復元）
        # 注: min_charsフィルタはマージ後に適用（短いブロックもマージ対象）
        blocks = []
        for block in result.get("blocks", []):
            text = block.get("text", "").strip()
            bbox = block.get("bbox", [0, 0, 0, 0])

            if text:  # 空でなければ全て取得
                # リサイズした場合は座標を元のスケールに戻す
                if scale_factor != 1.0:
                    bbox = [
                        bbox[0] / scale_factor,
                        bbox[1] / scale_factor,
                        bbox[2] / scale_factor,
                        bbox[3] / scale_factor
                    ]

                blocks.append(TextBlock(
                    text=text,
                    bbox=tuple(bbox),
                    font_size=12.0  # OCRではフォントサイズ不明
                ))

        if not blocks:
            return []

        # 画像幅を推定（全ブロックの最大x1座標）
        image_width = max(b.bbox[2] for b in blocks)

        # カラム検出
        columns = self._detect_columns_for_image(blocks, image_width)

        # 各カラム内でブロックをマージ
        merged_columns = []
        for col_idx, col_blocks in enumerate(columns):
            if col_blocks:
                merged = self._merge_ocr_blocks(
                    col_blocks,
                    same_line_threshold=50.0,
                    paragraph_gap_threshold=100.0
                )
                merged_columns.append(merged)
            else:
                merged_columns.append([])

        # パラグラフを構築（min_charsフィルタ適用）
        paragraphs = []
        for col_idx, col_blocks in enumerate(merged_columns):
            para_idx = 1
            for block in col_blocks:
                # マージ後にmin_charsフィルタを適用
                if len(block.text) >= self.min_chars:
                    paragraphs.append(Paragraph(
                        id=f"img_{col_idx}_{para_idx}",
                        text=block.text,
                        bbox=[int(x) for x in block.bbox],
                        page=1,
                        column=col_idx,
                        line_count=block.text.count("\n") + 1
                    ))
                    para_idx += 1

        # 読み順でソート（カラム順 → Y座標順）
        paragraphs.sort(key=lambda p: (p.column, p.bbox[1]))

        return paragraphs

    def _merge_ocr_blocks(
        self,
        blocks: List[TextBlock],
        same_line_threshold: float = 50.0,
        paragraph_gap_threshold: float = 100.0
    ) -> List[TextBlock]:
        """
        OCRの短いテキストブロックを位置ベースでマージして長文パラグラフを形成

        Args:
            blocks: OCRから取得したテキストブロック
            same_line_threshold: 同一行と判定するY座標差 (px)
            paragraph_gap_threshold: 新パラグラフとする行間ギャップ (px)

        Returns:
            マージ後のTextBlockリスト
        """
        if not blocks:
            return []

        # Y座標でソート
        sorted_blocks = sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))

        # Step 1: 同一行のブロックをグループ化
        lines: List[List[TextBlock]] = []
        current_line: List[TextBlock] = []
        current_line_y = None

        for block in sorted_blocks:
            block_y = (block.bbox[1] + block.bbox[3]) / 2  # Y中心

            if current_line_y is None:
                # 最初のブロック
                current_line = [block]
                current_line_y = block_y
            elif abs(block_y - current_line_y) <= same_line_threshold:
                # 同一行
                current_line.append(block)
            else:
                # 新しい行
                if current_line:
                    # X座標でソートして行を確定
                    current_line.sort(key=lambda b: b.bbox[0])
                    lines.append(current_line)
                current_line = [block]
                current_line_y = block_y

        # 最後の行を追加
        if current_line:
            current_line.sort(key=lambda b: b.bbox[0])
            lines.append(current_line)

        if not lines:
            return []

        # Step 2: 行をパラグラフにマージ
        merged_blocks: List[TextBlock] = []
        para_lines: List[List[TextBlock]] = []
        prev_line_bottom = None

        for line in lines:
            line_top = min(b.bbox[1] for b in line)
            line_bottom = max(b.bbox[3] for b in line)

            if prev_line_bottom is None:
                # 最初の行
                para_lines = [line]
            elif line_top - prev_line_bottom <= paragraph_gap_threshold:
                # 同一パラグラフ（ギャップが小さい）
                para_lines.append(line)
            else:
                # 新しいパラグラフ（ギャップが大きい）
                if para_lines:
                    merged_blocks.append(self._create_merged_block(para_lines))
                para_lines = [line]

            prev_line_bottom = line_bottom

        # 最後のパラグラフを追加
        if para_lines:
            merged_blocks.append(self._create_merged_block(para_lines))

        print(f"📦 ブロックマージ: {len(blocks)} → {len(merged_blocks)} パラグラフ")

        return merged_blocks

    def _create_merged_block(self, lines: List[List[TextBlock]]) -> TextBlock:
        """
        複数行のブロックを1つのTextBlockにマージ

        Args:
            lines: 行ごとにグループ化されたブロックのリスト

        Returns:
            マージされたTextBlock
        """
        all_blocks = [b for line in lines for b in line]

        # 包含する最小矩形を計算
        x0 = min(b.bbox[0] for b in all_blocks)
        y0 = min(b.bbox[1] for b in all_blocks)
        x1 = max(b.bbox[2] for b in all_blocks)
        y1 = max(b.bbox[3] for b in all_blocks)

        # テキストを連結（行内はスペース、行間は改行）
        line_texts = []
        for line in lines:
            line_text = " ".join(b.text for b in line)
            line_texts.append(line_text)

        merged_text = "\n".join(line_texts)

        # 平均フォントサイズ
        avg_font_size = sum(b.font_size for b in all_blocks) / len(all_blocks)

        return TextBlock(
            text=merged_text,
            bbox=(x0, y0, x1, y1),
            font_size=avg_font_size,
            is_heading=any(b.is_heading for b in all_blocks),
            column=all_blocks[0].column
        )

    def _detect_columns_for_image(
        self,
        blocks: List[TextBlock],
        image_width: float
    ) -> List[List[TextBlock]]:
        """
        OCR結果からカラムを検出（X座標クラスタリング）

        シンプルな2分割: 画像中央より左か右かで判定
        """
        if not blocks:
            return []

        # 各ブロックの中心X座標を計算
        center_x_threshold = image_width / 2

        left_blocks = []
        right_blocks = []

        for block in blocks:
            center_x = (block.bbox[0] + block.bbox[2]) / 2

            if center_x < center_x_threshold:
                block.column = 0
                left_blocks.append(block)
            else:
                block.column = 1
                right_blocks.append(block)

        # 各カラム内でY座標順にソート
        left_blocks.sort(key=lambda b: b.bbox[1])
        right_blocks.sort(key=lambda b: b.bbox[1])

        # 右カラムが空なら1カラムとして返す
        if not right_blocks:
            return [left_blocks]

        return [left_blocks, right_blocks]


# テスト用
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python paragraph_detector.py <pdf_or_image_path>")
        sys.exit(1)
    
    path = sys.argv[1]
    detector = ParagraphDetector()
    
    if path.lower().endswith(".pdf"):
        paragraphs = detector.detect_from_pdf(path)
    else:
        paragraphs = detector.detect_from_image(path)
    
    print(f"\n📄 Detected {len(paragraphs)} paragraphs:\n")
    for p in paragraphs:
        print(f"[{p.id}] Column:{p.column} {'📌 HEADING' if p.is_heading else ''}")
        print(f"   {p.preview}")
        print()
