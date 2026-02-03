
import logging
from typing import Optional, List, Any, Tuple
from PIL import Image, ImageTk

logger = logging.getLogger(__name__)

class ThumbnailManager:
    """
    Thumbnail Generation Manager
    Encapsulates logic for creating thumbnails from Web/PDF images,
    handling both stitched global coordinates and page-aware local cropping.
    """
    
    THUMB_WIDTH = 60
    THUMB_HEIGHT = 80

    @classmethod
    def create_page_aware_thumbnail(cls, region: Any, pages_list: List[dict], 
                                  fallback_image: Image.Image) -> Optional[ImageTk.PhotoImage]:
        """
        Create thumbnail using Page-Aware logic (Region.page_id -> Specific Page Image).
        
        Args:
            region: Object with .rect (bbox) and .page_id
            pages_list: List of dicts {'image': PIL.Image, ...}
            fallback_image: Image to use if page-aware lookup fails (stitching)
            
        Returns:
            ImageTk.PhotoImage or None
        """
        if not region:
            return None
            
        bbox = getattr(region, 'rect', None)
        if not bbox:
            return None
        
        page_id = getattr(region, 'page_id', 1)
        
        # 1. Try to find specific page image
        page_image = None
        if pages_list and len(pages_list) >= page_id and page_id > 0:
            page_data = pages_list[page_id - 1]  # 0-indexed
            page_image = page_data.get('image')
        
        # 2. Fallback to stitched image
        if not page_image:
            logger.debug(f"[PageThumb] Fallback to stitch image for page {page_id}")
            page_image = fallback_image
        
        if not page_image:
            return None
            
        try:
            # 3. Use bbox as Local Crop Rect
            # AdvancedComparisonView treats region.rect as Page-Relative (Local) when page_id is set.
            # Do NOT subtract offsets.
            crop_rect = bbox
                
            logger.debug(f"[PageThumb] Page {page_id} Crop: {crop_rect}")

            return cls._crop_and_resize(page_image, crop_rect)
            
        except Exception as e:
            logger.error(f"[PageThumb] Error: {e}")
            # Fallback to simple crop on fallback_image as last resort
            if fallback_image and fallback_image != page_image:
                 return cls._crop_and_resize(fallback_image, bbox)
            return None

    @classmethod
    def create_thumbnail_from_global_bbox(cls, bbox: List[int], pages_list: List[dict], 
                                        fallback_image: Image.Image) -> Optional[ImageTk.PhotoImage]:
        """
        Create thumbnail by inferring the page from Global Stitched Coordinates (Virtual Cropping).
        Useful when region.page_id is not available.
        """
        if not bbox:
            return None
            
        target_image = fallback_image
        crop_rect = bbox
        
        try:
            # Try to find page from Global Y
            if pages_list:
                current_y = 0
                y_center = (bbox[1] + bbox[3]) / 2
                
                for i, page in enumerate(pages_list):
                    img = page.get('image')
                    if not img: continue
                    
                    next_y = current_y + img.height
                    
                    if current_y <= y_center < next_y:
                        # Found the page
                        target_image = img
                        # Global -> Local
                        local_y1 = bbox[1] - current_y
                        local_y2 = bbox[3] - current_y
                        crop_rect = (bbox[0], local_y1, bbox[2], local_y2)
                        break
                    
                    current_y = next_y
            
            return cls._crop_and_resize(target_image, crop_rect)

        except Exception as e:
            logger.error(f"[Thumb] Global Crop Error: {e}")
            return cls._crop_and_resize(fallback_image, bbox)

    @classmethod
    def create_thumbnail(cls, image: Image.Image, bbox: List[int]) -> Optional[ImageTk.PhotoImage]:
        """
        Simple thumbnail creation from a source image and bbox.
        """
        if not image or not bbox:
            return None
            
        return cls._crop_and_resize(image, bbox)

    @classmethod
    def _crop_and_resize(cls, image: Image.Image, rect: tuple) -> Optional[ImageTk.PhotoImage]:
        """Internal helper for safe cropping and resizing"""
        if not image:
            return None
            
        try:
            x1, y1, x2, y2 = rect
            x1 = max(0, int(x1))
            y1 = max(0, int(y1))
            x2 = min(image.width, int(x2))
            y2 = min(image.height, int(y2))

            if x2 <= x1 or y2 <= y1:
                return None

            cropped = image.crop((x1, y1, x2, y2))
            
            # Keep Aspect Ratio Resize
            aspect = cropped.height / cropped.width if cropped.width > 0 else 1
            if aspect > cls.THUMB_HEIGHT / cls.THUMB_WIDTH:
                new_h = cls.THUMB_HEIGHT
                new_w = max(1, int(new_h / aspect))
            else:
                new_w = cls.THUMB_WIDTH
                new_h = max(1, int(new_w * aspect))

            # Resize
            resized = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(resized)
            
        except Exception as e:
            logger.error(f"[Thumb] Crop/Resize Error: {e}")
            return None
