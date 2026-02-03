# Clawdbot Proxy Architecture

> **Source**: GPT-5.2 戦略指示 (2026-01-31)  
> **Status**: 計画中

---

## アーキテクチャ概要

```
┌─────────────┐     ┌─────────────────────┐     ┌─────────────┐
│ Antigravity │────▶│ Clawdbot (WSL)      │────▶│ GPT-5.2 API │
│ (Claude)    │     │ - LiteLLM Proxy     │     │             │
└─────────────┘     │ - Guardrail検閲     │     └─────────────┘
                    │ - 指示不履行監視     │
                    └─────────────────────┘
```

---

## メリット

| 項目 | 効果 |
|------|------|
| Guardrail | 指示不履行を検閲してからコード受け渡し |
| 監視 | Antigravityの行動をログ・監査 |
| 翻訳 | モデル間のプロトコル変換 |
| 制御 | リクエスト/レスポンスのフィルタリング |

---

## 実装計画

### Phase 1: LiteLLM Proxy 設定

```bash
# WSL側でLiteLLMサーバー起動
pip install litellm
litellm --model gpt-4o --port 8080
```

### Phase 2: Guardrail 実装

```python
# clawdbot_proxy/guardrail.py
def check_compliance(request: dict, response: dict) -> bool:
    """指示不履行チェック"""
    # 禁止パターン検出
    # ログ記録
    # アラート発火
    pass
```

### Phase 3: Antigravity統合

```python
# app/utils/gpt_bridge.py 修正
CLAWDBOT_PROXY_URL = "http://localhost:8080"

def query_gpt_via_proxy(prompt: str) -> str:
    """Clawdbot経由でGPT-5.2に問い合わせ"""
    response = requests.post(
        f"{CLAWDBOT_PROXY_URL}/v1/chat/completions",
        json={"messages": [{"role": "user", "content": prompt}]}
    )
    return response.json()["choices"][0]["message"]["content"]
```

---

## 参照

- [Clawdbot使用ガイド](clawdbot_guide.md)
- [GPT-5.2 Session Bridge](../20_AI_Strategy/GPT52_Session_Bridge.md)
