import os
import json
import shutil
from PIL import Image

class ProjectHandler:
    """
    プロジェクト（画像とエリア情報）の保存と読み込みを行うクラス
    """
    
    @staticmethod
    def save_project(directory, image_path, clusters):
        """
        指定したディレクトリに画像とJSONデータを保存する
        """
        if not os.path.exists(directory):
            os.makedirs(directory)
            
        # 1. 画像のコピー保存
        # 元画像ファイル名を取得
        filename = os.path.basename(image_path)
        dest_image_path = os.path.join(directory, filename)
        shutil.copy2(image_path, dest_image_path)
        
        # 2. データのJSON保存
        # rectなどのタプルはJSON化できないのでリストに変換
        serializable_clusters = []
        for c in clusters:
            serializable_clusters.append({
                "rect": list(map(int, c["rect"])),
                "text": c["text"],
                "id": c.get("id", 0)
            })
            
        data = {
            "image_filename": filename,
            "clusters": serializable_clusters
        }
        
        json_path = os.path.join(directory, "project_data.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        return dest_image_path

    @staticmethod
    def load_project(directory):
        """
        ディレクトリから画像パスとエリアデータを読み込む
        """
        json_path = os.path.join(directory, "project_data.json")
        if not os.path.exists(json_path):
            raise FileNotFoundError("プロジェクトデータ(project_data.json)が見つかりません")
            
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        image_filename = data["image_filename"]
        image_path = os.path.join(directory, image_filename)
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"画像ファイル({image_filename})が見つかりません")
            
        return image_path, data["clusters"]