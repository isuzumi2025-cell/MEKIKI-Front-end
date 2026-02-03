"""
Multi-Agent Discussion Orchestra
複数AIエージェントを連携させて議論・問題解決

エージェント構成:
- GPT (GPT-4o): 戦略アドバイザー
- Grok: リアルタイムWeb/X検索
- Antigravity (Claude): 実装担当
- Obsidian: ナレッジベース
- Slack: 通知・記録

使用方法:
    from app.sdk.orchestration.orchestra import discuss
    result = discuss("HybridOCRの最適化方法")
"""
import os
import json
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv

from app.sdk.integration.notification.agent_client import get_agent_client, AgentBackend

load_dotenv()


class AgentOrchestra:
    """マルチエージェント議論オーケストレーター"""
    
    def __init__(self):
        self.agents = {}
        self.discussion_log = []
        self._init_agents()
    
    def _init_agents(self):
        """利用可能なエージェントを初期化"""
        # GPT (Producer)
        if os.getenv("OPENAI_API_KEY"):
            self.agents['gpt'] = GPTAgent()
        
        # Gemini (Reviewer) - 常に利用可能
        if os.getenv("GEMINI_API_KEY"):
            self.agents['reviewer'] = ReviewerAgent()
        
        # Grok
        if os.getenv("GROK_API_KEY"):
            self.agents['grok'] = GrokAgent()
        
        # Obsidian (常に利用可能)
        self.agents['obsidian'] = ObsidianAgent()
        
        # Slack
        self.agents['slack'] = SlackAgent()
        
        print(f"🎭 Orchestra初期化: {list(self.agents.keys())}")
    
    def discuss(self, topic: str, rounds: int = 2) -> Dict:
        """
        トピックについてマルチエージェント議論
        
        必須5エージェント協議フロー:
        1. Obsidian/Clawdbot: 内部情報取得
        2. Grok: 外部リアルタイム情報
        3. Antigravity Browser: 外部調査（必要に応じて）
        4. GPT-5.2: 戦略立案
        5. Gemini: レビュー・スコアリング
        
        Args:
            topic: 議論トピック
            rounds: 議論ラウンド数
        
        Returns:
            議論結果
        """
        self.discussion_log = []
        timestamp = datetime.now().isoformat()
        
        print(f"\n🎭 [Orchestra] 議論開始: {topic}")
        print("=" * 60)
        print("必須エージェント: GPT-5.2 / Grok / Antigravity / Clawdbot / Gemini")
        print("=" * 60)
        
        # 1. Obsidian/Clawdbot: 内部情報取得
        obsidian_context = self.agents['obsidian'].search(topic)
        doc_count = len(obsidian_context.get('vault', []))
        self._log('obsidian', f"内部情報取得: {doc_count}件")
        
        # 2. Grok: リアルタイム外部情報
        realtime_info = None
        grok_summary = "未実行"
        if 'grok' in self.agents:
            realtime_info = self.agents['grok'].search(topic)
            grok_summary = realtime_info.get('summary', 'N/A') if realtime_info else 'エラー'
            self._log('grok', f"外部リアルタイム検索完了")
        else:
            self._log('grok', f"⚠️ Grok未接続（APIキー確認）")
        
        # 3. Antigravity Browser Control: 外部調査フラグ
        # Note: ブラウザ操作は自動実行せず、必要に応じて後で実行
        antigravity_info = {
            'available': True,
            'note': 'Browser Control可能（必要時に実行）'
        }
        self._log('antigravity', f"Browser Control待機中")
        
        # 4. GPT-5.2 (Producer): 戦略立案
        strategy = None
        if 'gpt' in self.agents:
            context = self._build_context(obsidian_context, realtime_info)
            strategy = self.agents['gpt'].consult(topic, context)
            self._log('gpt', f"GPT-5.2 戦略提案完了")
        else:
            self._log('gpt', f"⚠️ GPT未接続（APIキー確認）")
        
        # 5. Gemini (Reviewer): レビュー・スコアリング & デバッグ判断
        reviewed_strategy = strategy
        review_feedback = None
        review_score = None
        
        if strategy and 'reviewer' in self.agents:
            review_result = self.agents['reviewer'].review(topic, strategy)
            review_feedback = review_result.get('feedback')
            review_score = review_result.get('score', 0)
            
            # デバッグ/調査指示があるか確認
            debug_directive = review_result.get('debug_directive', {})
            debug_info = ""
            
            if debug_directive.get('required'):
                task_desc = debug_directive.get('task')
                self._log('reviewer', f"✋ 調査要求: {task_desc}")
                print(f"🔧 [Orchestra] Geminiがデバッグ調査を要求しました: {task_desc}")
                
                client = get_agent_client()
                if client.is_available(AgentBackend.OPENCLAW):
                    self._log('openclaw', f"調査開始: {task_desc}")
                    print(f"🚀 OpenClaw起動中...")
                    
                    spawn_result = client.spawn_task(
                        task=task_desc,
                        allow_spawn=False,
                        priority="high",
                        timeout=120
                    )
                    
                    if spawn_result:
                        output = spawn_result.get('output', 'No output')
                        status = spawn_result.get('status', 'unknown')
                        debug_info = f"\n\n【OpenClaw調査結果 (Status: {status})】\n{output}"
                        self._log('openclaw', f"調査完了: {status}")
                    else:
                        debug_info = "\n\n【OpenClaw調査結果】\n実行失敗またはタイムアウト"
                        self._log('openclaw', f"⚠️ 調査失敗")
                else:
                    self._log('openclaw', f"⚠️ OpenClaw未接続のため調査スキップ")
                    debug_info = "\n\n【OpenClaw調査】\nOpenClaw未接続のためスキップ"

            # レビュー結果と調査結果を合わせてログ出力
            self._log('reviewer', f"Gemini レビュー完了: スコア {review_score}/10")
            
            # スコアが低い、または調査結果がある場合は改善版を生成
            if (review_score < 8 or debug_info) and 'gpt' in self.agents:
                # フィードバックに調査結果を結合
                full_feedback = f"{review_feedback}{debug_info}"
                improved = self.agents['gpt'].improve(topic, strategy, full_feedback)
                if improved:
                    reviewed_strategy = improved
                    self._log('gpt', f"GPT-5.2 改善版生成完了 (調査結果反映済み)")
                    
                    # 改善版を再度簡易レビュー（オプション）
                    # 今回はループ回避のため省略するが、本来は再レビューが望ましい
        else:
            self._log('reviewer', f"⚠️ Gemini未接続（APIキー確認）")
        
        # 6. 必須エージェント参加状況サマリー
        participation = {
            'obsidian': doc_count > 0,
            'grok': realtime_info is not None,
            'antigravity': True,  # 常に待機
            'gpt': strategy is not None,
            'gemini': review_score is not None
        }
        print(f"\n📊 参加状況: {sum(participation.values())}/5 エージェント")
        
        # 7. 結果をまとめる
        result = {
            'topic': topic,
            'timestamp': timestamp,
            'obsidian_context': obsidian_context,
            'realtime_info': realtime_info,
            'antigravity_info': antigravity_info,
            'gpt_strategy': reviewed_strategy,
            'original_strategy': strategy,
            'review_feedback': review_feedback,
            'score': review_score,
            'participation': participation,
            'discussion_log': self.discussion_log
        }
        
        # 8. Slackに通知
        self._notify_slack(result)
        
        # 9. Obsidianに保存
        self._save_to_obsidian(result)
        
        print("=" * 60)
        print(f"🎭 [Orchestra] 議論完了 - スコア: {review_score}/10\n")
        
        return result
    
    def _log(self, agent: str, message: str):
        """議論ログに追加"""
        entry = {
            'agent': agent,
            'message': message,
            'time': datetime.now().isoformat()
        }
        self.discussion_log.append(entry)
        icon = {'gpt': '🧠', 'grok': '🌐', 'obsidian': '📚', 'slack': '💬'}.get(agent, '🤖')
        print(f"  {icon} [{agent.upper()}] {message}")
    
    def _build_context(self, obsidian: Dict, grok: Optional[Dict]) -> str:
        """エージェント用コンテキストを構築"""
        parts = []
        
        if obsidian.get('files'):
            parts.append("【Obsidian既存知識】")
            for f in obsidian['files'][:3]:
                parts.append(f"- {f.get('path', 'unknown')}")
        
        if grok and grok.get('summary'):
            parts.append("\n【Grokリアルタイム情報】")
            parts.append(grok['summary'][:500])
        
        return '\n'.join(parts)
    
    def _notify_slack(self, result: Dict):
        """Slackに議論結果を通知"""
        try:
            message = f"🎭 [Orchestra] 議論完了: {result['topic'][:50]}..."
            self.agents['slack'].notify(message)
            self._log('slack', "通知送信完了")
        except Exception as e:
            self._log('slack', f"通知失敗: {e}")
    
    def _save_to_obsidian(self, result: Dict):
        """議論結果をObsidianに保存"""
        try:
            self.agents['obsidian'].save_discussion(result)
            self._log('obsidian', "議論ログ保存完了")
        except Exception as e:
            self._log('obsidian', f"保存失敗: {e}")


class GPTAgent:
    """GPT戦略アドバイザー (Producer)"""
    
    def consult(self, topic: str, context: str) -> Optional[str]:
        try:
            from openai import OpenAI
            client = OpenAI()
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "あなたはMEKIKI Proofing Systemの戦略アドバイザーです。具体的で実装可能な提案をしてください。"},
                    {"role": "user", "content": f"トピック: {topic}\n\nコンテキスト:\n{context}\n\n戦略的アドバイスをください。"}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"  ⚠️ GPT エラー: {e}")
            return None
    
    def improve(self, topic: str, original: str, feedback: str) -> Optional[str]:
        """レビューフィードバックを元に改善版を生成"""
        try:
            from openai import OpenAI
            client = OpenAI()
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "レビューフィードバックを元に、戦略提案を改善してください。"},
                    {"role": "user", "content": f"トピック: {topic}\n\n【元の提案】\n{original[:2000]}\n\n【レビューフィードバック】\n{feedback}\n\n上記を踏まえて改善版を生成してください。"}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"  ⚠️ GPT 改善エラー: {e}")
            return None


class ReviewerAgent:
    """Geminiレビューエージェント (Reviewer)"""
    
    def review(self, topic: str, strategy: str) -> Dict[str, Any]:
        """戦略をレビューしてスコアとフィードバック、デバッグ指示を返す"""
        try:
            from app.core.llm_client import LLMClient
            client = LLMClient()
            
            prompt = f"""
あなたはMEKIKIプロジェクトの「最高品質責任者」の役割を持つAIです。
提案された戦略に対し、**徹底的な批判的レビュー**を行ってください。

【重要指針: NOと言える勇気】
- ユーザーやGPTの提案に安易に迎合しないでください。
- 「言われた通りに動く」ことよりも、「未然に事故を防ぐ」「根本解決する」ことを優先してください。
- 曖昧な点や前提条件に疑義がある場合は、必ず**「逆質問」**を行ってください。
- 実装前に確認すべき挙動や仕様がある場合は、**「デバッグ/調査指示」**を出してください。

【評価対象】
トピック: {topic}
戦略案: {strategy[:5000]}

【出力フォーマット】
以下のJSONフォーマットで出力してください。Markdownのコードブロック(```json ... ```)で囲ってください。

{{
  "score": <0-10の整数 (8未満は改善必須)>,
  "critical_questions": ["<前提を確認する逆質問1>", "<リスクに関する質問2>"],
  "debug_directive": {{
    "required": <true/false (調査が必要な場合のみtrue)>,
    "task": "<OpenClawに実行させるべき具体的な調査・デバッグタスク記述>"
  }},
  "feedback": "<詳細なレビューコメント。辛辣な指摘も歓迎します>"
}}
"""
            result_text = client.generate_content(prompt)
            
            # JSON抽出
            import json
            import re
            
            # デフォルト値
            clean_result = {
                'score': 5,
                'feedback': result_text,
                'debug_directive': {'required': False},
                'reviewer': 'gemini'
            }

            if result_text:
                try:
                    # MarkdownコードブロックからJSONを探す
                    match = re.search(r'```json\s*(\{.*?\})\s*```', result_text, re.DOTALL)
                    if not match:
                        # コードブロックがない場合、全体から{}を探す
                        match = re.search(r'(\{.*\})', result_text, re.DOTALL)
                    
                    if match:
                        json_str = match.group(1)
                        data = json.loads(json_str)
                        clean_result.update(data)
                        
                        # feedbackフィールドが無い場合のフォールバック
                        if 'feedback' not in data:
                            clean_result['feedback'] = result_text
                    
                except Exception as parse_error:
                    print(f"  ⚠️ JSON Parse Error: {parse_error}")
                    # パースエラーでも生のテキストは残す
            
            return clean_result

        except Exception as e:
            print(f"  ⚠️ Reviewer エラー: {e}")
            return {'score': 5, 'feedback': str(e), 'debug_directive': {'required': False}, 'reviewer': 'error'}


class GrokAgent:
    """Grokリアルタイム検索"""
    
    def search(self, topic: str) -> Dict:
        try:
            from app.sdk.llm.grok_client import search_realtime
            return search_realtime(topic)
        except Exception as e:
            print(f"  ⚠️ Grok エラー: {e}")
            return {'summary': None}


class ObsidianAgent:
    """Obsidianナレッジベース"""
    
    def __init__(self):
        self.vault_path = "c:/Users/raiko/OneDrive/Desktop/26/OCR/Vault"
    
    def search(self, topic: str) -> Dict:
        try:
            from app.sdk.integration.notification.context_search import find_related_context
            return find_related_context(topic)
        except Exception as e:
            return {'files': [], 'error': str(e)}
    
    def save_discussion(self, result: Dict):
        """議論をObsidianに保存"""
        from pathlib import Path
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"discussion_{timestamp}.md"
        path = Path(self.vault_path) / "50_Logs" / "discussions" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        
        content = self._format_discussion(result)
        path.write_text(content, encoding='utf-8')
    
    def _format_discussion(self, result: Dict) -> str:
        lines = [
            f"# 議論ログ: {result['topic']}",
            f"**日時**: {result['timestamp']}",
            "",
            "## 参加エージェント",
            ""
        ]
        
        for log in result.get('discussion_log', []):
            lines.append(f"- **{log['agent']}**: {log['message']}")
        
        if result.get('gpt_strategy'):
            lines.extend([
                "",
                "## GPT戦略提案",
                "",
                result['gpt_strategy']
            ])
        
        # Add Gemini review feedback
        if result.get('review_feedback'):
            lines.extend([
                "",
                f"## Geminiレビュー (スコア: {result.get('score', 'N/A')}/10)",
                "",
                result['review_feedback']
            ])
        
        lines.extend(["", "---", "Tags: #Discussion #Orchestra #MEKIKI"])
        return '\n'.join(lines)


class SlackAgent:
    """Slack通知"""
    
    def notify(self, message: str):
        from app.sdk.integration.notification.clawdbot_client import notify_slack
        notify_slack(message)


# ショートカット関数
_orchestra = None

def discuss(topic: str, rounds: int = 2) -> Dict:
    """トピックについてマルチエージェント議論"""
    global _orchestra
    if _orchestra is None:
        _orchestra = AgentOrchestra()
    return _orchestra.discuss(topic, rounds)


# CLI実行
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        topic = ' '.join(sys.argv[1:])
        result = discuss(topic)
        print("\n📋 議論結果:")
        if result.get('strategy'):
            print(result['strategy'][:500])
    else:
        print("Usage: python -m app.sdk.orchestra 'discussion topic'")
