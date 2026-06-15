"""
api/app.py — the Product API: an HTTP service over the pipeline (Phase 4).

WHAT: turns the CLI engine into a usable service. Endpoints:
  POST /designs                      → start a design run in the background → {run_id}
  GET  /designs                      → list runs + states
  GET  /designs/{id}/status          → state, verdict, available artifacts, report_url
  GET  /designs/{id}/report          → the run's report.html (the visible summary)
  GET  /designs/{id}/artifacts/{name}→ a run artifact (ir.json / model.stl / step / manifest …)
CALLED BY: `uvicorn api.app:app` (or any ASGI host); the ForgeCAD UI (Phase 5).
CALLS: pipeline.run_pipeline (the whole agentic loop). `RUNNER` is module-level so
       tests can substitute a fast, LLM-free fake.

SECURITY: a network endpoint. If env HARNESS_API_KEY is set, every request must send
          header `x-api-key`. If it is UNSET the API is OPEN (local-dev only) — set the
          key before exposing this anywhere. (Auth/RBAC hardening is Phase 8.)
"""
from __future__ import annotations
import os
import uuid
import threading
import time

import json
import asyncio
from fastapi import FastAPI, Header, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from api.recompile import recompile_ir
from api.viewer import viewer_html

from core.env import bootstrap_env
from pipeline import run_pipeline
from core.logger import get_agent_logger

bootstrap_env()

app = FastAPI(title="Geometry Agent Harness API", version="1.0")

# Web UI (webui/) — the single front door: dashboard + run page (Phase 6).
# Thin static glue that reuses these API endpoints + the report.html + /viewer.
import os as _os
_WEBUI = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "webui")
if _os.path.isdir(_WEBUI):
    app.mount("/ui", StaticFiles(directory=_WEBUI, html=True), name="ui")


@app.get("/")
def _root():
    return RedirectResponse("/ui/index.html")
log = get_agent_logger()

RUNNER = run_pipeline            # overridable in tests (LLM-free fake)
_OUT = "outputs"                 # base output dir (overridable in tests)
RUNS: dict[str, dict] = {}       # run_id → {state, dir, prompt, error}
_RUN_LOCK = threading.RLock()
_QUESTION_TIMEOUT_S = 300


def _auth(x_api_key: str | None = Header(default=None)) -> None:
    """Require x-api-key only when HARNESS_API_KEY is configured."""
    key = os.environ.get("HARNESS_API_KEY")
    if key and x_api_key != key:
        raise HTTPException(status_code=401, detail="invalid or missing x-api-key")


def _question_handler(rid: str):
    """Return a blocking planner question handler backed by /answer.
    Answered Q&A pairs are appended to RUNS[rid]['qa_history'] so that
    iterate() can carry context forward to child runs."""
    def ask(question: str) -> str:
        qid = uuid.uuid4().hex[:12]
        deadline = time.monotonic() + _QUESTION_TIMEOUT_S
        with _RUN_LOCK:
            r = RUNS.get(rid)
            if not r:
                return "Run was no longer available; proceed with best engineering judgment."
            cond = r.setdefault("condition", threading.Condition(_RUN_LOCK))
            r["state"] = "waiting_for_user"
            r["pending_question"] = {"id": qid, "question": question}
            r["answer"] = None
            cond.notify_all()
            while True:
                answer = r.get("answer")
                if answer and answer.get("question_id") == qid:
                    text = answer.get("answer") or ""
                    r["answer"] = None
                    r["pending_question"] = None
                    r["state"] = "running"
                    # Persist Q&A so iterate() can carry context forward
                    r.setdefault("qa_history", []).append({"q": question, "a": text})
                    return text
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    r["answer"] = None
                    r["pending_question"] = None
                    r["state"] = "running"
                    return ("No browser answer arrived in time; proceed with best "
                            "engineering judgment based on the prompt.")
                cond.wait(timeout=min(remaining, 1.0))
    return ask


def _run(rid: str, prompt: str, interactive: bool, parent_session_id: str | None = None) -> None:
    """Background worker: run the pipeline, then mark approved/completed/failed."""
    with _RUN_LOCK:
        if rid not in RUNS:
            return
        RUNS[rid]["state"] = "running"
    try:
        RUNNER(prompt, output_base_dir=_OUT, interactive=interactive, run_id=rid,
               question_handler=_question_handler(rid) if interactive else None,
               parent_session_id=parent_session_id)
        with _RUN_LOCK:
            if rid not in RUNS:
                return
            d = RUNS[rid]["dir"]
        approved = (os.path.exists(os.path.join(d, "APPROVED_ir.json"))
                    or os.path.exists(os.path.join(d, "APPROVED_assembly.json")))
        with _RUN_LOCK:
            if rid in RUNS:
                RUNS[rid]["state"] = "approved" if approved else "completed"
                RUNS[rid]["pending_question"] = None
    except Exception as e:  # surface, never crash the service
        with _RUN_LOCK:
            if rid in RUNS:
                RUNS[rid]["state"] = "failed"
                RUNS[rid]["error"] = str(e)
                RUNS[rid]["pending_question"] = None
        log.error(f"[API] run {rid} failed: {e}")


@app.post("/designs")
def create_design(body: dict, _=Depends(_auth)):
    """Start a design run. Body: {"prompt": str, "interactive": bool?}."""
    prompt = (body or {}).get("prompt")
    if not prompt:
        raise HTTPException(status_code=422, detail="missing 'prompt'")
    rid = uuid.uuid4().hex[:12]
    with _RUN_LOCK:
        RUNS[rid] = {"state": "queued", "dir": os.path.join(_OUT, f"run_{rid}"),
                     "prompt": prompt, "error": None, "pending_question": None,
                     "answer": None, "qa_history": [],
                     "condition": threading.Condition(_RUN_LOCK)}
    threading.Thread(target=_run, args=(rid, prompt, bool((body or {}).get("interactive"))),
                     daemon=True).start()
    return {"run_id": rid, "status_url": f"/designs/{rid}/status"}


@app.get("/designs")
def list_designs(_=Depends(_auth)):
    with _RUN_LOCK:
        runs = [{"run_id": k, "state": v["state"], "prompt": v["prompt"][:80]}
                for k, v in RUNS.items()]
    return {"runs": runs}


@app.get("/designs/{rid}/status")
def status(rid: str, _=Depends(_auth)):
    with _RUN_LOCK:
        r = dict(RUNS.get(rid) or {})
    if not r:
        raise HTTPException(status_code=404, detail="unknown run_id")
    arts = sorted(os.listdir(r["dir"])) if os.path.isdir(r["dir"]) else []
    return {"run_id": rid, "state": r["state"], "error": r.get("error"),
            "report_url": f"/designs/{rid}/report" if "report.html" in arts else None,
            "artifacts": arts, "pending_question": r.get("pending_question"),
            "qa_history": r.get("qa_history", [])}


@app.get("/designs/{rid}/log")
def run_log(rid: str, _=Depends(_auth)):
    """Tail of the run's pipeline log + current state (drives the UI live log)."""
    with _RUN_LOCK:
        r = dict(RUNS.get(rid) or {})
    if not r:
        raise HTTPException(status_code=404, detail="unknown run_id")
    path = os.path.join(r["dir"], "00_pipeline_execution.log")
    text = open(path).read()[-40000:] if os.path.exists(path) else ""
    return {"run_id": rid, "state": r["state"], "error": r.get("error"), "log": text,
            "pending_question": r.get("pending_question")}


@app.get("/designs/{rid}/report")
def report(rid: str, _=Depends(_auth)):
    r = RUNS.get(rid) or {}
    path = os.path.join(r.get("dir", ""), "report.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="no report yet")
    return FileResponse(path, media_type="text/html")


@app.get("/designs/{rid}/artifacts/{name:path}")
def artifact(rid: str, name: str, _=Depends(_auth)):
    d = (RUNS.get(rid) or {}).get("dir")
    if not d:
        raise HTTPException(status_code=404, detail="unknown run_id")
    path = os.path.normpath(os.path.join(d, name))
    if not path.startswith(os.path.normpath(d) + os.sep) or not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="artifact not found")  # blocks path traversal
    return FileResponse(path)


# ── Phase 4b — iterate (re-run seeded with feedback) + approve (human gate) ──
@app.post("/designs/{rid}/iterate")
def iterate(rid: str, body: dict, _=Depends(_auth)):
    """Start a NEW run seeded from a prior run's prompt + revision feedback.

    Prior Q&A history is injected as context so the planner does not re-ask
    questions the user already answered. The child run is interactive so the
    planner CAN ask about genuinely new unknowns introduced by the revision.
    """
    with _RUN_LOCK:
        parent = dict(RUNS.get(rid) or {})
    if not parent:
        raise HTTPException(status_code=404, detail="unknown run_id")

    feedback = (body or {}).get("feedback", "")
    qa_history = parent.get("qa_history", [])

    # Build context prefix from prior Q&A so planner skips re-asking.
    # Use unique delimiters (<<<QA_START>>>...<<<QA_END>>>) so _design_prompt() can
    # strip the block reliably even when question text contains blank lines (\n\n).
    context_prefix = ""
    if qa_history:
        qa_block = "<<<QA_START>>> (user already answered — do NOT re-ask)\n"
        for item in qa_history:
            qa_block += f"Q: {item['q']}\nA: {item['a']}\n---\n"
        qa_block += "<<<QA_END>>>\n"
        context_prefix = qa_block

    original_prompt = parent.get("prompt", "")
    # Strip any previously injected Q&A / revision context from the parent prompt
    # so we don't stack context blocks on nested iterates.
    if "<<<QA_START>>>" in original_prompt:
        idx = original_prompt.find("<<<QA_END>>>")
        if idx != -1:
            original_prompt = original_prompt[idx + len("<<<QA_END>>>"):].strip()
    # Legacy format (PRIOR Q&A CONTEXT) — handle old runs gracefully
    if "PRIOR Q&A CONTEXT" in original_prompt:
        parts = original_prompt.split("\n\n")
        parts = [p for p in parts if not p.startswith("PRIOR Q&A CONTEXT")]
        original_prompt = "\n\n".join(parts).strip()
    if "REVISION REQUESTED:" in original_prompt:
        original_prompt = original_prompt.split("REVISION REQUESTED:")[0].strip()

    # Read parent run's planner session_id for ADK session continuity
    parent_dir = parent.get("dir", "")
    parent_session_id = None
    session_id_path = os.path.join(parent_dir, "planner_session_id.txt")
    if os.path.isfile(session_id_path):
        try:
            with open(session_id_path) as _f:
                parent_session_id = _f.read().strip() or None
        except Exception:
            pass

    new_prompt = f"{context_prefix}{original_prompt}\n\nREVISION REQUESTED: {feedback}"
    nid = uuid.uuid4().hex[:12]
    with _RUN_LOCK:
        RUNS[nid] = {"state": "queued", "dir": os.path.join(_OUT, f"run_{nid}"),
                     "prompt": new_prompt, "error": None, "parent": rid,
                     "pending_question": None, "answer": None, "qa_history": [],
                     "condition": threading.Condition(_RUN_LOCK)}
    # interactive=True + parent_session_id for full ADK context continuity
    threading.Thread(target=_run, args=(nid, new_prompt, True, parent_session_id),
                     daemon=True).start()
    return {"run_id": nid, "parent": rid, "status_url": f"/designs/{nid}/status"}


@app.post("/designs/{rid}/answer")
def answer_question(rid: str, body: dict, _=Depends(_auth)):
    """Resume an interactive run by answering the planner's pending question."""
    qid = (body or {}).get("question_id")
    answer = (body or {}).get("answer")
    if not qid or answer is None:
        raise HTTPException(status_code=422, detail="missing question_id or answer")
    with _RUN_LOCK:
        r = RUNS.get(rid)
        if not r:
            raise HTTPException(status_code=404, detail="unknown run_id")
        pending = r.get("pending_question")
        if r.get("state") != "waiting_for_user" or not pending:
            raise HTTPException(status_code=409, detail="run is not waiting for an answer")
        if pending.get("id") != qid:
            raise HTTPException(status_code=409, detail="answer question_id does not match")
        r["answer"] = {"question_id": qid, "answer": str(answer)}
        r["pending_question"] = None
        r["state"] = "running"
        cond = r.get("condition")
        if cond:
            cond.notify_all()
    return {"run_id": rid, "answered": True}


@app.post("/designs/{rid}/approve")
def approve(rid: str, body: dict, _=Depends(_auth)):
    """Human acceptance over HTTP: record accept/reject for a finished run."""
    with _RUN_LOCK:
        r = dict(RUNS.get(rid) or {})
    if not r:
        raise HTTPException(status_code=404, detail="unknown run_id")
    if r["state"] not in ("approved", "completed"):
        raise HTTPException(status_code=409, detail=f"run is '{r['state']}', not reviewable yet")
    accepted = bool((body or {}).get("accepted", True))
    rec_path = os.path.join(r["dir"], "10_acceptance_record.json")
    rec = {}
    if os.path.exists(rec_path):
        rec = json.load(open(rec_path))
    rec.update({"accepted": accepted, "accepted_by": "api", "note": (body or {}).get("note")})
    json.dump(rec, open(rec_path, "w"), indent=2)
    # Regenerate report.html to reflect the accepted/rejected state prominently
    try:
        from reporting import build_report
        build_report(r["dir"])
    except Exception:
        pass
    return {"run_id": rid, "accepted": accepted, "accepted_by": "api"}


# ── Phase detection helper ──────────────────────────────────────────────────
def _detect_phase(artifacts: list[str], state: str) -> str:
    """Determine the current pipeline phase from state + artifact names."""
    if state == "failed":
        return "failed"
    if state in ("approved", "completed"):
        return "done"
    if state == "waiting_for_user":
        # Check what's been produced to know *which* wait
        if any(a.startswith("07_") for a in artifacts):
            return "review"
        if any(a.startswith("05_") for a in artifacts):
            return "inspect"
        if any("ir.json" in a for a in artifacts):
            return "plan"
        return "intent"
    # state == "running"
    if any(a.startswith("07_") and "reviewer_verdict" in a for a in artifacts):
        return "review"
    if any(a.startswith("05_") and "solid_inspection" in a for a in artifacts):
        return "inspect"
    if any(a.startswith("04_") and "model" in a for a in artifacts):
        return "compile"
    if any("ir.json" in a for a in artifacts):
        return "plan"
    return "intent"


# ── Phase 4c — live progress stream ─────────────────────────────────────────
@app.websocket("/ws/designs/{rid}/stream")
async def stream(ws: WebSocket, rid: str):
    """Stream enriched status frames until the run reaches a terminal state."""
    await ws.accept()
    try:
        last = None
        while True:
            with _RUN_LOCK:
                r = dict(RUNS.get(rid) or {})
            if not r:
                await ws.send_json({"error": "unknown run_id"}); break
            d = r["dir"]
            arts = sorted(os.listdir(d)) if os.path.isdir(d) else []
            phase = _detect_phase(arts, r["state"])
            frame = {
                "run_id": rid,
                "state": r["state"],
                "phase": phase,
                "artifacts": arts,
                "pending_question": r.get("pending_question"),
                "qa_history": r.get("qa_history", []),
                "error": r.get("error"),
                "report_url": f"/designs/{rid}/report" if "report.html" in arts else None,
            }
            if frame != last:
                await ws.send_json(frame); last = frame
            if r["state"] in ("approved", "completed", "failed"):
                break
            await asyncio.sleep(0.3)
    except WebSocketDisconnect:
        return
    finally:
        try:
            await ws.close()
        except Exception:
            pass


# ── Phase 5 — ForgeCAD viewer + edit→recompile round-trip ───────────────────
@app.get("/designs/{rid}/viewer", response_class=HTMLResponse)
def viewer(rid: str, _=Depends(_auth)):
    if rid not in RUNS:
        raise HTTPException(status_code=404, detail="unknown run_id")
    return viewer_html(rid)


@app.post("/recompile")
def recompile(body: dict, _=Depends(_auth)):
    """Recompile + re-verify an edited IR (stateless). Returns checks + new STL b64."""
    ir = (body or {}).get("ir")
    if not isinstance(ir, dict):
        raise HTTPException(status_code=422, detail="missing 'ir' object")
    return recompile_ir(ir)


# ── Prompt 10 — Image intake endpoint ────────────────────────────────────────
@app.get("/designs/{rid}/reference-image")
def get_reference_status(rid: str, _=Depends(_auth)):
    """Check if a reference image exists for a session."""
    with _RUN_LOCK:
        r = dict(RUNS.get(rid) or {})
    if not r:
        raise HTTPException(status_code=404, detail="unknown run_id")
    from interaction.image_intake import has_reference_image
    return {"has_reference": has_reference_image(r["dir"])}
