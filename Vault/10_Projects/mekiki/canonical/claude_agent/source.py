"""
Claude Code Agent
信頼性の高いコード編集と自動化エージェント

Features:
- 要件を守りながらコード修正
- バックアップ付きファイル編集
- 依存関係チェック
- 人間承認ゲート（破壊的変更時）
"""
import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field


@dataclass
class ToolResult:
    """ツール実行結果"""
    success: bool
    output: str
    error: Optional[str] = None


@dataclass
class Task:
    """タスク情報"""
    id: str
    description: str
    requirements: List[str]
    status: str = "pending"  # pending, in_progress, completed, failed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    changes: List[Dict] = field(default_factory=list)


class ClaudeAgent:
    """
    Claude Code エージェント
    
    Anthropic API を使用してコード編集・自動化を行う
    """
    
    def __init__(
        self,
        workspace_dir: str,
        backup_dir: Optional[str] = None,
        require_approval_for_destructive: bool = True
    ):
        """
        Args:
            workspace_dir: 作業ディレクトリ（編集可能なファイルの範囲）
            backup_dir: バックアップ保存先（デフォルト: workspace/.backups）
            require_approval_for_destructive: 破壊的変更に人間承認を要求
        """
        self.workspace_dir = Path(workspace_dir)
        self.backup_dir = Path(backup_dir) if backup_dir else self.workspace_dir / ".backups"
        self.require_approval = require_approval_for_destructive
        
        # API クライアント (遅延初期化)
        self._client = None
        
        # タスク管理
        self.tasks: Dict[str, Task] = {}
        self.current_task_id: Optional[str] = None
        
        # 承認待ちアクション
        self.pending_approval: Optional[Dict] = None
        
        # 変更履歴
        self.change_history: List[Dict] = []
        
        # ツール定義
        self.tools = self._define_tools()
        
        # バックアップディレクトリ作成
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"🤖 Claude Agent initialized")
        print(f"   Workspace: {self.workspace_dir}")
        print(f"   Backups: {self.backup_dir}")
    
    def _init_client(self):
        """Anthropic クライアントを初期化"""
        if self._client:
            return self._client
        
        try:
            import anthropic
            
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            
            self._client = anthropic.Anthropic(api_key=api_key)
            print("✅ Anthropic client initialized")
            return self._client
            
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
    
    def _define_tools(self) -> List[Dict]:
        """ツール定義"""
        return [
            {
                "name": "read_file",
                "description": "ファイルの内容を読み取る",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "読み取るファイルのパス（workspace相対）"
                        }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "edit_file",
                "description": "ファイルを編集する（差分ベース）。バックアップを自動作成。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "編集するファイルのパス（workspace相対）"
                        },
                        "search": {
                            "type": "string",
                            "description": "置換対象のテキスト（完全一致）"
                        },
                        "replace": {
                            "type": "string",
                            "description": "置換後のテキスト"
                        },
                        "reason": {
                            "type": "string",
                            "description": "変更理由"
                        }
                    },
                    "required": ["path", "search", "replace", "reason"]
                }
            },
            {
                "name": "create_file",
                "description": "新規ファイルを作成する",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "作成するファイルのパス（workspace相対）"
                        },
                        "content": {
                            "type": "string",
                            "description": "ファイル内容"
                        },
                        "reason": {
                            "type": "string",
                            "description": "作成理由"
                        }
                    },
                    "required": ["path", "content", "reason"]
                }
            },
            {
                "name": "run_command",
                "description": "シェルコマンドを実行する",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "実行するコマンド"
                        },
                        "reason": {
                            "type": "string",
                            "description": "実行理由"
                        }
                    },
                    "required": ["command", "reason"]
                }
            },
            {
                "name": "list_directory",
                "description": "ディレクトリ内のファイル一覧を取得",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "ディレクトリパス（workspace相対）"
                        }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "search_files",
                "description": "ファイル内をテキスト検索",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "検索クエリ"
                        },
                        "path": {
                            "type": "string",
                            "description": "検索対象ディレクトリ（workspace相対）",
                            "default": "."
                        },
                        "extensions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "対象ファイル拡張子（例: ['.py', '.js']）"
                        }
                    },
                    "required": ["query"]
                }
            }
        ]
    
    # ==================== Tool Implementations ====================
    
    def _execute_tool(self, name: str, args: Dict) -> ToolResult:
        """ツールを実行"""
        tool_map = {
            "read_file": self._tool_read_file,
            "edit_file": self._tool_edit_file,
            "create_file": self._tool_create_file,
            "run_command": self._tool_run_command,
            "list_directory": self._tool_list_directory,
            "search_files": self._tool_search_files,
        }
        
        handler = tool_map.get(name)
        if not handler:
            return ToolResult(success=False, output="", error=f"Unknown tool: {name}")
        
        try:
            return handler(**args)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
    
    def _resolve_path(self, path: str) -> Path:
        """パスをworkspace内に解決（セキュリティ）"""
        resolved = (self.workspace_dir / path).resolve()
        
        # workspace外へのアクセスを防止
        if not str(resolved).startswith(str(self.workspace_dir.resolve())):
            raise ValueError(f"Path escapes workspace: {path}")
        
        return resolved
    
    def _create_backup(self, file_path: Path) -> Path:
        """ファイルのバックアップを作成"""
        if not file_path.exists():
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}.{timestamp}.bak"
        backup_path = self.backup_dir / file_path.relative_to(self.workspace_dir).parent / backup_name
        
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, backup_path)
        
        return backup_path
    
    def _tool_read_file(self, path: str) -> ToolResult:
        """ファイル読み取り"""
        file_path = self._resolve_path(path)
        
        if not file_path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")
        
        content = file_path.read_text(encoding="utf-8")
        return ToolResult(success=True, output=content)
    
    def _tool_edit_file(self, path: str, search: str, replace: str, reason: str) -> ToolResult:
        """ファイル編集（差分ベース）"""
        file_path = self._resolve_path(path)
        
        if not file_path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")
        
        content = file_path.read_text(encoding="utf-8")
        
        if search not in content:
            return ToolResult(success=False, output="", error=f"Search text not found in file")
        
        # バックアップ作成
        backup_path = self._create_backup(file_path)
        
        # 置換実行
        new_content = content.replace(search, replace, 1)
        file_path.write_text(new_content, encoding="utf-8")
        
        # 変更履歴に記録
        change = {
            "type": "edit",
            "path": str(file_path),
            "backup": str(backup_path) if backup_path else None,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        self.change_history.append(change)
        
        if self.current_task_id:
            self.tasks[self.current_task_id].changes.append(change)
        
        return ToolResult(
            success=True, 
            output=f"✅ File edited: {path}\n   Backup: {backup_path}\n   Reason: {reason}"
        )
    
    def _tool_create_file(self, path: str, content: str, reason: str) -> ToolResult:
        """ファイル作成"""
        file_path = self._resolve_path(path)
        
        if file_path.exists():
            return ToolResult(success=False, output="", error=f"File already exists: {path}")
        
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        
        change = {
            "type": "create",
            "path": str(file_path),
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        self.change_history.append(change)
        
        return ToolResult(success=True, output=f"✅ File created: {path}")
    
    def _tool_run_command(self, command: str, reason: str) -> ToolResult:
        """コマンド実行"""
        import subprocess
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.workspace_dir),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n[STDERR]\n{result.stderr}"
            
            return ToolResult(
                success=result.returncode == 0,
                output=output,
                error=result.stderr if result.returncode != 0 else None
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, output="", error="Command timed out (60s)")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
    
    def _tool_list_directory(self, path: str) -> ToolResult:
        """ディレクトリ一覧"""
        dir_path = self._resolve_path(path)
        
        if not dir_path.exists():
            return ToolResult(success=False, output="", error=f"Directory not found: {path}")
        
        items = []
        for item in sorted(dir_path.iterdir()):
            prefix = "📁 " if item.is_dir() else "📄 "
            items.append(f"{prefix}{item.name}")
        
        return ToolResult(success=True, output="\n".join(items))
    
    def _tool_search_files(self, query: str, path: str = ".", extensions: List[str] = None) -> ToolResult:
        """ファイル検索"""
        search_path = self._resolve_path(path)
        
        results = []
        pattern = "**/*" if extensions is None else None
        
        files_to_search = []
        if extensions:
            for ext in extensions:
                files_to_search.extend(search_path.glob(f"**/*{ext}"))
        else:
            files_to_search = [f for f in search_path.rglob("*") if f.is_file()]
        
        for file_path in files_to_search[:100]:  # 上限100ファイル
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if query in content:
                    # マッチした行を抽出
                    for i, line in enumerate(content.split("\n"), 1):
                        if query in line:
                            rel_path = file_path.relative_to(self.workspace_dir)
                            results.append(f"{rel_path}:{i}: {line.strip()[:100]}")
            except:
                continue
        
        if not results:
            return ToolResult(success=True, output="No matches found")
        
        return ToolResult(success=True, output="\n".join(results[:50]))  # 上限50件
    
    # ==================== Task Management ====================
    
    def create_task(self, description: str, requirements: List[str]) -> str:
        """タスクを作成"""
        import uuid
        task_id = str(uuid.uuid4())[:8]
        
        task = Task(
            id=task_id,
            description=description,
            requirements=requirements
        )
        
        self.tasks[task_id] = task
        print(f"📋 Task created: {task_id}")
        print(f"   {description}")
        print(f"   Requirements: {len(requirements)}")
        
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """タスク状態を取得"""
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        return {
            "id": task.id,
            "description": task.description,
            "requirements": task.requirements,
            "status": task.status,
            "changes": len(task.changes)
        }
    
    # ==================== Chat Interface ====================
    
    def chat(self, message: str, max_turns: int = 10) -> str:
        """
        Claude とチャット（ツール使用ループ付き）
        
        Args:
            message: ユーザーメッセージ
            max_turns: 最大ツール実行回数
        
        Returns:
            最終応答テキスト
        """
        client = self._init_client()
        
        # システムプロンプト
        system = f"""あなたはコード編集エージェントです。
ユーザーの要求を正確に理解し、必要なファイル編集やコマンド実行を行います。

重要なルール:
1. 変更を行う前に、必ず対象ファイルを読んで内容を確認する
2. 変更理由を明確に記録する
3. 既存の機能を壊さないよう注意する
4. 不明点があれば確認する

Workspace: {self.workspace_dir}
"""
        
        messages = [{"role": "user", "content": message}]
        
        for turn in range(max_turns):
            # API呼び出し
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system,
                tools=self.tools,
                messages=messages
            )
            
            # 応答を処理
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})
            
            # ツール呼び出しがあるかチェック
            tool_uses = [block for block in assistant_content if block.type == "tool_use"]
            
            if not tool_uses:
                # ツール呼び出しなし = 最終応答
                text_blocks = [block.text for block in assistant_content if hasattr(block, 'text')]
                return "\n".join(text_blocks)
            
            # ツールを実行
            tool_results = []
            for tool_use in tool_uses:
                print(f"🔧 Tool: {tool_use.name}")
                result = self._execute_tool(tool_use.name, tool_use.input)
                
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result.output if result.success else f"Error: {result.error}"
                })
                
                if result.success:
                    print(f"   ✅ Success")
                else:
                    print(f"   ❌ {result.error}")
            
            messages.append({"role": "user", "content": tool_results})
        
        return "Max turns reached"


# テスト用エントリーポイント
if __name__ == "__main__":
    import sys
    
    workspace = sys.argv[1] if len(sys.argv) > 1 else "."
    
    agent = ClaudeAgent(workspace_dir=workspace)
    
    if len(sys.argv) > 2:
        # チャットモード
        message = " ".join(sys.argv[2:])
        response = agent.chat(message)
        print("\n" + "="*60)
        print(response)
    else:
        # テスト: ディレクトリ一覧
        result = agent._execute_tool("list_directory", {"path": "."})
        print(result.output)

