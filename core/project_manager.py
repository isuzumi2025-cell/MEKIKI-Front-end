"""
プロジェクト管理クラス
WebページリストとPDFページリストを管理し、マッチング結果を保持
"""
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import json
from pathlib import Path


@dataclass
class TextArea:
    """テキスト領域のデータ構造（bbox付き）"""
    text: str
    bbox: List[float]  # [x0, y0, x1, y1]
    area_id: Optional[int] = None


@dataclass
class WebPage:
    """Webページのデータ構造"""
    url: str
    title: str
    text: str
    screenshot_path: Optional[str] = None
    page_id: Optional[int] = None  # 内部ID
    areas: Optional[List[TextArea]] = None  # テキスト領域リスト
    screenshot_image: Optional[object] = None  # PIL Image (シリアライズ時は除外)
    error: Optional[str] = None  # エラーメッセージ（取得失敗時）


@dataclass
class PDFPage:
    """PDFページのデータ構造"""
    filename: str
    page_num: int
    text: str
    image_path: Optional[str] = None
    page_id: Optional[int] = None  # 内部ID
    areas: Optional[List[TextArea]] = None  # テキスト領域リスト
    page_image: Optional[object] = None  # PIL Image (シリアライズ時は除外)


@dataclass
class MatchPair:
    """マッチングペアのデータ構造"""
    web_id: int
    pdf_id: int
    score: float
    web_url: Optional[str] = None
    pdf_filename: Optional[str] = None
    pdf_page_num: Optional[int] = None


class ProjectManager:
    """プロジェクト管理クラス"""
    
    def __init__(self, project_name: str = "default_project"):
        self.project_name = project_name
        self.web_pages: List[WebPage] = []
        self.pdf_pages: List[PDFPage] = []
        self.pairs: List[MatchPair] = []
        self.global_mask: Optional[Dict] = None  # {"x0": int, "y0": int, "x1": int, "y1": int}
        self._web_id_counter = 0
        self._pdf_id_counter = 0
    
    def add_web_page(self, url: str, title: str, text: str, screenshot_path: Optional[str] = None, areas: Optional[List[TextArea]] = None, screenshot_image=None, error: Optional[str] = None) -> int:
        """Webページを追加し、IDを返す"""
        page = WebPage(
            url=url,
            title=title,
            text=text,
            screenshot_path=screenshot_path,
            page_id=self._web_id_counter,
            areas=areas,
            screenshot_image=screenshot_image,
            error=error
        )
        self.web_pages.append(page)
        self._web_id_counter += 1
        return page.page_id
    
    def add_pdf_page(self, filename: str, page_num: int, text: str, image_path: Optional[str] = None, areas: Optional[List[TextArea]] = None, page_image=None) -> int:
        """PDFページを追加し、IDを返す"""
        page = PDFPage(
            filename=filename,
            page_num=page_num,
            text=text,
            image_path=image_path,
            page_id=self._pdf_id_counter,
            areas=areas,
            page_image=page_image
        )
        self.pdf_pages.append(page)
        self._pdf_id_counter += 1
        return page.page_id
    
    def add_match_pair(self, web_id: int, pdf_id: int, score: float):
        """マッチングペアを追加"""
        web_page = self.get_web_page_by_id(web_id)
        pdf_page = self.get_pdf_page_by_id(pdf_id)
        
        pair = MatchPair(
            web_id=web_id,
            pdf_id=pdf_id,
            score=score,
            web_url=web_page.url if web_page else None,
            pdf_filename=pdf_page.filename if pdf_page else None,
            pdf_page_num=pdf_page.page_num if pdf_page else None
        )
        self.pairs.append(pair)
    
    def get_web_page_by_id(self, page_id: int) -> Optional[WebPage]:
        """IDでWebページを取得"""
        for page in self.web_pages:
            if page.page_id == page_id:
                return page
        return None
    
    def get_pdf_page_by_id(self, page_id: int) -> Optional[PDFPage]:
        """IDでPDFページを取得"""
        for page in self.pdf_pages:
            if page.page_id == page_id:
                return page
        return None
    
    def set_global_mask(self, x0: int, y0: int, x1: int, y1: int):
        """グローバルマスク（除外矩形）を設定"""
        self.global_mask = {"x0": x0, "y0": y0, "x1": x1, "y1": y1}
    
    def clear_global_mask(self):
        """グローバルマスクをクリア"""
        self.global_mask = None
    
    def clear_all(self):
        """すべてのデータをクリア"""
        self.web_pages.clear()
        self.pdf_pages.clear()
        self.pairs.clear()
        self._web_id_counter = 0
        self._pdf_id_counter = 0
        self.global_mask = None
    
    def save_project(self, filepath: str):
        """プロジェクトをJSONファイルに保存"""
        data = {
            "project_name": self.project_name,
            "web_pages": [asdict(page) for page in self.web_pages],
            "pdf_pages": [asdict(page) for page in self.pdf_pages],
            "pairs": [asdict(pair) for pair in self.pairs],
            "global_mask": self.global_mask
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_project(self, filepath: str):
        """プロジェクトをJSONファイルから読み込み"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.project_name = data.get("project_name", "default_project")
        self.global_mask = data.get("global_mask")
        
        # Webページを復元
        self.web_pages = []
        for wp_data in data.get("web_pages", []):
            page = WebPage(**wp_data)
            self.web_pages.append(page)
            if page.page_id is not None and page.page_id >= self._web_id_counter:
                self._web_id_counter = page.page_id + 1
        
        # PDFページを復元
        self.pdf_pages = []
        for pdf_data in data.get("pdf_pages", []):
            page = PDFPage(**pdf_data)
            self.pdf_pages.append(page)
            if page.page_id is not None and page.page_id >= self._pdf_id_counter:
                self._pdf_id_counter = page.page_id + 1
        
        # ペアを復元
        self.pairs = []
        for pair_data in data.get("pairs", []):
            pair = MatchPair(**pair_data)
            self.pairs.append(pair)
    
    def get_statistics(self) -> Dict:
        """プロジェクトの統計情報を取得"""
        return {
            "web_pages_count": len(self.web_pages),
            "pdf_pages_count": len(self.pdf_pages),
            "pairs_count": len(self.pairs),
            "has_global_mask": self.global_mask is not None
        }

