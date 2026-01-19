"""
Advanced Proofing System - FastAPI Backend
REST API エンドポイント

Created: 2026-01-11
"""
import sys
from pathlib import Path

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import json
import shutil


# ========== Pydantic Models ==========

class IngestWebRequest(BaseModel):
    url: str
    run_id: Optional[str] = None
    storage_state: Optional[str] = None
    wait_ms: int = 2000


class IngestPDFRequest(BaseModel):
    pdf_path: str
    run_id: Optional[str] = None
    page_range: Optional[tuple] = None


class ProofingRequest(BaseModel):
    left_source: str
    right_source: str
    left_type: str = "auto"  # web, pdf, auto
    right_type: str = "auto"
    export_xlsx: bool = True


class IssueUpdateRequest(BaseModel):
    status: Optional[str] = None  # OPEN, CONFIRMED, RESOLVED, IGNORED
    reviewer: Optional[str] = None
    comment: Optional[str] = None


class MatchOverrideRequest(BaseModel):
    left_id: str
    right_id: str


# ========== App Setup ==========

app = FastAPI(
    title="Advanced Proofing System API",
    description="Web/PDF広告検版システム REST API",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (本番ではDB使用)
runs_store: Dict[str, Dict[str, Any]] = {}
issues_store: Dict[str, Dict[str, Any]] = {}


# ========== Endpoints ==========

@app.get("/")
async def root():
    return {
        "name": "Advanced Proofing System",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# --- Ingest ---

@app.post("/api/ingest/web")
async def ingest_web(request: IngestWebRequest, background_tasks: BackgroundTasks):
    """Webページを取り込み"""
    import urllib.request
    from urllib.error import URLError
    
    run_id = request.run_id or str(uuid.uuid4())[:8]
    
    try:
        # Playwright版を試行
        from app.pipeline.ingest_web import WebIngestor, PLAYWRIGHT_AVAILABLE
        
        if PLAYWRIGHT_AVAILABLE:
            try:
                async with WebIngestor() as ingestor:
                    result = await ingestor.capture(
                        url=request.url,
                        run_id=run_id,
                        storage_state=request.storage_state,
                        wait_ms=request.wait_ms
                    )
                
                runs_store[run_id] = {
                    "run_id": run_id,
                    "type": "web",
                    "url": request.url,
                    "title": result.title,
                    "status": "completed" if not result.error else "failed",
                    "screenshot_path": result.screenshot_path,
                    "dom_text_length": len(result.dom_text),
                    "dom_text_preview": result.dom_text[:500] if result.dom_text else "",
                    "error": result.error,
                    "created_at": datetime.now().isoformat()
                }
                return runs_store[run_id]
            except Exception as pw_err:
                # Playwright失敗時はHTTPフォールバック
                pass
        
        # HTTPフォールバック
        req = urllib.request.Request(request.url, headers={"User-Agent": "ProofingBot/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            html = response.read().decode('utf-8', errors='ignore')
            # 簡易テキスト抽出
            import re
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            
            # タイトル抽出
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
            title = title_match.group(1) if title_match else ""
        
        runs_store[run_id] = {
            "run_id": run_id,
            "type": "web",
            "url": request.url,
            "title": title,
            "status": "completed",
            "screenshot_path": None,
            "dom_text_length": len(text),
            "dom_text_preview": text[:500],
            "error": None,
            "method": "http_fallback",
            "created_at": datetime.now().isoformat()
        }
        return runs_store[run_id]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest/pdf")
async def ingest_pdf(request: IngestPDFRequest):
    """PDFを取り込み"""
    run_id = request.run_id or str(uuid.uuid4())[:8]
    
    try:
        from app.pipeline.ingest_pdf import capture_pdf
        
        result = capture_pdf(
            pdf_path=request.pdf_path,
            run_id=run_id
        )
        
        runs_store[run_id] = {
            "run_id": run_id,
            "type": "pdf",
            "pdf_path": request.pdf_path,
            "status": "completed" if not result.error else "failed",
            "total_pages": result.total_pages,
            "error": result.error,
            "created_at": datetime.now().isoformat()
        }
        
        return runs_store[run_id]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Proofing ---

@app.post("/api/proofing/run")
async def run_proofing(request: ProofingRequest):
    """検版パイプラインを実行"""
    try:
        from app.pipeline.orchestrator import ProofingPipeline
        
        pipeline = ProofingPipeline()
        result = pipeline.run(
            left_source=request.left_source,
            right_source=request.right_source,
            left_type=request.left_type,
            right_type=request.right_type,
            export_xlsx=request.export_xlsx
        )
        
        # Issue保存
        for issue in result.issues:
            issue_id = issue.get("issue_id", str(uuid.uuid4()))
            issues_store[issue_id] = {
                **issue,
                "run_id": result.run_id
            }
        
        return {
            "run_id": result.run_id,
            "total_elements": result.total_elements,
            "matched_count": result.matched_count,
            "issue_count": result.issue_count,
            "critical_count": result.critical_count,
            "major_count": result.major_count,
            "minor_count": result.minor_count,
            "export_path": result.export_path,
            "error": result.error
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Issues ---

@app.get("/api/issues")
async def list_issues(
    run_id: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
):
    """Issue一覧を取得"""
    issues = list(issues_store.values())
    
    # フィルタ
    if run_id:
        issues = [i for i in issues if i.get("run_id") == run_id]
    if severity:
        issues = [i for i in issues if i.get("severity") == severity]
    if status:
        issues = [i for i in issues if i.get("status") == status]
    
    # ソート（重大度順）
    severity_order = {"CRITICAL": 0, "MAJOR": 1, "MINOR": 2, "INFO": 3}
    issues.sort(key=lambda x: severity_order.get(x.get("severity", "INFO"), 99))
    
    return {"issues": issues[:limit], "total": len(issues)}


@app.get("/api/issues/{issue_id}")
async def get_issue(issue_id: str):
    """Issue詳細を取得"""
    if issue_id not in issues_store:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issues_store[issue_id]


@app.patch("/api/issues/{issue_id}")
async def update_issue(issue_id: str, request: IssueUpdateRequest):
    """Issueを更新"""
    if issue_id not in issues_store:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    issue = issues_store[issue_id]
    
    if request.status:
        issue["status"] = request.status
    if request.reviewer:
        issue["reviewer"] = request.reviewer
    if request.comment:
        issue["comment"] = request.comment
    
    issue["updated_at"] = datetime.now().isoformat()
    
    return issue


# --- Queue ---

@app.get("/api/queue")
async def get_review_queue(
    run_id: Optional[str] = None,
    limit: int = 50
):
    """Review Queueを取得（重大度・リスク順にソート）"""
    issues = list(issues_store.values())
    
    # OPENのみ
    issues = [i for i in issues if i.get("status") == "OPEN"]
    
    if run_id:
        issues = [i for i in issues if i.get("run_id") == run_id]
    
    # ソート: 重大度 desc → スコア low asc
    severity_order = {"CRITICAL": 0, "MAJOR": 1, "MINOR": 2, "INFO": 3}
    issues.sort(key=lambda x: (
        severity_order.get(x.get("severity", "INFO"), 99),
        x.get("score_total", 1.0)
    ))
    
    return {"queue": issues[:limit], "total": len(issues)}


# --- Match Override ---

@app.post("/api/matches/override")
async def override_match(request: MatchOverrideRequest):
    """マッチングを上書き"""
    # 本番ではDB更新
    return {
        "status": "overridden",
        "left_id": request.left_id,
        "right_id": request.right_id
    }


# --- Export ---

@app.get("/api/export/{run_id}")
async def export_results(run_id: str, format: str = "xlsx"):
    """結果をエクスポート"""
    try:
        from app.pipeline.spreadsheet_exporter import export_issues
        
        issues = [i for i in issues_store.values() if i.get("run_id") == run_id]
        
        if not issues:
            raise HTTPException(status_code=404, detail="No issues found for this run")
        
        result = export_issues(issues, run_id, format=format)
        
        if result.error:
            raise HTTPException(status_code=500, detail=result.error)
        
        return FileResponse(
            result.file_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=Path(result.file_path).name
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Evidence ---

@app.get("/api/evidence/{evidence_id}")
async def get_evidence(evidence_id: str):
    """Evidence画像を取得"""
    # 本番ではpathを検索
    return {"evidence_id": evidence_id, "status": "not_implemented"}


# --- Dataset (Human-in-the-loop) ---

@app.post("/api/dataset/feedback")
async def save_feedback(feedback: Dict[str, Any]):
    """Human feedbackを保存"""
    storage_path = Path("storage/datasets")
    storage_path.mkdir(parents=True, exist_ok=True)
    
    feedback_file = storage_path / "feedback.jsonl"
    
    with open(feedback_file, "a", encoding="utf-8") as f:
        feedback["timestamp"] = datetime.now().isoformat()
        f.write(json.dumps(feedback, ensure_ascii=False) + "\n")
    
    return {"status": "saved", "feedback_id": str(uuid.uuid4())}


# ========== Main ==========

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
