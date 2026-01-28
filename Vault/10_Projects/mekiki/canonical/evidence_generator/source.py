"""
Evidence Pack Generator
左右切り抜き + オーバーレイ + メタJSONを生成

Created: 2026-01-11
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict
import uuid

try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


@dataclass
class EvidencePack:
    """証拠パック"""
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issue_id: str = ""
    left_crop_path: Optional[str] = None
    right_crop_path: Optional[str] = None
    overlay_crop_path: Optional[str] = None
    meta_json_path: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


class EvidenceGenerator:
    """
    証拠パック生成器
    各Issueに対して視覚的根拠を生成
    """
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        margin: int = 20,
        overlay_opacity: float = 0.5
    ):
        """
        初期化
        
        Args:
            storage_path: 保存先ディレクトリ
            margin: 切り抜き時のマージン(px)
            overlay_opacity: オーバーレイの透明度
        """
        if not PIL_AVAILABLE:
            raise ImportError("PIL/Pillow is not installed")
        
        self.storage_path = Path(storage_path) if storage_path else Path("storage/runs")
        self.margin = margin
        self.overlay_opacity = overlay_opacity
    
    def generate(
        self,
        issue_id: str,
        run_id: str,
        left_image_path: Optional[str],
        right_image_path: Optional[str],
        left_bbox: Optional[Dict[str, float]],
        right_bbox: Optional[Dict[str, float]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> EvidencePack:
        """
        証拠パックを生成
        
        Args:
            issue_id: Issue ID
            run_id: 実行ID
            left_image_path: 左側画像パス
            right_image_path: 右側画像パス
            left_bbox: 左側バウンディングボックス {x1, y1, x2, y2}
            right_bbox: 右側バウンディングボックス
            metadata: 追加メタデータ
            
        Returns:
            EvidencePack
        """
        pack = EvidencePack(issue_id=issue_id)
        
        # 保存先ディレクトリ
        save_dir = self.storage_path / run_id / "evidence"
        save_dir.mkdir(parents=True, exist_ok=True)
        
        short_id = pack.evidence_id[:8]
        
        # 左側切り抜き
        if left_image_path and left_bbox:
            left_crop = self._crop_region(left_image_path, left_bbox)
            if left_crop:
                left_path = save_dir / f"left_{short_id}.png"
                left_crop.save(str(left_path))
                pack.left_crop_path = str(left_path)
        
        # 右側切り抜き
        if right_image_path and right_bbox:
            right_crop = self._crop_region(right_image_path, right_bbox)
            if right_crop:
                right_path = save_dir / f"right_{short_id}.png"
                right_crop.save(str(right_path))
                pack.right_crop_path = str(right_path)
        
        # オーバーレイ生成
        if pack.left_crop_path and pack.right_crop_path:
            overlay = self._create_overlay(
                pack.left_crop_path,
                pack.right_crop_path
            )
            if overlay:
                overlay_path = save_dir / f"overlay_{short_id}.png"
                overlay.save(str(overlay_path))
                pack.overlay_crop_path = str(overlay_path)
        
        # メタJSON
        meta = {
            "evidence_id": pack.evidence_id,
            "issue_id": issue_id,
            "run_id": run_id,
            "left_bbox": left_bbox,
            "right_bbox": right_bbox,
            "left_crop_path": pack.left_crop_path,
            "right_crop_path": pack.right_crop_path,
            "overlay_crop_path": pack.overlay_crop_path,
            "created_at": pack.created_at.isoformat(),
            **(metadata or {})
        }
        
        meta_path = save_dir / f"evidence_{short_id}.json"
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        pack.meta_json_path = str(meta_path)
        
        return pack
    
    def _crop_region(
        self,
        image_path: str,
        bbox: Dict[str, float]
    ) -> Optional[Image.Image]:
        """
        画像から領域を切り抜き
        """
        try:
            img = Image.open(image_path)
            
            # マージン適用
            x1 = max(0, int(bbox["x1"]) - self.margin)
            y1 = max(0, int(bbox["y1"]) - self.margin)
            x2 = min(img.width, int(bbox["x2"]) + self.margin)
            y2 = min(img.height, int(bbox["y2"]) + self.margin)
            
            cropped = img.crop((x1, y1, x2, y2))
            
            # ハイライト枠を描画
            draw = ImageDraw.Draw(cropped)
            draw.rectangle(
                [self.margin, self.margin, 
                 cropped.width - self.margin, cropped.height - self.margin],
                outline="red",
                width=2
            )
            
            return cropped
            
        except Exception as e:
            print(f"[EvidenceGenerator] Crop error: {e}")
            return None
    
    def _create_overlay(
        self,
        left_path: str,
        right_path: str
    ) -> Optional[Image.Image]:
        """
        2つの画像を重ねたオーバーレイを作成
        """
        try:
            left = Image.open(left_path).convert("RGBA")
            right = Image.open(right_path).convert("RGBA")
            
            # サイズを合わせる（大きい方に）
            max_width = max(left.width, right.width)
            max_height = max(left.height, right.height)
            
            # 背景を作成
            overlay = Image.new("RGBA", (max_width, max_height), (255, 255, 255, 255))
            
            # 左側（赤チャンネル強調）
            left_tinted = self._tint_image(left, (255, 100, 100))
            
            # 右側（青チャンネル強調）
            right_tinted = self._tint_image(right, (100, 100, 255))
            
            # ブレンド
            overlay.paste(left_tinted, (0, 0))
            overlay = Image.blend(overlay, right_tinted, self.overlay_opacity)
            
            return overlay.convert("RGB")
            
        except Exception as e:
            print(f"[EvidenceGenerator] Overlay error: {e}")
            return None
    
    def _tint_image(self, img: Image.Image, color: Tuple[int, int, int]) -> Image.Image:
        """画像を特定色で着色"""
        tinted = Image.new("RGBA", img.size, color + (128,))
        return Image.blend(img, tinted, 0.3)


# ========== Convenience Function ==========

def generate_evidence(
    issue_id: str,
    run_id: str,
    left_image: str,
    right_image: str,
    left_bbox: Dict[str, float],
    right_bbox: Dict[str, float],
    **kwargs
) -> EvidencePack:
    """
    証拠パック生成（簡易インターフェース）
    """
    generator = EvidenceGenerator()
    return generator.generate(
        issue_id=issue_id,
        run_id=run_id,
        left_image_path=left_image,
        right_image_path=right_image,
        left_bbox=left_bbox,
        right_bbox=right_bbox,
        **kwargs
    )
