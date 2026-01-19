"""
Data Manager Module
データ管理エンジン - プロジェクトの保存/読み込み、永続化
"""
from typing import List, Dict, Optional
from pathlib import Path
import json
from datetime import datetime


class DataManager:
    """
    データ管理エンジン
    プロジェクトの保存、読み込み、永続化
    """
    
    def __init__(self, storage_path: str = "data_storage/projects"):
        """
        Args:
            storage_path: データ保存先ディレクトリ
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def save_project(
        self,
        project_name: str,
        web_pages: List[Dict],
        pdf_pages: List[Dict],
        pairs: List[Dict],
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        プロジェクトを保存
        
        Args:
            project_name: プロジェクト名
            web_pages: Webページデータ
            pdf_pages: PDFページデータ
            pairs: ペアリングデータ
            metadata: メタデータ
        
        Returns:
            成功した場合True
        """
        try:
            # プロジェクトディレクトリを作成
            project_dir = self.storage_path / project_name
            project_dir.mkdir(exist_ok=True)
            
            # データを保存
            data = {
                "project_name": project_name,
                "created_at": datetime.now().isoformat(),
                "web_pages": web_pages,
                "pdf_pages": pdf_pages,
                "pairs": pairs,
                "metadata": metadata or {}
            }
            
            # JSONファイルに書き込み
            json_path = project_dir / "project_data.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ プロジェクト保存完了: {project_name}")
            return True
            
        except Exception as e:
            print(f"⚠️ プロジェクト保存エラー: {str(e)}")
            return False
    
    def load_project(self, project_name: str) -> Optional[Dict]:
        """
        プロジェクトを読み込み
        
        Args:
            project_name: プロジェクト名
        
        Returns:
            プロジェクトデータ、失敗時None
        """
        try:
            json_path = self.storage_path / project_name / "project_data.json"
            
            if not json_path.exists():
                print(f"⚠️ プロジェクトが見つかりません: {project_name}")
                return None
            
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"✅ プロジェクト読み込み完了: {project_name}")
            return data
            
        except Exception as e:
            print(f"⚠️ プロジェクト読み込みエラー: {str(e)}")
            return None
    
    def list_projects(self) -> List[str]:
        """
        保存されているプロジェクト一覧を取得
        
        Returns:
            プロジェクト名のリスト
        """
        try:
            projects = []
            for item in self.storage_path.iterdir():
                if item.is_dir() and (item / "project_data.json").exists():
                    projects.append(item.name)
            return sorted(projects)
        except Exception as e:
            print(f"⚠️ プロジェクト一覧取得エラー: {str(e)}")
            return []
    
    def delete_project(self, project_name: str) -> bool:
        """
        プロジェクトを削除
        
        Args:
            project_name: プロジェクト名
        
        Returns:
            成功した場合True
        """
        try:
            project_dir = self.storage_path / project_name
            
            if not project_dir.exists():
                print(f"⚠️ プロジェクトが見つかりません: {project_name}")
                return False
            
            # ディレクトリごと削除
            import shutil
            shutil.rmtree(project_dir)
            
            print(f"✅ プロジェクト削除完了: {project_name}")
            return True
            
        except Exception as e:
            print(f"⚠️ プロジェクト削除エラー: {str(e)}")
            return False

