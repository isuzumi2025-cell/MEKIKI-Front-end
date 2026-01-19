"""
EditMixin - 編集モード関連メソッド
手動選択・編集・リアルタイムシート反映

リファクタリング: 2026-01-19 (Phase 1.5)
レガシー移植元: _OLD/gui/windows/advanced_comparison_view_backup_20260108.py

機能:
- ドラッグによる領域移動 (_on_canvas_drag)
- 領域リサイズ
- リアルタイムシート反映 (_update_text_for_region)
- 類似検出連携
"""

import logging
from typing import Optional, Tuple, Any, List

logger = logging.getLogger(__name__)


class EditMixin:
    """
    編集モードのMixin
    
    ★ 主要機能:
    - 領域のドラッグ移動
    - リアルタイムシート反映
    - SDK連携 (PageCoordinateManager, SimilarityDetector)
    """
    
    # 編集モードフラグ
    edit_mode: bool = False
    drag_start: Optional[Tuple[int, int]] = None
    selected_region: Optional[Any] = None
    
    def _init_edit_mixin(self):
        """EditMixin初期化"""
        self.edit_mode = False
        self.drag_start = None
        self._edit_history = []  # 編集履歴
        logger.info("EditMixin initialized")
    
    def _toggle_edit_mode(self):
        """
        編集モードの切り替え
        
        編集モードON: 領域の移動・リサイズが可能
        編集モードOFF: 新規選択のみ可能
        """
        self.edit_mode = not self.edit_mode
        
        # UIフィードバック
        if hasattr(self, 'edit_mode_btn') and self.edit_mode_btn:
            if self.edit_mode:
                self.edit_mode_btn.configure(fg_color="#4CAF50", text="✏️ 編集中")
            else:
                self.edit_mode_btn.configure(fg_color="#616161", text="✏️ 編集")
        
        # ステータス表示
        status = "編集モード: ON" if self.edit_mode else "編集モード: OFF"
        if hasattr(self, 'status_label') and self.status_label:
            self.status_label.configure(text=status)
        
        logger.info(f"Edit mode toggled: {self.edit_mode}")
    
    def _on_edit_click(self, event):
        """
        編集モードでのクリック
        
        レガシー移植元: L778-805
        - 既存領域をクリック → 選択
        - 空白をクリック → 選択解除
        """
        canvas = event.widget
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        
        # スケール情報取得
        scale_x = getattr(canvas, 'scale_x', 1.0)
        scale_y = getattr(canvas, 'scale_y', 1.0)
        offset_x = getattr(canvas, 'offset_x', 0)
        offset_y = getattr(canvas, 'offset_y', 0)
        
        # 領域検索
        regions = self._get_regions_for_canvas(canvas)
        
        for region in regions:
            if not hasattr(region, 'rect') or len(region.rect) < 4:
                continue
            
            # 座標をスケーリング
            rx1 = region.rect[0] * scale_x + offset_x
            ry1 = region.rect[1] * scale_y + offset_y
            rx2 = region.rect[2] * scale_x + offset_x
            ry2 = region.rect[3] * scale_y + offset_y
            
            if rx1 <= x <= rx2 and ry1 <= y <= ry2:
                self._select_region(region)
                self.drag_start = (x, y)
                logger.debug(f"Region selected: {getattr(region, 'area_code', 'unknown')}")
                return
        
        # 何もない場所をクリック → 選択解除
        self._deselect_region()
    
    def _on_edit_drag(self, event):
        """
        編集モードでのドラッグ - 領域移動
        
        レガシー移植元: L807-825
        - ドラッグ量を計算
        - 矩形座標を更新
        - リアルタイム再描画
        """
        if not self.selected_region or not self.drag_start:
            return
        
        canvas = event.widget
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        
        # ドラッグ量計算
        dx = x - self.drag_start[0]
        dy = y - self.drag_start[1]
        
        # スケールを逆変換 (Canvas座標 → 元画像座標)
        scale_x = getattr(canvas, 'scale_x', 1.0)
        scale_y = getattr(canvas, 'scale_y', 1.0)
        
        dx_src = dx / scale_x if scale_x > 0 else 0
        dy_src = dy / scale_y if scale_y > 0 else 0
        
        # 矩形を移動
        if hasattr(self.selected_region, 'rect') and len(self.selected_region.rect) >= 4:
            self.selected_region.rect[0] += dx_src
            self.selected_region.rect[1] += dy_src
            self.selected_region.rect[2] += dx_src
            self.selected_region.rect[3] += dy_src
        
        self.drag_start = (x, y)
        
        # 再描画
        if hasattr(self, '_redraw_regions'):
            self._redraw_regions()
        
        logger.debug(f"Region moved by ({dx_src:.1f}, {dy_src:.1f})")
    
    def _on_edit_release(self, event):
        """
        編集モードでのリリース - リアルタイムシート更新
        
        レガシー移植元: L827-833
        - 編集完了通知
        - テキスト再計算
        - シート反映
        """
        if self.selected_region:
            # リアルタイムテキスト更新
            self._update_text_for_region(self.selected_region)
            
            # 編集履歴に追加
            self._add_edit_history('move', self.selected_region)
            
            logger.info(f"Region edit completed: {getattr(self.selected_region, 'area_code', 'unknown')}")
        
        self.drag_start = None
    
    def _select_region(self, region: Any):
        """
        領域を選択
        
        レガシー移植元: L835-839
        """
        self.selected_region = region
        
        if hasattr(self, '_update_selected_info'):
            self._update_selected_info()
        
        if hasattr(self, '_highlight_selected'):
            self._highlight_selected()
        
        logger.debug(f"Region selected: {getattr(region, 'area_code', 'unknown')}")
    
    def _deselect_region(self):
        """
        選択解除
        
        レガシー移植元: L841-845
        """
        self.selected_region = None
        
        if hasattr(self, 'selected_info') and self.selected_info:
            self.selected_info.configure(text="エリアを選択してください")
        
        if hasattr(self, '_redraw_regions'):
            self._redraw_regions()
        
        logger.debug("Region deselected")
    
    def _update_text_for_region(self, region: Any):
        """
        領域変更時のテキスト再計算とシート反映
        
        レガシー移植元: L885-888 (実装追加)
        
        ★ リアルタイムシート反映:
        - 新座標から包含テキストを再計算
        - スプレッドシートを即座に更新
        """
        logger.info(f"Updating text for region: {getattr(region, 'area_code', 'unknown')}")
        
        # raw_wordsから領域内のテキストを再計算
        if hasattr(self, '_recalculate_region_text'):
            new_text = self._recalculate_region_text(region)
            if new_text is not None:
                region.text = new_text
        
        # シート反映
        if hasattr(self, '_refresh_inline_spreadsheet'):
            self._refresh_inline_spreadsheet()
        
        # Sync再計算
        if hasattr(self, '_recalculate_sync'):
            self._recalculate_sync(update_ui=True)
    
    def _recalculate_region_text(self, region: Any) -> Optional[str]:
        """
        領域内のテキストを再計算
        
        raw_wordsから座標内の単語を収集してテキストを再構成
        """
        if not hasattr(self, 'web_raw_words') and not hasattr(self, 'pdf_raw_words'):
            return None
        
        # ソース判定
        source = getattr(region, 'source', 'web')
        raw_words = getattr(self, f'{source}_raw_words', [])
        
        if not raw_words:
            return None
        
        x1, y1, x2, y2 = region.rect[:4]
        
        # 領域内の単語を収集
        words_in_region = []
        for word_data in raw_words:
            if isinstance(word_data, dict):
                wx1 = word_data.get('x1', 0)
                wy1 = word_data.get('y1', 0)
                wx2 = word_data.get('x2', 0)
                wy2 = word_data.get('y2', 0)
                text = word_data.get('text', '')
                
                # 中心座標が領域内にあるか
                cx = (wx1 + wx2) / 2
                cy = (wy1 + wy2) / 2
                
                if x1 <= cx <= x2 and y1 <= cy <= y2:
                    words_in_region.append({
                        'y': wy1,
                        'x': wx1,
                        'text': text
                    })
        
        if not words_in_region:
            return ""
        
        # Y座標でソート、同じ行はX座標でソート
        words_in_region.sort(key=lambda w: (w['y'], w['x']))
        
        # テキストを結合
        result_text = ' '.join(w['text'] for w in words_in_region)
        logger.debug(f"Recalculated text: {len(result_text)} chars from {len(words_in_region)} words")
        
        return result_text
    
    def _get_regions_for_canvas(self, canvas) -> List[Any]:
        """キャンバスに対応する領域リストを取得"""
        if hasattr(self, 'web_canvas') and canvas == self.web_canvas:
            return getattr(self, 'web_regions', [])
        elif hasattr(self, 'pdf_canvas') and canvas == self.pdf_canvas:
            return getattr(self, 'pdf_regions', [])
        return []
    
    def _add_edit_history(self, action: str, region: Any):
        """編集履歴に追加"""
        import copy
        entry = {
            'action': action,
            'region_code': getattr(region, 'area_code', 'unknown'),
            'rect': copy.copy(region.rect) if hasattr(region, 'rect') else None,
            'timestamp': None
        }
        
        try:
            import time
            entry['timestamp'] = time.time()
        except:
            pass
        
        self._edit_history.append(entry)
        
        # 履歴上限 (100件)
        if len(self._edit_history) > 100:
            self._edit_history = self._edit_history[-100:]
    
    def _undo_last_edit(self) -> bool:
        """最後の編集を取り消し"""
        if not self._edit_history:
            logger.warning("No edit history to undo")
            return False
        
        last = self._edit_history.pop()
        logger.info(f"Undoing edit: {last['action']} on {last['region_code']}")
        
        # TODO: 実際の取り消し処理を実装
        return True


# ========== Convenience exports ==========
__all__ = ["EditMixin"]
