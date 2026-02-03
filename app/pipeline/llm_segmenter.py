"""
Phase 5: マルチモーダルLLMパラグラフ生成

処理フロー:
1. 全文抽出（クラスタリングなし）
2. 全文比較 → マッチ箇所検出
3. LLM（画像+テキスト+マッチ情報）→ パラグラフ生成
4. LiveComparisonSheetに反映
"""

import json
import re
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
import google.generativeai as genai
from PIL import Image
from config import Config
try:
    from app.config import get_match_config
except ImportError:
    get_match_config = None


@dataclass
class LLMParagraph:
    """LLM生成パラグラフ"""
    id: str
    web_text: str
    pdf_text: str
    sync_score: float
    common_anchor: str = ""


class MultimodalLLMSegmenter:
    """
    マルチモーダルLLMパラグラフ生成器
    
    画像+テキスト+マッチ情報からパラグラフを生成
    """
    
    def __init__(self):
        self.model = None
        if Config.GEMINI_API_KEY:
            try:
                genai.configure(api_key=Config.GEMINI_API_KEY)
                self.model = genai.GenerativeModel("gemini-2.0-flash")
                print("✅ Multimodal LLM Segmenter initialized")
            except Exception as e:
                print(f"❌ LLM init error: {e}")
    
    def generate_paragraphs(
        self,
        web_image: Image.Image,
        pdf_image: Image.Image,
        web_full_text: str,
        pdf_full_text: str,
        match_segments: List[Dict]
    ) -> List[LLMParagraph]:
        """
        画像+テキスト+マッチ情報からパラグラフを生成
        
        Args:
            web_image: Webスクリーンショット
            pdf_image: PDFページ画像
            web_full_text: Web全文（クラスタリングなし）
            pdf_full_text: PDF全文（クラスタリングなし）
            match_segments: 共通部分リスト [{common, web_context, pdf_context}, ...]
        
        Returns:
            List[LLMParagraph]: 生成されたパラグラフペア
        """
        if not self.model:
            print("⚠️ LLM not available, using fallback")
            return self._fallback_paragraphs(match_segments, web_full_text, pdf_full_text)
        
        print("🧠 マルチモーダルLLMパラグラフ生成開始...")
        
        # マッチ情報をテキスト化
        match_info = self._format_match_info(match_segments)
        
        # プロンプト構築
        prompt = f"""あなたはテキスト比較の専門家です。

## タスク
Web画像とPDF画像を見て、両方に共通するテキストセグメントを特定し、
論理的なパラグラフペアに分割してください。

## 共通テキスト情報（すでに検出済み）
{match_info}

## Web全文（参考）
{web_full_text[:2000]}

## PDF全文（参考）
{pdf_full_text[:2000]}

## 出力形式
以下のJSON配列を返してください。他の説明は不要です：
[
  {{"web": "Webのパラグラフ1", "pdf": "PDFのパラグラフ1", "anchor": "共通アンカー文字列"}},
  ...
]

最大20ペアまで。視覚的レイアウトを考慮して分割してください。
"""
        
        try:
            import io
            import base64
            
            # 画像をバイトに変換（Gemini API用）
            def image_to_part(img: Image.Image):
                """PIL ImageをGemini Part形式に変換（ImageSegmentを使用）"""
                try:
                    from app.sdk.core.segment import ImageSegment
                    segment = ImageSegment.from_image(img, max_long_edge=1024)
                    target_img = segment.resized_image if segment.resized_image else img
                except ImportError:
                    # フォールバック: 従来のリサイズ
                    target_img = img
                    max_dim = 1024
                    if img.width > max_dim or img.height > max_dim:
                        scale = min(max_dim / img.width, max_dim / img.height)
                        target_img = img.resize((int(img.width * scale), int(img.height * scale)))
                
                img_byte_arr = io.BytesIO()
                # RGBに変換
                if target_img.mode != 'RGB':
                    target_img = target_img.convert('RGB')
                target_img.save(img_byte_arr, format='JPEG', quality=85)
                return {
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(img_byte_arr.getvalue()).decode()
                }
            
            web_part = image_to_part(web_image)
            pdf_part = image_to_part(pdf_image)
            
            # マルチモーダル入力（画像+テキスト）
            response = self.model.generate_content([
                prompt,
                web_part,
                pdf_part
            ])
            
            if not response.text:
                print("   ⚠️ LLM returned empty response, using fallback")
                return self._fallback_paragraphs(match_segments, web_full_text, pdf_full_text)
            
            print(f"   📝 LLM応答: {len(response.text)} chars")
            paragraphs = self._parse_llm_response(response.text)
            
            # パース失敗または空の場合はフォールバック
            if not paragraphs:
                print("   ⚠️ Parse returned 0 paragraphs, using fallback")
                return self._fallback_paragraphs(match_segments, web_full_text, pdf_full_text)
            
            print(f"   ✅ LLM生成完了: {len(paragraphs)}パラグラフ")
            return paragraphs
            
        except Exception as e:
            print(f"   ❌ LLM error: {e}")
            return self._fallback_paragraphs(match_segments, web_full_text, pdf_full_text)
    
    def _format_match_info(self, match_segments: List[Dict]) -> str:
        """マッチ情報をプロンプト用にフォーマット"""
        if not match_segments:
            return "（共通テキストなし）"
        
        lines = []
        for i, m in enumerate(match_segments[:15]):
            common = m.get('common', m.get('common_text', ''))[:50]
            lines.append(f"{i+1}. 共通: 「{common}」")
        
        return "\n".join(lines)
    
    def _parse_llm_response(self, response: str) -> List[LLMParagraph]:
        """LLMレスポンスをパース"""
        try:
            # コードブロック除去
            clean = response.strip()
            if clean.startswith("```"):
                clean = re.sub(r'^```\w*\n?', '', clean)
                clean = re.sub(r'\n?```$', '', clean)
            
            data = json.loads(clean)
            
            paragraphs = []
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    paragraphs.append(LLMParagraph(
                        id=f"LP-{i+1:03d}",
                        web_text=item.get('web', '')[:300],
                        pdf_text=item.get('pdf', '')[:300],
                        sync_score=0.8,  # LLM生成は高シンクロ
                        common_anchor=item.get('anchor', '')[:50]
                    ))
            
            return paragraphs
            
        except Exception as e:
            print(f"   ⚠️ Parse error: {e}")
            return []
    
    def _fallback_paragraphs(self, match_segments: List[Dict], web_text: str = "", pdf_text: str = "") -> List[LLMParagraph]:
        """フォールバック: マッチセグメントまたは全文からパラグラフ化"""
        print(f"   📋 Fallback: {len(match_segments)} matches, web={len(web_text)} chars, pdf={len(pdf_text)} chars")
        paragraphs = []
        
        def calc_similarity(text1: str, text2: str) -> float:
            """実際のテキスト類似度を計算"""
            if not text1 or not text2:
                return 0.0
            # 共通文字数による簡易類似度
            t1, t2 = set(text1), set(text2)
            if not t1 or not t2:
                return 0.0
            common = len(t1 & t2)
            return common / max(len(t1), len(t2))
        
        # マッチセグメントがある場合
        if match_segments:
            for i, m in enumerate(match_segments[:20]):
                w = m.get('web_text', m.get('web_context', ''))[:300]
                p = m.get('pdf_text', m.get('pdf_context', ''))[:300]
                paragraphs.append(LLMParagraph(
                    id=f"LP-{i+1:03d}",
                    web_text=w,
                    pdf_text=p,
                    sync_score=calc_similarity(w, p),  # 実際の類似度
                    common_anchor=m.get('common', m.get('common_text', ''))[:50]
                ))
        
        # マッチセグメントからパラグラフが作れなかった場合は全文から
        if not paragraphs and (web_text or pdf_text):
            print("   📋 Using full text for fallback")
            web_paras = [p.strip() for p in web_text.split('\n') if len(p.strip()) > 10][:20]
            pdf_paras = [p.strip() for p in pdf_text.split('\n') if len(p.strip()) > 10][:20]
            
            max_len = max(len(web_paras), len(pdf_paras), 1)
            for i in range(min(max_len, 20)):
                w = web_paras[i] if i < len(web_paras) else ""
                p = pdf_paras[i] if i < len(pdf_paras) else ""
                if w or p:
                    paragraphs.append(LLMParagraph(
                        id=f"LP-{i+1:03d}",
                        web_text=w[:300],
                        pdf_text=p[:300],
                        sync_score=calc_similarity(w, p),  # 実際の類似度
                        common_anchor=""
                    ))
        
        print(f"   📋 Fallback generated: {len(paragraphs)} paragraphs")
        return paragraphs


def find_common_segments(web_text: str, pdf_text: str, min_length: int = None) -> List[Dict]:
    """
    全文比較で共通セグメントを検出
    
    Args:
        web_text: Web全文
        pdf_text: PDF全文
        min_length: 最小共通文字数
    
    Returns:
        List[Dict]: 共通セグメントリスト
    """
    # Configからデフォルト値を取得
    if min_length is None:
        if get_match_config:
            min_length = get_match_config().min_match_length
        else:
            min_length = 8  # フォールバック
    
    if not web_text or not pdf_text:
        return []
    
    segments = []
    web_clean = web_text.replace('\n', ' ')
    pdf_clean = pdf_text.replace('\n', ' ')
    
    # 最長共通部分文字列を見つける（簡易版）
    found_positions = set()
    
    for length in range(min(100, len(web_clean)), min_length - 1, -1):
        for i in range(len(web_clean) - length + 1):
            substring = web_clean[i:i+length]
            if substring.strip() and substring in pdf_clean:
                # 重複チェック
                is_duplicate = False
                for pos in found_positions:
                    if abs(pos - i) < length // 2:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    found_positions.add(i)
                    
                    # コンテキスト抽出
                    web_start = max(0, i - 50)
                    web_end = min(len(web_clean), i + length + 50)
                    pdf_pos = pdf_clean.find(substring)
                    pdf_start = max(0, pdf_pos - 50)
                    pdf_end = min(len(pdf_clean), pdf_pos + length + 50)
                    
                    segments.append({
                        'common': substring,
                        'common_len': length,
                        'web_context': web_clean[web_start:web_end],
                        'pdf_context': pdf_clean[pdf_start:pdf_end]
                    })
                    
                    if len(segments) >= 30:  # 最大30セグメント
                        break
        
        if len(segments) >= 30:
            break
    
    # 長い順にソート
    segments.sort(key=lambda x: x['common_len'], reverse=True)
    return segments


def run_phase5_pipeline(
    web_image: Image.Image,
    pdf_image: Image.Image
) -> Tuple[List[LLMParagraph], List[Dict]]:
    """
    Phase 5 完全パイプライン
    
    1. 全文抽出
    2. 全文比較
    3. LLMパラグラフ生成
    
    Returns:
        (paragraphs, match_segments)
    """
    from app.core.engine_cloud import CloudOCREngine
    
    print("=" * 60)
    print("🚀 Phase 5: マルチモーダルLLMパラグラフ生成")
    print("=" * 60)
    
    # Step 1: 全文抽出
    ocr = CloudOCREngine()
    print("\n📄 Step 1: 全文抽出（クラスタリングなし）")
    web_full_text = ocr.extract_full_text(web_image)
    pdf_full_text = ocr.extract_full_text(pdf_image)
    
    print(f"   Web: {len(web_full_text)}文字")
    print(f"   PDF: {len(pdf_full_text)}文字")
    
    # Step 2: 全文比較
    print("\n🔍 Step 2: 全文比較 → マッチ箇所検出")
    match_segments = find_common_segments(web_full_text, pdf_full_text)
    print(f"   マッチセグメント: {len(match_segments)}件")
    
    # Step 3: LLMパラグラフ生成
    print("\n🧠 Step 3: LLMパラグラフ生成")
    segmenter = MultimodalLLMSegmenter()
    paragraphs = segmenter.generate_paragraphs(
        web_image, pdf_image,
        web_full_text, pdf_full_text,
        match_segments
    )
    
    print(f"\n✅ 完了: {len(paragraphs)}パラグラフ生成")
    return paragraphs, match_segments
