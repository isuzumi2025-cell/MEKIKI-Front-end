"""
重大度判定ルールエンジン
差分種別・フィールド種別から severity と risk_reason を決定

Created: 2026-01-11
"""
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import yaml
from pathlib import Path


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFO = "INFO"


class RulesEngine:
    """
    重大度判定ルールエンジン
    rules.yaml を読み込み、差分に対して severity と risk_reason を決定
    """
    
    def __init__(self, rules_path: Optional[str] = None):
        """
        初期化
        
        Args:
            rules_path: rules.yaml のパス（Noneの場合はデフォルト）
        """
        if rules_path is None:
            # デフォルトパス
            rules_path = Path(__file__).parent.parent / "config" / "rules.yaml"
        
        self.rules_path = Path(rules_path)
        self.config = self._load_rules()
        
        # 重大度ルールをパース
        self.severity_rules = self.config.get("severity_rules", [])
        self.field_rules = self.config.get("field_rules", [])
        self.match_weights = self.config.get("match_weights", {
            "alpha_text": 0.4,
            "beta_embed": 0.2,
            "gamma_layout": 0.2,
            "delta_visual": 0.2
        })
    
    def _load_rules(self) -> Dict[str, Any]:
        """rules.yaml 読み込み"""
        if not self.rules_path.exists():
            print(f"[RulesEngine] Warning: {self.rules_path} not found, using defaults")
            return {}
        
        try:
            with open(self.rules_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[RulesEngine] Error loading rules: {e}")
            return {}
    
    def evaluate(
        self,
        diff_type: str,
        field_type: Optional[str] = None,
        role: Optional[str] = None,
        text_diff: Optional[str] = None,
        left_value: Optional[str] = None,
        right_value: Optional[str] = None,
        **kwargs
    ) -> Tuple[Severity, List[str]]:
        """
        差分を評価し、重大度と理由を返す
        
        Args:
            diff_type: 差分種別 (text_diff, field_diff, missing, added, table_diff)
            field_type: フィールド種別 (price, date, url, etc.)
            role: 要素ロール (headline, body, legal, etc.)
            text_diff: テキスト差分（判定用）
            left_value: 左側の値
            right_value: 右側の値
            **kwargs: 追加パラメータ
        
        Returns:
            (severity, risk_reasons)
        """
        # コンテキストを構築
        context = {
            "diff_type": diff_type,
            "field_type": field_type,
            "role": role,
            "text_diff": text_diff,
            "left_value": left_value,
            "right_value": right_value,
            "has_diff": left_value != right_value if left_value and right_value else True,
            "is_whitespace_only": self._is_whitespace_only(left_value, right_value),
            "is_punctuation_only": self._is_punctuation_only(left_value, right_value),
            **kwargs
        }
        
        # 数値差分の計算
        if field_type in ("percent", "price", "dimension"):
            context["abs_diff"] = self._calculate_numeric_diff(left_value, right_value)
        
        # ルールを順番に評価
        fired_reasons = []
        highest_severity = Severity.INFO
        
        for rule in self.severity_rules:
            condition = rule.get("condition", "")
            severity_str = rule.get("severity", "INFO")
            risk_reason = rule.get("risk_reason", "")
            
            # 条件評価
            if self._evaluate_condition(condition, context):
                severity = Severity(severity_str)
                fired_reasons.append(risk_reason)
                
                # 最も高い重大度を採用
                if self._severity_rank(severity) > self._severity_rank(highest_severity):
                    highest_severity = severity
        
        # デフォルト判定
        if not fired_reasons:
            if diff_type == "missing":
                return Severity.MAJOR, ["要素が欠落"]
            elif diff_type == "added":
                return Severity.MINOR, ["要素が追加"]
            elif diff_type == "text_diff":
                return Severity.MINOR, ["テキスト差分"]
        
        return highest_severity, fired_reasons
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """
        条件式を評価
        
        簡易的な条件パーサー
        例: "diff_type == 'missing' and role == 'legal'"
        """
        if not condition:
            return False
        
        try:
            # 安全な評価（限定的な名前空間）
            safe_context = {
                k: v for k, v in context.items()
                if isinstance(v, (str, int, float, bool, type(None)))
            }
            return eval(condition, {"__builtins__": {}}, safe_context)
        except Exception:
            # 条件評価失敗時はFalse
            return False
    
    def _severity_rank(self, severity: Severity) -> int:
        """重大度をランク化"""
        ranks = {
            Severity.CRITICAL: 4,
            Severity.MAJOR: 3,
            Severity.MINOR: 2,
            Severity.INFO: 1
        }
        return ranks.get(severity, 0)
    
    def _is_whitespace_only(self, left: Optional[str], right: Optional[str]) -> bool:
        """空白のみの差分か"""
        if left is None or right is None:
            return False
        import re
        return re.sub(r'\s+', '', left) == re.sub(r'\s+', '', right)
    
    def _is_punctuation_only(self, left: Optional[str], right: Optional[str]) -> bool:
        """句読点のみの差分か"""
        if left is None or right is None:
            return False
        import re
        # 句読点・記号を除去して比較
        pattern = r'[、。,.!?！？・：:；;「」『』（）()【】\[\]{}]'
        return re.sub(pattern, '', left) == re.sub(pattern, '', right)
    
    def _calculate_numeric_diff(self, left: Optional[str], right: Optional[str]) -> float:
        """数値差分を計算"""
        if left is None or right is None:
            return float('inf')
        
        import re
        
        def extract_number(s: str) -> Optional[float]:
            # 数字部分を抽出
            match = re.search(r'[\d,.]+', s)
            if match:
                try:
                    return float(match.group().replace(',', ''))
                except ValueError:
                    return None
            return None
        
        left_num = extract_number(left)
        right_num = extract_number(right)
        
        if left_num is not None and right_num is not None:
            return abs(left_num - right_num)
        return float('inf')
    
    def get_field_rule(self, field_type: str) -> Optional[Dict[str, Any]]:
        """フィールドルールを取得"""
        for rule in self.field_rules:
            if rule.get("field_type") == field_type:
                return rule
        return None


# ========== Convenience Function ==========

def evaluate_diff(
    diff_type: str,
    field_type: Optional[str] = None,
    role: Optional[str] = None,
    left_value: Optional[str] = None,
    right_value: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    差分を評価（簡易インターフェース）
    
    Returns:
        {
            "severity": "CRITICAL|MAJOR|MINOR|INFO",
            "risk_reasons": ["理由1", "理由2"],
            "rules_fired": int
        }
    """
    engine = RulesEngine()
    severity, reasons = engine.evaluate(
        diff_type=diff_type,
        field_type=field_type,
        role=role,
        left_value=left_value,
        right_value=right_value,
        **kwargs
    )
    
    return {
        "severity": severity.value,
        "risk_reasons": reasons,
        "rules_fired": len(reasons)
    }


if __name__ == "__main__":
    # テスト
    engine = RulesEngine()
    
    # 価格差分（CRITICAL）
    result = engine.evaluate(
        diff_type="field_diff",
        field_type="price",
        left_value="¥1,980",
        right_value="¥1,880"
    )
    print(f"価格差分: {result}")
    
    # 法務文言欠落（CRITICAL）
    result = engine.evaluate(
        diff_type="missing",
        role="legal"
    )
    print(f"法務欠落: {result}")
    
    # 空白のみ（MINOR）
    result = engine.evaluate(
        diff_type="text_diff",
        left_value="サンプル テキスト",
        right_value="サンプルテキスト"
    )
    print(f"空白差分: {result}")
