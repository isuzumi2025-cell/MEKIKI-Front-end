from abc import ABC, abstractmethod
from PIL import Image
from typing import Optional

class OCREngineStrategy(ABC):
    """
    全てのOCRエンジンが守るべき共通ルール（インターフェース）。
    これを作ることで、後でエンジンを増やしてもメインコードを修正しなくて済みます。
    """

    @abstractmethod
    def extract_text(self, image: Image.Image) -> str:
        """
        PIL画像を受け取り、抽出したテキストを文字列で返す。
        """
        pass

class LLMEngineStrategy(ABC):
    """
    所有的LLMエンジンが守るべき共通ルール。
    """
    
    @abstractmethod
    def generate_content(self, prompt: str) -> Optional[str]:
        """
        プロンプトを受け取り、生成されたテキストを返す。
        """
        pass
    
    @abstractmethod
    def analyze_text(self, text: str, instruction: str) -> Optional[str]:
        """
        テキストと指示を受け取り、分析結果を返す。
        """
        pass
