"""
Google Cloud Vision API によるOCR実行
"""
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image
import io

try:
    from google.cloud import vision
    from google.oauth2 import service_account
    GOOGLE_VISION_AVAILABLE = True
except ImportError:
    GOOGLE_VISION_AVAILABLE = False


def create_vision_client() -> Optional[Any]:
    """
    Google Cloud Vision API クライアントを作成
    
    Returns:
        Vision API クライアント、または None（利用不可の場合）
    """
    if not GOOGLE_VISION_AVAILABLE:
        return None
    
    # 環境変数から認証情報を取得
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    api_key = os.getenv("GOOGLE_CLOUD_API_KEY")
    
    if creds_path and Path(creds_path).exists():
        # サービスアカウントキーから認証
        credentials = service_account.Credentials.from_service_account_file(creds_path)
        client = vision.ImageAnnotatorClient(credentials=credentials)
        return client
    elif api_key:
        # APIキーから認証（簡易版）
        # 注意: APIキー方式は推奨されないが、互換性のためサポート
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = ""  # クリア
        client = vision.ImageAnnotatorClient()
        return client
    else:
        # デフォルト認証（gcloud auth application-default login など）
        try:
            client = vision.ImageAnnotatorClient()
            return client
        except Exception:
            return None


def run_ocr(image: Image.Image, feature_type: str = "DOCUMENT_TEXT_DETECTION") -> Dict[str, Any]:
    """
    Google Vision API でOCRを実行
    
    Args:
        image: PIL画像
        feature_type: "DOCUMENT_TEXT_DETECTION" または "TEXT_DETECTION"
    
    Returns:
        OCR結果の辞書（Vision API レスポンスをシリアライズ可能な形式に変換）
    """
    if not GOOGLE_VISION_AVAILABLE:
        raise RuntimeError(
            "Google Cloud Vision API が利用できません。\n"
            "pip install google-cloud-vision を実行してください。"
        )
    
    client = create_vision_client()
    if client is None:
        raise RuntimeError(
            "Google Cloud Vision API クライアントが作成できません。\n"
            "認証情報を設定してください:\n"
            "  1. 環境変数 GOOGLE_APPLICATION_CREDENTIALS にサービスアカウントキーファイルのパスを設定\n"
            "  2. または gcloud auth application-default login を実行\n"
            "  3. または環境変数 GOOGLE_CLOUD_API_KEY にAPIキーを設定"
        )
    
    # PIL画像をbytesに変換
    img_bytes = io.BytesIO()
    image.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    content = img_bytes.read()
    
    # Vision API リクエスト
    image_obj = vision.Image(content=content)
    
    if feature_type == "DOCUMENT_TEXT_DETECTION":
        feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
    else:
        feature = vision.Feature(type_=vision.Feature.Type.TEXT_DETECTION)
    
    response = client.annotate_image(
        {"image": image_obj, "features": [feature]}
    )
    
    # レスポンスを辞書に変換
    result = {
        "full_text_annotation": None,
        "text_annotations": [],
        "error": None,
    }
    
    if response.error.message:
        result["error"] = response.error.message
        return result
    
    # 全文テキスト
    if response.full_text_annotation:
        result["full_text_annotation"] = {
            "text": response.full_text_annotation.text,
            "pages": [],
        }
        
        # ページ情報
        for page in response.full_text_annotation.pages:
            page_data = {
                "width": page.width,
                "height": page.height,
                "blocks": [],
            }
            
            # ブロック情報
            for block in page.blocks:
                block_data = {
                    "bounding_box": _convert_bounding_poly(block.bounding_box),
                    "paragraphs": [],
                }
                
                # 段落情報
                for para in block.paragraphs:
                    para_data = {
                        "bounding_box": _convert_bounding_poly(para.bounding_box),
                        "words": [],
                    }
                    
                    # 単語情報
                    for word in para.words:
                        word_text = "".join([symbol.text for symbol in word.symbols])
                        word_data = {
                            "text": word_text,
                            "bounding_box": _convert_bounding_poly(word.bounding_box),
                            "confidence": word.confidence if hasattr(word, "confidence") else None,
                            "symbols": [
                                {
                                    "text": symbol.text,
                                    "bounding_box": _convert_bounding_poly(symbol.bounding_box),
                                }
                                for symbol in word.symbols
                            ],
                        }
                        para_data["words"].append(word_data)
                    
                    block_data["paragraphs"].append(para_data)
                
                page_data["blocks"].append(block_data)
            
            result["full_text_annotation"]["pages"].append(page_data)
    
    # テキストアノテーション（個別検出）
    for annotation in response.text_annotations:
        result["text_annotations"].append({
            "text": annotation.description,
            "bounding_box": _convert_bounding_poly(annotation.bounding_poly),
        })
    
    return result


def _convert_bounding_poly(bounding_poly) -> Dict[str, Any]:
    """バウンディングボックスを辞書に変換"""
    if not bounding_poly or not bounding_poly.vertices:
        return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
    
    vertices = bounding_poly.vertices
    xs = [v.x for v in vertices if hasattr(v, "x")]
    ys = [v.y for v in vertices if hasattr(v, "y")]
    
    if not xs or not ys:
        return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
    
    return {
        "x1": min(xs),
        "y1": min(ys),
        "x2": max(xs),
        "y2": max(ys),
    }



