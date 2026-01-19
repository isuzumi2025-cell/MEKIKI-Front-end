import pytesseract
import re
from PIL import Image
from app.core.interface import OCREngineStrategy

# Windowsパス設定 (必要に応じてコメントアウトを外す)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class LocalOCREngine(OCREngineStrategy):
    """
    Tesseract OCR (ノイズ除去フィルター付き)
    """
    
    def extract_text(self, image: Image.Image) -> str:
        try:
            # 1. OCR実行 (PSM 11で隅々まで拾う)
            custom_config = r'--oem 3 --psm 11' 
            raw_text = pytesseract.image_to_string(image, lang='jpn+eng', config=custom_config)
            
            # 2. ゴミ掃除ロジック
            lines = raw_text.split('\n')
            clean_lines = []
            
            for line in lines:
                text = line.strip()
                if not text:
                    continue

                # --- フィルター条件 ---
                
                # A. 日本語（ひらがな・カタカナ・漢字）が1文字でも入っていれば「採用」
                if re.search(r'[ぁ-んァ-ン一-龥]', text):
                    clean_lines.append(text)
                    continue

                # B. 日本語がない場合、英数字の「ゴミ」かどうか判定
                # 文字数が3文字以下、かつ「年号やJR」などの重要単語っぽくなければ「不採用」
                if len(text) <= 3:
                    # 例外的に残したい単語があればここに追加 (例: JR, 1F など)
                    if text in ['JR', 'HP']:
                        clean_lines.append(text)
                    continue
                
                # C. 記号だらけの行は「不採用」 (例: "[|] ...")
                # 英数字の割合が極端に低い場合など
                if re.match(r'^[!-/:-@[-`{-~ ]+$', text):
                    continue

                # それ以外（ある程度長い英語や数字列）は「採用」
                clean_lines.append(text)

            return '\n'.join(clean_lines)

        except Exception as e:
            raise RuntimeError(f"Tesseract OCR Error: {e}")
