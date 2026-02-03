"""
DisplayMixin - 画像表示・領域描画関連メソッド
リファクタリング: 2026-01-13
"""

import tkinter as tk
from PIL import Image, ImageTk
from typing import Optional, Tuple


class DisplayMixin:
    """画像表示と領域描画のMixin"""

    def _stitch_pages_vertically(self, images: list) -> Image.Image:
        """複数の画像を縦に連結"""
        try:
            if not images:
                return Image.new('RGB', (100, 100), (30, 30, 30))

            # 有効な画像のみフィルタリング
            valid_images = [img for img in images if img and hasattr(img, 'width') and img.width > 0]
            if not valid_images:
                self._show_warning("有効な画像がありません")
                return Image.new('RGB', (100, 100), (30, 30, 30))

            # 最大幅に合わせる
            max_width = max(img.width for img in valid_images)
            total_height = sum(img.height for img in valid_images)

            # サイズ制限チェック（メモリ保護）
            if total_height > 100000:
                self._show_warning(f"画像が大きすぎます（高さ: {total_height}px）。最初の10ページのみ連結します。")
                valid_images = valid_images[:10]
                total_height = sum(img.height for img in valid_images)

            # 連結画像を作成
            stitched = Image.new('RGB', (max_width, total_height), (30, 30, 30))
            y_offset = 0

            for img in valid_images:
                # 幅を統一
                if img.width != max_width:
                    ratio = max_width / img.width
                    new_height = max(int(img.height * ratio), 1)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

                stitched.paste(img, (0, y_offset))
                y_offset += img.height

            return stitched

        except MemoryError as e:
            self._show_error("メモリ不足: 画像サイズを縮小してください", e)
            return Image.new('RGB', (100, 100), (30, 30, 30))
        except Exception as e:
            self._show_error("画像連結エラー", e, show_traceback=True)
            return Image.new('RGB', (100, 100), (30, 30, 30))

    def _display_image(self, canvas: tk.Canvas, image: Image.Image):
        """画像を表示 (幅優先フィット + 縦スクロール対応)"""
        try:
            if not image or not hasattr(image, 'width') or image.width == 0 or image.height == 0:
                print(f"[_display_image] SKIP: invalid image")
                return

            # キャンバスサイズ取得
            canvas.update_idletasks()
            canvas_width = max(canvas.winfo_width(), 100)

            # 幅に合わせてリサイズ
            img_copy = image.copy()
            scale_factor = canvas_width / img_copy.width
            new_width = max(canvas_width, 1)
            new_height = max(int(img_copy.height * scale_factor), 1)

            # サイズ制限（パフォーマンス保護）
            if new_height > 50000:
                scale_factor = 50000 / img_copy.height
                new_width = max(int(img_copy.width * scale_factor), 1)
                new_height = 50000

            img_copy = img_copy.resize((new_width, new_height), Image.Resampling.LANCZOS)

            photo = ImageTk.PhotoImage(img_copy)
            canvas.delete("image")

            canvas.create_image(0, 0, anchor="nw", image=photo, tags="image")
            canvas.tag_lower("image")
            canvas.image = photo

            canvas.configure(scrollregion=(0, 0, new_width, new_height))

            # スケール情報を保存
            canvas.scale_x = scale_factor
            canvas.scale_y = scale_factor
            canvas.offset_x = 0
            canvas.offset_y = 0

        except MemoryError as e:
            self._show_error("メモリ不足: 画像が大きすぎます", e)
        except Exception as e:
            self._show_error("画像表示エラー", e, show_traceback=True)

    def _redraw_regions(self):
        """エリア矩形を再描画 (シンク番号で色分け + 丸数字バッジ)"""
        try:
            sync_colors = [
                "#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#00BCD4",
                "#E91E63", "#CDDC39", "#FF5722", "#607D8B", "#795548"
            ]
            # ★ Legacy: 丸数字バッジ
            circle_numbers = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩",
                             "⑪", "⑫", "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳"]

            for canvas, regions, source in [
                (self.web_canvas, self.web_regions, "web"),
                (self.pdf_canvas, self.pdf_regions, "pdf")
            ]:
                if not canvas:
                    continue

                canvas.delete("region")
                canvas.delete("badge")  # ★ バッジも削除

                if not regions:
                    continue

                scale_x = getattr(canvas, 'scale_x', 1.0)
                scale_y = getattr(canvas, 'scale_y', 1.0)
                offset_x = getattr(canvas, 'offset_x', 0)
                offset_y = getattr(canvas, 'offset_y', 0)

                for idx, region in enumerate(regions):
                    try:
                        if not hasattr(region, 'rect') or len(region.rect) < 4:
                            continue

                        # ★ Phase 45: Global-to-Local Coordinate Mapping (Orchestra Fix)
                        # Canvasは「現在のページ画像」を表示しているため、ステッチ座標(Y=15000等)を
                        # そのまま描画すると画面外になる。ページオフセットを引いてローカル座標に戻す。
                        
                        current_page = getattr(self, 'current_page', 1)
                        
                        if source == "web":
                            # ページフィルタリング: 現在のページ以外の領域は描画しない（または薄く描画）
                            # region.page_id がある場合のみチェック
                            r_page = getattr(region, 'page_id', -1)
                            if r_page != -1 and r_page != current_page:
                                continue # 別ページの領域はスキップ
                            
                            # 座標変換: Global -> Local
                            # stored offsets: self.web_page_offsets
                            offsets = getattr(self, 'web_page_offsets', [0])
                            
                            # current_page is 1-based index
                            page_idx = current_page - 1
                            if 0 <= page_idx < len(offsets):
                                y_offset = offsets[page_idx]
                                # Note: region.rect is Global (Stitch) Coordinates
                                y1_src = region.rect[1] - y_offset
                                y2_src = region.rect[3] - y_offset
                                
                                # Xはそのまま
                                x1_src = region.rect[0]
                                x2_src = region.rect[2]
                                
                                # スケール適用
                                x1 = x1_src * scale_x + offset_x
                                y1 = y1_src * scale_y + offset_y
                                x2 = x2_src * scale_x + offset_x
                                y2 = y2_src * scale_y + offset_y
                            else:
                                # Fallback (should not happen if offsets synced)
                                x1 = region.rect[0] * scale_x + offset_x
                                y1 = region.rect[1] * scale_y + offset_y
                                x2 = region.rect[2] * scale_x + offset_x
                                y2 = region.rect[3] * scale_y + offset_y
                        else:
                            # PDF (or unset source) uses standard scaling
                            x1 = region.rect[0] * scale_x + offset_x
                            y1 = region.rect[1] * scale_y + offset_y
                            x2 = region.rect[2] * scale_x + offset_x
                            y2 = region.rect[3] * scale_y + offset_y

                        # ★ 修正: sync_numberでバッジ番号と色を決定
                        sync_num = getattr(region, 'sync_number', None)
                        
                        if region == self.selected_region:
                            outline = "#FFFFFF"
                            width = 3
                            badge_num = sync_num if sync_num is not None else idx
                        elif sync_num is not None:
                            outline = sync_colors[sync_num % len(sync_colors)]
                            width = 2
                            badge_num = sync_num
                        else:
                            # ★ 修正: 未同期は灰色
                            outline = "#808080"
                            width = 2
                            badge_num = idx

                        canvas.create_rectangle(
                            x1, y1, x2, y2,
                            outline=outline, width=width,
                            tags="region"
                        )

                        # ★ 修正: sync_number+1を表示（マッチペア識別用）
                        badge_text = circle_numbers[badge_num] if badge_num < 20 else str(badge_num + 1)
                        badge_bg = canvas.create_rectangle(
                            x1, y1, x1 + 30, y1 + 22,
                            fill=outline, outline="",
                            tags="badge"
                        )
                        canvas.create_text(
                            x1 + 15, y1 + 11,
                            text=badge_text,
                            fill="white",
                            font=("Arial", 11, "bold"),
                            tags="badge"
                        )
                    except Exception as e:
                        print(f"[WARNING] Region描画スキップ: {e}")
                        continue

        except Exception as e:
            self._show_error("領域描画エラー", e, show_traceback=True)

    def _highlight_region_on_canvas(self, canvas, region, color: str):
        """キャンバス上の特定領域をハイライト"""
        if not canvas or not region:
            return

        try:
            scale_x = getattr(canvas, 'scale_x', 1.0)
            scale_y = getattr(canvas, 'scale_y', 1.0)
            offset_x = getattr(canvas, 'offset_x', 0)
            offset_y = getattr(canvas, 'offset_y', 0)

            if hasattr(region, 'rect') and len(region.rect) >= 4:
                x1 = region.rect[0] * scale_x + offset_x
                y1 = region.rect[1] * scale_y + offset_y
                x2 = region.rect[2] * scale_x + offset_x
                y2 = region.rect[3] * scale_y + offset_y

                # ハイライト矩形
                canvas.create_rectangle(
                    x1, y1, x2, y2,
                    outline=color, width=4,
                    tags="highlight"
                )

                # ★ 修正: scrollregionの全体高さで計算
                scroll_region = canvas.cget("scrollregion")
                if scroll_region:
                    parts = scroll_region.split()
                    if len(parts) >= 4:
                        total_height = float(parts[3])
                        if total_height > 0:
                            # 領域の中央にスクロール
                            center_y = (y1 + y2) / 2
                            visible_height = canvas.winfo_height()
                            # 領域が中央に来るように調整
                            scroll_pos = max(0, (center_y - visible_height / 2) / total_height)
                            scroll_pos = min(scroll_pos, 1.0)
                            canvas.yview_moveto(scroll_pos)

        except Exception as e:
            print(f"[WARNING] ハイライトエラー: {e}")

    def _get_color_for_score(self, score: float) -> str:
        """スコアに応じた色を返す"""
        if score >= 0.8:
            return "#4CAF50"  # 緑
        elif score >= 0.5:
            return "#FFC107"  # 黄
        elif score >= 0.3:
            return "#FF9800"  # 橙
        else:
            return "#F44336"  # 赤
