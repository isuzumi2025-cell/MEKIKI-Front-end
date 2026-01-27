"""
ParagraphSplitter - 文字をパラグラフに分割

Phase 2.5: コンテ素材抽出ツール用のパラグラフ分割器
- セマンティックな段落認識
- レイアウト情報を活用した分割
- Gemini LLMによるインテリジェント分割オプション
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import re


@dataclass
class StoryParagraph:
    """コンテ用パラグラフ"""
    id: str
    text: str
    page_num: int
    order: int
    paragraph_type: str = "body"  # "title", "subtitle", "body", "caption", "note"
    font_size: float = 12.0
    is_bold: bool = False
    bbox: tuple = (0, 0, 0, 0)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ParagraphSplitter:
    """
    テキストをパラグラフに分割するエンジン
    
    機能:
    - 空行ベースの段落分割
    - フォントサイズによるタイトル/本文判定
    - レイアウト情報を活用した構造化
    """
    
    # 段落区切りパターン
    PARAGRAPH_BREAK = re.compile(r'\n\s*\n')
    
    # タイトルらしいパターン（短い、数字で始まる等）
    TITLE_PATTERN = re.compile(r'^(第?\d+[章節項]|[\d\.\-]+\s|【|■|●|◆|▼)')
    
    # キャプションパターン
    CAPTION_PATTERN = re.compile(r'^(図\d+|表\d+|Photo\s*\d+|画像\d+)', re.IGNORECASE)
    
    # 注釈パターン
    NOTE_PATTERN = re.compile(r'^(※|＊|\*|注[:：]|Note[:：])', re.IGNORECASE)
    
    def __init__(self, min_paragraph_length: int = 10):
        """
        Args:
            min_paragraph_length: 最小パラグラフ長（これより短いものはマージ候補）
        """
        self.min_paragraph_length = min_paragraph_length
    
    def split(
        self, 
        text: str, 
        layout_info: Optional[Dict] = None,
        page_num: int = 0
    ) -> List[StoryParagraph]:
        """
        テキストをパラグラフに分割
        
        Args:
            text: 分割対象テキスト
            layout_info: レイアウト情報（フォントサイズ等）
            page_num: ページ番号
            
        Returns:
            List[StoryParagraph]: 分割されたパラグラフリスト
        """
        if not text or not text.strip():
            return []
        
        paragraphs = []
        
        # 空行で分割
        raw_paragraphs = self.PARAGRAPH_BREAK.split(text)
        
        order = 0
        for raw_para in raw_paragraphs:
            cleaned = raw_para.strip()
            if not cleaned:
                continue
            
            # パラグラフタイプを判定
            para_type = self._detect_paragraph_type(cleaned)
            
            # フォントサイズを推定（レイアウト情報がない場合はデフォルト）
            font_size = 12.0
            is_bold = False
            if layout_info:
                font_size = layout_info.get("font_size", 12.0)
                is_bold = layout_info.get("is_bold", False)
            
            # タイトルらしければフォントサイズを大きめに
            if para_type == "title":
                font_size = max(font_size, 18.0)
                is_bold = True
            elif para_type == "subtitle":
                font_size = max(font_size, 14.0)
                is_bold = True
            
            para_id = f"P{page_num:02d}-{order:03d}"
            
            paragraphs.append(StoryParagraph(
                id=para_id,
                text=cleaned,
                page_num=page_num,
                order=order,
                paragraph_type=para_type,
                font_size=font_size,
                is_bold=is_bold
            ))
            
            order += 1
        
        return paragraphs
    
    def split_from_blocks(
        self, 
        text_blocks: List[Dict]
    ) -> List[StoryParagraph]:
        """
        TextBlockリストからパラグラフを生成
        
        Args:
            text_blocks: LayerSeparatorからのTextBlockリスト
            
        Returns:
            List[StoryParagraph]
        """
        paragraphs = []
        
        for i, block in enumerate(text_blocks):
            text = block.get("text", "") if isinstance(block, dict) else getattr(block, "text", "")
            if not text.strip():
                continue
            
            page_num = block.get("page_num", 0) if isinstance(block, dict) else getattr(block, "page_num", 0)
            font_size = block.get("font_size", 12.0) if isinstance(block, dict) else getattr(block, "font_size", 12.0)
            is_bold = block.get("is_bold", False) if isinstance(block, dict) else getattr(block, "is_bold", False)
            bbox = block.get("bbox", (0, 0, 0, 0)) if isinstance(block, dict) else getattr(block, "bbox", (0, 0, 0, 0))
            
            para_type = self._detect_paragraph_type(text)
            
            # フォントサイズからタイプを再判定
            if font_size >= 18:
                para_type = "title"
            elif font_size >= 14 and is_bold:
                para_type = "subtitle"
            
            para_id = f"P{page_num:02d}-{i:03d}"
            
            paragraphs.append(StoryParagraph(
                id=para_id,
                text=text.strip(),
                page_num=page_num,
                order=i,
                paragraph_type=para_type,
                font_size=font_size,
                is_bold=is_bold,
                bbox=bbox
            ))
        
        return paragraphs
    
    def _detect_paragraph_type(self, text: str) -> str:
        """パラグラフタイプを検出"""
        # タイトルパターンチェック
        if self.TITLE_PATTERN.match(text):
            return "title"
        
        # キャプションパターンチェック
        if self.CAPTION_PATTERN.match(text):
            return "caption"
        
        # 注釈パターンチェック
        if self.NOTE_PATTERN.match(text):
            return "note"
        
        # 短いテキストはサブタイトルの可能性
        if len(text) < 50 and text.endswith(('。', '」', '）')) is False:
            return "subtitle"
        
        return "body"
    
    def merge_short_paragraphs(
        self, 
        paragraphs: List[StoryParagraph], 
        threshold: int = None
    ) -> List[StoryParagraph]:
        """
        短いパラグラフを前後とマージ
        
        Args:
            paragraphs: パラグラフリスト
            threshold: マージ閾値（デフォルトはmin_paragraph_length）
            
        Returns:
            マージ後のパラグラフリスト
        """
        threshold = threshold or self.min_paragraph_length
        
        if len(paragraphs) <= 1:
            return paragraphs
        
        merged = []
        i = 0
        
        while i < len(paragraphs):
            current = paragraphs[i]
            
            # 短いパラグラフは次とマージを試みる
            if len(current.text) < threshold and i + 1 < len(paragraphs):
                next_para = paragraphs[i + 1]
                # 同じページなら結合
                if current.page_num == next_para.page_num:
                    merged_text = current.text + "\n" + next_para.text
                    merged_para = StoryParagraph(
                        id=current.id,
                        text=merged_text,
                        page_num=current.page_num,
                        order=current.order,
                        paragraph_type=next_para.paragraph_type,  # 後者の型を採用
                        font_size=max(current.font_size, next_para.font_size),
                        is_bold=current.is_bold or next_para.is_bold,
                        bbox=current.bbox
                    )
                    merged.append(merged_para)
                    i += 2
                    continue
            
            merged.append(current)
            i += 1
        
        return merged
