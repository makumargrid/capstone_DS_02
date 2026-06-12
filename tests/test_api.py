"""Phase 4 tests — Product API plumbing (no LLM, no pytest; RUNNER is faked)."""
import os, sys, json, time, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.app as api
from fastapi.testclient import TestClient
from tests.fixtures import pattern_box_ir


def _fake_runner(prompt, output_base_dir="outputs", interactive=False, run_id=None,
                 question_handler=None, **kwargs):
    """Deterministic stand-in for run_pipeline: writes a report + artifacts."""
    d = os.path.join(output_base_dir, f"run_{run_id}")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "report.html"), "w").write("<h1>APPROVED</h1>")
    json.dump({"ok": True}, open(os.path.join(d, "ir.json"), "w"))
    open(os.path.join(d, "APPROVED_ir.json"), "w").write("{}")
    return d


def _fake_question_runner(prompt, output_base_dir="outputs", interactive=False,
                          run_id=None, question_handler=None, **kwargs):
    """Fake runner that exercises the browser question bridge."""
    d = os.path.join(output_base_dir, f"run_{run_id}")
    os.makedirs(d, exist_ok=True)
    answer = question_handler("What diameter should the bore be?") if interactive else "not interactive"
    json.dump({"answer": answer}, open(os.path.join(d, "answer.json"), "w"))
    open(os.path.join(d, "report.html"), "w").write("<h1>APPROVED</h1>")
    open(os.path.join(d, "APPROVED_ir.json"), "w").write("{}")
    return d


def _setup(key=None):
    """Point the API at a temp dir + the fake runner. Returns (client, cleanup)."""
    d = tempfile.mkdtemp()
    api.RUNNER, api._OUT, api.RUNS = _fake_runner, d, {}
    if key:
        os.environ["HARNESS_API_KEY"] = key
    else:
        os.environ.pop("HARNESS_API_KEY", None)
    return TestClient(api.app)


def _wait(c, rid, headers=None):
    for _ in range(60):
        s = c.get(f"/designs/{rid}/status", headers=headers or {}).json()
        if s.get("state") not in ("queued", "running"):
            return s
        time.sleep(0.05)
    return s


def test_create_status_report_artifact():
    c = _setup()
    rid = c.post("/designs", json={"prompt": "a plate"}).json()["run_id"]
    s = _wait(c, rid)
    assert s["state"] == "approved" and s["report_url"], s
    assert c.get(f"/designs/{rid}/report").status_code == 200
    assert c.get(f"/designs/{rid}/artifacts/ir.json").json() == {"ok": True}


def test_path_traversal_blocked():
    c = _setup()
    rid = c.post("/designs", json={"prompt": "x"}).json()["run_id"]; _wait(c, rid)
    assert c.get(f"/designs/{rid}/artifacts/..%2f..%2fpipeline.py").status_code == 404


def test_missing_prompt_422():
    assert _setup().post("/designs", json={}).status_code == 422


def test_unknown_run_404():
    assert _setup().get("/designs/nope/status").status_code == 404


def test_api_key_enforced():
    c = _setup(key="secret")
    assert c.post("/designs", json={"prompt": "x"}).status_code == 401
    assert c.post("/designs", json={"prompt": "x"}, headers={"x-api-key": "secret"}).status_code == 200
    os.environ.pop("HARNESS_API_KEY", None)


def test_interactive_run_waits_for_browser_answer():
    c = _setup()
    api.RUNNER = _fake_question_runner
    rid = c.post("/designs", json={"prompt": "a plate", "interactive": True}).json()["run_id"]
    waiting = None
    for _ in range(60):
        s = c.get(f"/designs/{rid}/status").json()
        if s.get("state") == "waiting_for_user":
            waiting = s
            break
        time.sleep(0.05)
    assert waiting and waiting["pending_question"]["question"] == "What diameter should the bore be?"
    qid = waiting["pending_question"]["id"]

    r = c.post(f"/designs/{rid}/answer", json={"question_id": qid, "answer": "12 mm"})

    assert r.status_code == 200
    s = _wait(c, rid)
    assert s["state"] == "approved"
    assert c.get(f"/designs/{rid}/artifacts/answer.json").json()["answer"] == "12 mm"


def test_answer_rejects_wrong_question_id():
    c = _setup()
    api.RUNNER = _fake_question_runner
    rid = c.post("/designs", json={"prompt": "a plate", "interactive": True}).json()["run_id"]
    for _ in range(60):
        s = c.get(f"/designs/{rid}/status").json()
        if s.get("state") == "waiting_for_user":
            break
        time.sleep(0.05)

    assert c.post(f"/designs/{rid}/answer",
                  json={"question_id": "wrong", "answer": "12 mm"}).status_code == 409


def test_iterate_starts_child_run():
    c = _setup()
    rid = c.post("/designs", json={"prompt": "a plate"}).json()["run_id"]; _wait(c, rid)
    r = c.post(f"/designs/{rid}/iterate", json={"feedback": "make it taller"})
    assert r.status_code == 200 and r.json()["parent"] == rid
    child = r.json()["run_id"]; s = _wait(c, child)
    assert s["state"] in ("approved", "completed")


def test_approve_records_acceptance():
    import os, json as _j
    c = _setup()
    rid = c.post("/designs", json={"prompt": "a plate"}).json()["run_id"]; _wait(c, rid)
    r = c.post(f"/designs/{rid}/approve", json={"accepted": False, "note": "wrong size"})
    assert r.status_code == 200 and r.json()["accepted"] is False
    rec = _j.load(open(os.path.join(api.RUNS[rid]["dir"], "10_acceptance_record.json")))
    assert rec["accepted"] is False and rec["accepted_by"] == "api"


def test_ws_stream_reaches_terminal():
    c = _setup()
    rid = c.post("/designs", json={"prompt": "a plate"}).json()["run_id"]
    states = []
    with c.websocket_connect(f"/ws/designs/{rid}/stream") as ws:
        for _ in range(200):  # artifact-change frames can be many; read until terminal
            f = ws.receive_json(); states.append(f["state"])
            if f["state"] in ("approved", "completed", "failed"):
                break
    assert states[-1] in ("approved", "completed")


def test_recompile_valid_ir():
    c = _setup()
    r = c.post("/recompile", json={"ir": pattern_box_ir()}).json()
    assert r["valid"] and r["stl_b64"] and r["stage"] == "verify"


def test_recompile_invalid_ir():
    c = _setup()
    bad = pattern_box_ir(); del bad["features"][0]["params"]["r_base"]
    r = c.post("/recompile", json={"ir": bad}).json()
    assert r["valid"] is False and r["stage"] == "validate"


def test_recompile_missing_ir_422():
    assert _setup().post("/recompile", json={}).status_code == 422


def test_viewer_served():
    c = _setup()
    rid = c.post("/designs", json={"prompt": "a plate"}).json()["run_id"]; _wait(c, rid)
    r = c.get(f"/designs/{rid}/viewer")
    assert r.status_code == 200 and "ForgeCAD" in r.text and "/recompile" in r.text


def test_log_endpoint():
    c = _setup()
    rid = c.post("/designs", json={"prompt": "a plate"}).json()["run_id"]; _wait(c, rid)
    r = c.get(f"/designs/{rid}/log")
    assert r.status_code == 200 and "log" in r.json() and "state" in r.json()


def test_webui_served():
    c = _setup()
    assert c.get("/ui/index.html").status_code == 200
    assert "New design" in c.get("/ui/index.html").text
    assert c.get("/ui/run.html").status_code == 200
    js = c.get("/ui/static/run.js")
    assert js.status_code == 200 and "WebSocket" in js.text
    assert c.get("/ui/static/style.css").status_code == 200


def test_root_redirects_to_ui():
    c = _setup()
    r = c.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and "/ui/index.html" in r.headers.get("location", "")


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1; print(f"FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
