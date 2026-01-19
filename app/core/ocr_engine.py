"""
OCR Engine Module
Google Cloud Vision API連携エンジン
"""
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import os
import io


class OCREngine:
    """
    Google Cloud Vision APIを使用したOCRエンジン
    高精度なドキュメント認識とバウンディングボックス抽出
    """
    
    # 認証ファイルの検索パス
    CREDENTIAL_PATHS = [
        "credentials.json",
        "credentials/service_account.json",
        "../sitemap_pro/credentials/service_account.json",
        "C:/Users/raiko/OneDrive/Desktop/26/sitemap_pro/credentials/service_account.json",
    ]
    
    def __init__(self, credentials_path: str = None):
        """
        Args:
            credentials_path: Google Cloud認証情報のパス（Noneの場合は自動検索）
        """
        self.credentials_path = credentials_path or self._find_credentials()
        self.client = None
        self._is_initialized = False
    
    def _find_credentials(self) -> str:
        """認証ファイルを検索"""
        for path in self.CREDENTIAL_PATHS:
            if Path(path).exists():
                return str(Path(path).resolve())
        return "credentials.json"  # フォールバック
    
    def initialize(self) -> bool:
        """
        Vision APIクライアントを初期化
        
        Returns:
            成功した場合True
        """
        if self._is_initialized:
            return True
        
        try:
            # 認証ファイルの存在確認
            if not Path(self.credentials_path).exists():
                print(f"⚠️ 認証ファイルが見つかりません: {self.credentials_path}")
                print("📝 Google Cloudコンソールから credentials.json をダウンロードし、")
                print("   プロジェクトルートに配置してください。")
                return False
            
            from google.cloud import vision
            
            # 環境変数に認証情報を設定
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self.credentials_path
            
            # クライアント初期化
            self.client = vision.ImageAnnotatorClient()
            self._is_initialized = True
            
            print("✅ Google Cloud Vision API初期化完了")
            return True
            
        except ImportError:
            print("⚠️ google-cloud-vision がインストールされていません。")
            print("   pip install google-cloud-vision>=3.0.0 を実行してください。")
            return False
            
        except Exception as e:
            print(f"⚠️ Cloud Vision API初期化エラー: {str(e)}")
            return False
    
    def detect_document_text(self, image_path: str) -> Optional[Dict]:
        """
        画像からドキュメントテキストを検出（ブロック情報付き）
        
        Args:
            image_path: 画像ファイルのパス
        
        Returns:
            APIレスポンス辞書、失敗時None
            {
                "full_text": str,  # 全体テキスト
                "blocks": [  # ブロック情報
                    {
                        "text": str,
                        "bbox": [x0, y0, x1, y1],
                        "confidence": float,
                        "type": "BLOCK/PARAGRAPH/WORD"
                    },
                    ...
                ]
            }
        """
        # 初期化チェック
        if not self._is_initialized:
            if not self.initialize():
                return None
        
        try:
            # ファイル存在確認
            if not Path(image_path).exists():
                print(f"⚠️ 画像ファイルが見つかりません: {image_path}")
                return None
            
            # 画像を読み込み
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            from google.cloud import vision
            
            image = vision.Image(content=content)
            
            # Document Text Detection APIを呼び出し
            response = self.client.document_text_detection(image=image)
            
            if response.error.message:
                print(f"⚠️ API エラー: {response.error.message}")
                return None
            
            # レスポンスをパース
            result = self._parse_response(response)
            
            print(f"✅ OCR完了: {len(result['blocks'])} ブロック検出")
            return result
            
        except Exception as e:
            print(f"⚠️ OCR処理エラー: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _parse_response(self, response, granularity: str = "paragraph") -> Dict:
        """
        Vision APIレスポンスをパースして構造化データに変換（魔改造版）
        
        Args:
            response: Vision APIレスポンス
            granularity: 粒度 ("block", "paragraph", "word", "auto")
                - "block": ブロック単位（大きな塊）
                - "paragraph": パラグラフ単位（推奨、意味のある段落）
                - "word": 単語単位（最も細かい）
                - "auto": 自動判定（パラグラフを優先、なければブロック）
        
        Returns:
            構造化された辞書
        """
        # 全体テキスト
        full_text = response.full_text_annotation.text if response.full_text_annotation else ""
        
        areas = []
        
        # ドキュメント構造を解析
        if response.full_text_annotation:
            for page in response.full_text_annotation.pages:
                for block in page.blocks:
                    
                    if granularity in ["paragraph", "auto"]:
                        # パラグラフ単位で抽出（意味のある段落）
                        for paragraph in block.paragraphs:
                            para_text = self._extract_text_from_paragraph(paragraph)
                            
                            if not para_text.strip():
                                continue
                            
                            para_bbox = self._extract_bbox(paragraph.bounding_box)
                            para_confidence = paragraph.confidence if hasattr(paragraph, 'confidence') else 0.0
                            
                            areas.append({
                                "text": para_text,
                                "bbox": para_bbox,
                                "confidence": para_confidence,
                                "type": "PARAGRAPH"
                            })
                    
                    elif granularity == "block":
                        # ブロック単位で抽出（大きな塊）
                        block_text = self._extract_text_from_block(block)
                        
                        if not block_text.strip():
                            continue
                        
                        bbox = self._extract_bbox(block.bounding_box)
                        confidence = block.confidence if hasattr(block, 'confidence') else 0.0
                        
                        areas.append({
                            "text": block_text,
                            "bbox": bbox,
                            "confidence": confidence,
                            "type": "BLOCK"
                        })
                    
                    elif granularity == "word":
                        # 単語単位で抽出（最も細かい）
                        for paragraph in block.paragraphs:
                            for word in paragraph.words:
                                word_text = "".join([symbol.text for symbol in word.symbols])
                                
                                if not word_text.strip():
                                    continue
                                
                                word_bbox = self._extract_bbox(word.bounding_box)
                                word_confidence = word.confidence if hasattr(word, 'confidence') else 0.0
                                
                                areas.append({
                                    "text": word_text,
                                    "bbox": word_bbox,
                                    "confidence": word_confidence,
                                    "type": "WORD"
                                })
        
        print(f"📊 [OCR] Extracted {len(areas)} areas (granularity: {granularity})")
        
        return {
            "full_text": full_text,
            "blocks": areas  # 互換性のため"blocks"キーを維持
        }
    
    def _extract_text_from_block(self, block) -> str:
        """ブロックからテキストを抽出"""
        text_parts = []
        for paragraph in block.paragraphs:
            text_parts.append(self._extract_text_from_paragraph(paragraph))
        return " ".join(text_parts)
    
    def _extract_text_from_paragraph(self, paragraph) -> str:
        """パラグラフからテキストを抽出"""
        text_parts = []
        for word in paragraph.words:
            word_text = "".join([symbol.text for symbol in word.symbols])
            text_parts.append(word_text)
        return " ".join(text_parts)
    
    def _extract_bbox(self, bounding_box) -> List[int]:
        """
        バウンディングボックスを [x0, y0, x1, y1] 形式に変換
        
        Args:
            bounding_box: Vision API BoundingPoly
        
        Returns:
            [x0, y0, x1, y1]
        """
        vertices = bounding_box.vertices
        
        xs = [v.x for v in vertices]
        ys = [v.y for v in vertices]
        
        x0 = min(xs)
        y0 = min(ys)
        x1 = max(xs)
        y1 = max(ys)
        
        return [x0, y0, x1, y1]
    
    def detect_language(self, image_path: str) -> str:
        """
        画像内のテキストの言語を検出
        
        Args:
            image_path: 画像ファイルのパス
        
        Returns:
            言語コード (例: "ja", "en")
        """
        result = self.detect_document_text(image_path)
        
        if not result or not result.get("blocks"):
            return "unknown"
        
        # TODO: 実際の言語検出ロジック
        # Vision APIのレスポンスから言語情報を抽出
        return "ja"

