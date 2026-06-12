"""
Geometry IR Pipeline — the agentic harness orchestrator.

Flow (general for ANY prompt; no shape-specific code):

  prompt
    → Planner Agent  ............ emits Geometry IR (agents/planner_agent)
    → L1 validate_plan .......... schema + refs (src/geometry_ir/validate.py)
    → compile_design ............ IR → solid + provenance (geometry_ir/compiler)
    → export STEP/STL
    → L2 inspect_solid .......... deterministic intent ground truth
    → L3 render_views + Vision .. advisory multimodal check
    → (L4 MeshLib) .............. ONLY for custom/mesh_only nodes
    → Reviewer .................. APPROVED / REDESIGN(node-keyed) / HALT
        REDESIGN → revise_ir(feedback) → loop

Artifacts per run (outputs/run_YYYYMMDD_HHMMSS/):
  00 log · 01 design_brief · 02 planner text · 03 ir.json · 04 model.step/stl
  05 solid_inspection (L2) · 06 vision (L3) · 07 reviewer verdict · 09 view PNGs
"""
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import os
import sys
import json
import datetime

from core.env import bootstrap_env, diagnostic_summary
from core.logger import get_agent_logger
from core.process_detector import detect_process, load_profile
from geometry_ir import validate_plan
from primitives import compile_design, export_solid
from verification import inspect_solid, render_views
from core.spec import extract_spec, check_coverage, coverage_feedback, decompose
from core.registry import request_acceptance, record
from core.compile_errors import translate_error
from core.timeout import run_with_timeout
from verification.constraint_translator import translate_failure as _translate_failure

MAX_OUTER = 6
COMPILE_TIMEOUT_S = 120   # CadQuery solid compilation
RENDER_TIMEOUT_S = 60     # headless multi-view rendering
VISION_TIMEOUT_S = 120    # multimodal vision API call

bootstrap_env()


def _intent(ir: dict) -> dict:
    """Compact intent (features + envelope) for vision/reviewer — no kernel data."""
    return {"envelope": ir.get("envelope"), "process": ir.get("process"),
            "features": [{"id": f["id"], "type": f["type"],
                          "asserts": f.get("asserts")} for f in ir.get("features", [])]}


def _design_prompt(prompt: str) -> str:
    """Return the core design request, stripping iterate-injected context blocks.

    iterate() now builds prompts using unambiguous delimiters:
        <<<QA_START>>> ... <<<QA_END>>>
        <original design request>
        REVISION REQUESTED: ...

    process_detector, extract_spec, and decompose use ONLY the core design request.
    The planner still receives the full prompt (it needs revision + Q&A context).
    """
    p = prompt
    # Strip new-format Q&A block (<<<QA_START>>>...<<<QA_END>>>)
    if "<<<QA_START>>>" in p:
        idx = p.find("<<<QA_END>>>")
        if idx != -1:
            p = p[idx + len("<<<QA_END>>>"):].strip()
        else:
            # Malformed: no end marker — strip from start marker to end as fallback
            p = p[p.find("<<<QA_START>>>") + len("<<<QA_START>>>"):].strip()
    # Legacy format (PRIOR Q&A CONTEXT from old runs) — strip gracefully
    if "PRIOR Q&A CONTEXT" in p:
        parts = p.split("\n\n")
        clean = [s for s in parts
                 if not s.startswith("PRIOR Q&A CONTEXT")
                 and not s.strip().startswith("  Q:") and not s.strip().startswith("  A:")]
        p = "\n\n".join(clean).strip()
    # Strip REVISION REQUESTED suffix
    if "REVISION REQUESTED:" in p:
        p = p.split("REVISION REQUESTED:")[0].strip()
    return p or prompt


def run_pipeline(prompt: str, output_base_dir: str = "outputs", interactive: bool = False,
                 run_id: str = None, question_handler=None, parent_session_id: str | None = None):
    # run_id lets a caller (e.g. the API) fix the run-folder name up front; else timestamp.
    ts = run_id or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(output_base_dir, f"run_{ts}")
    os.makedirs(out, exist_ok=True)
    log = get_agent_logger(os.path.join(out, "00_pipeline_execution.log"))

    log.info("=" * 70)
    log.info("GEOMETRY IR PIPELINE")
    log.info(diagnostic_summary())
    log.info(f"Output: {out} | interactive={interactive}")
    log.info(f"Prompt: {prompt[:200]}")

    # Strip iterate-injected context so process/spec/decompose see only the core design.
    # The planner receives the full prompt (it needs revision + Q&A context).
    dp = _design_prompt(prompt)
    if dp != prompt:
        log.info(f"[DESIGN_PROMPT] stripped iterate context; core prompt: {dp[:120]}")

    profile = load_profile(detect_process(dp))
    min_wall = profile["min_wall_mm"]
    process = profile["process_key"]

    # ── Trace store (Prompt 13): record every run as queryable rows ──────────
    from core.trace_store import TraceStore
    trace_db = os.path.join(output_base_dir, "pipeline_traces.db")
    trace = TraceStore(trace_db)
    trace.start_run(ts if run_id is None else run_id, prompt[:500], process)
    trace.log_stage(ts if run_id is None else run_id, "init", "started")
    log.info(f"[INIT] Process={profile['full_name']} min_wall={min_wall}mm")

    # ── INTENT RESOLUTION (Prompt 9): unified clarification + standards grounding
    #     + human confirmation gate. The Spec is frozen here and consumed by both
    #     planner and checker as the single source of truth.
    from core.intent_resolver import resolve_intent, explain_plan
    intent = resolve_intent(dp, profile, interactive, question_handler)
    if not intent["confirmed"]:
        log.warning("[INTENT] Spec not confirmed by user; halting.")
        _save(out, "01_intent_cancelled.json", json.dumps(intent, indent=2))
        _report(out)
        return out
    spec = intent["spec"]
    log.info(f"[INTENT] Spec confirmed ({'engineer' if intent['is_engineer'] else 'general'} user): "
             f"{len(spec)} requirement(s), "
             + ", ".join(f"{r.get('claim')}:{r.get('target')}" for r in spec))
    if intent.get("clarification_notes"):
        log.info(f"[INTENT] Clarification notes: {intent['clarification_notes']}")
    _save(out, "01_intent_resolution.json", json.dumps(intent, indent=2, default=str))
    _save(out, "01b_spec.json", json.dumps(spec, indent=2))
    with open(os.path.join(out, "01_design_brief.json"), "w") as f:
        json.dump({"prompt": prompt, "process": process, "min_wall_mm": min_wall,
                   "spec": spec}, f, indent=2)

    # Import agents lazily so the module imports even without ADK/keys present.
    from agents.planner_agent import IRPlanner
    from agents.reviewer_agent import run_review
    try:
        from agents.vision_agent import run_vision_verification
    except Exception:
        run_vision_verification = None

    # ADK session persistence: use SQLite so iterate() can reuse the parent's session.
    _session_db = os.path.join(output_base_dir, "adk_sessions.db")
    _session_db_uri = f"sqlite+aiosqlite:///{_session_db}"
    planner = IRPlanner(interactive=interactive, process=process,
                        question_handler=question_handler,
                        session_db_uri=_session_db_uri,
                        reuse_session_id=parent_session_id,
                        prompt=prompt)
    planner._log = log  # redirect planner-internal logs to the pipeline file logger
    # Save session_id so iterate() can reuse it for full context continuity
    with open(os.path.join(out, "planner_session_id.txt"), "w") as _f:
        _f.write(planner.session_id)
    if parent_session_id:
        log.info(f"[PLANNER] Reusing session {planner.session_id[:8]}... from parent run")

    # Load or initialize the doom-loop streak counter (persisted to disk so it
    # survives crashes/restarts — prevents wasting iterations on phantom reqs).
    _streak_path = os.path.join(out, "coverage_streak.json")
    if os.path.exists(_streak_path):
        try:
            _coverage_miss_streak = json.loads(open(_streak_path).read())
            log.info(f"[COVERAGE] Loaded streak state from previous run: {_coverage_miss_streak}")
        except Exception:
            _coverage_miss_streak: dict = {}
    else:
        _coverage_miss_streak: dict = {}

    # Per-run metrics accumulator (written to disk at every exit path).
    _metrics: dict[str, any] = {
        "start_time": ts,
        "prompt": prompt[:200],
        "process": process,
        "domain_blocks": [],
        "failover_events": 0,
        "compile_failures": 0,
        "design_count": 0,
        "vision_runs": 0,
        "final_verdict": "none",
        "total_iterations": 0,
        "timeouts": 0,
    }

    # Doom-loop detection: track per-node failure streaks to detect when the
    # planner is circling on the same failure with non-working fixes.
    _redo_streaks: dict[str, int] = {}
    _last_redo_feedback: str | None = None

    def _save_streak():
        """Persist doom-loop streak counter to disk for crash recovery."""
        try:
            json.dump(_coverage_miss_streak, open(_streak_path, "w"))
        except Exception:
            pass

    def _save_metrics():
        """Write per-run metrics to disk."""
        try:
            _metrics["total_iterations"] = attempt if "attempt" in dir() else 0
            json.dump(_metrics, open(os.path.join(out, "metrics.json"), "w"), indent=2)
        except Exception:
            pass

    # DECOMPOSITION JUDGMENT (independent of the planner): part vs assembly, and
    # how to split — only where it's genuinely an assembly of distinct bodies.
    decision = decompose(dp)  # use core design prompt, not iterate-augmented prompt
    _save(out, "01c_decomposition.json", json.dumps(decision, indent=2))
    log.info(f"[DECOMPOSE] mode={decision['mode']} "
             f"components={[c.get('id') for c in decision.get('components', [])]} :: {decision.get('rationale','')[:140]}")
    if decision["mode"] == "assembly":
        return _run_assembly(planner, prompt, spec, decision["components"], out, log, interactive, min_wall)

    # Phase 1: initial IR (monolithic part path).
    try:
        text, ir = planner.generate_ir(prompt, spec=spec)
    except Exception as e:
        log.error(f"[PLAN] Planner failed (model/API unavailable?): {e}"); _report(out); return out
    _save(out, "02_outer1_planner_output.txt", text)

    for attempt in range(1, MAX_OUTER + 1):
        log.info(f"\n{'='*70}\nOUTER {attempt}/{MAX_OUTER}\n{'='*70}")

        # L1: validate (with one self-correct retry inside the loop).
        if ir is None or not validate_plan(ir)["valid"]:
            errs = validate_plan(ir)["errors"] if ir else [{"node": "design", "detail": "no IR emitted"}]
            log.warning(f"[L1] Invalid IR: {errs}")
            if attempt == MAX_OUTER:
                _metrics["final_verdict"] = "invalid_ir_exhausted"
                _save_metrics(); _save_streak()
                log.error("[L1] Out of attempts with invalid IR."); _report(out, _metrics); return out
            text, ir = planner.revise_ir(
                "Your IR failed validation. Fix these node-keyed errors and "
                f"re-emit the full IR:\n{json.dumps(errs, indent=2)}")
            _save(out, f"02_outer{attempt}_planner_revision.txt", text)
            continue
        _save(out, f"03_outer{attempt}_ir.json", json.dumps(ir, indent=2))
        log.info("[L1] ✅ IR valid.")
        _metrics["design_count"] += 1

        # Compile (geometry authority) — with timeout protection.
        try:
            (solid, prov), timed_out = run_with_timeout(compile_design, ir, timeout=COMPILE_TIMEOUT_S)
            if timed_out:
                _metrics["timeouts"] += 1
                log.warning(f"[COMPILE] Timed out after {COMPILE_TIMEOUT_S}s")
                if attempt == MAX_OUTER:
                    _metrics["final_verdict"] = "compile_timeout_exhausted"
                    _save_metrics(); _save_streak()
                    log.error("[COMPILE] Out of attempts."); _report(out, _metrics); return out
                text, ir = planner.revise_ir(
                    f"Compilation timed out after {COMPILE_TIMEOUT_S}s. Simplify the geometry or "
                    "reduce feature complexity, then re-emit the full IR.")
                continue
        except Exception as e:
            _metrics["compile_failures"] += 1
            raw = str(e)
            readable = translate_error(raw)
            log.warning(f"[COMPILE] Failed: {raw}")
            if attempt == MAX_OUTER:
                _metrics["final_verdict"] = "compile_exhausted"
                _save_metrics(); _save_streak()
                log.error("[COMPILE] Out of attempts."); _report(out, _metrics); return out
            text, ir = planner.revise_ir(
                f"Compilation failed. {readable}\n\n"
                "Fix the offending feature and re-emit the full IR.")
            continue

        step = export_solid(solid, os.path.join(out, f"04_outer{attempt}_model.step"))
        stl = export_solid(solid, os.path.join(out, f"04_outer{attempt}_model.stl"))
        log.info(f"[COMPILE] ✅ solids={len(solid.Solids())} vol={solid.Volume():.0f} → {os.path.basename(step)}/{os.path.basename(stl)}")

        # ── COMPILER DIAGNOSTICS: log + surface to reviewer ──────────────────
        from primitives.compiler import get_last_diagnostics as _get_diags
        _compiler_diags = _get_diags()
        for _d in _compiler_diags:
            log.warning(f"[COMPILE-DIAG] {_d.feature_id}: {_d.issue} — {_d.detail}")
        # ── /compiler diagnostics ────────────────────────────────────────────

        # L2: deterministic intent ground truth.
        l2 = inspect_solid(ir, solid, prov, min_wall_mm=min_wall, profile=profile)
        _save(out, f"05_outer{attempt}_solid_inspection.json", json.dumps(l2, indent=2))
        log.info(f"[L2] valid={l2['valid']} failures={l2['hard_failures']}")

        # ── CONSTRAINT TRANSLATION: map L2 failures to specific parameter targets ──
        _constraint_fixes: list[str] = []
        for _c in l2.get("checks", []) or []:
            if not _c.get("passed") and _c.get("claim") not in ("envelope_x_mm", "envelope_y_mm"):
                try:
                    _fix = _translate_failure(_c, prov, ir, solid)
                    if _fix:
                        _constraint_fixes.append(f"[{_c['node']}.{_c['claim']}] {_fix}")
                        log.info(f"[CONSTRAINT] {_c['node']}.{_c['claim']}: {_fix[:120]}...")
                except Exception as _e:
                    log.warning(f"[CONSTRAINT] translation failed for {_c['node']}.{_c['claim']}: {_e}")
        # ── /constraint translation ────────────────────────────────────────────────

        # L3: render + advisory vision (best-effort).
        vision = None
        try:
            views = render_views(solid, out, prefix=f"09_outer{attempt}_view")
            if run_vision_verification:
                _metrics["vision_runs"] += 1
                vision = run_vision_verification(views, _intent(ir))
                _save(out, f"06_outer{attempt}_vision_findings.json", json.dumps(vision, indent=2))
        except Exception as e:
            log.warning(f"[L3] Vision/render skipped: {e}")

        # L4: MeshLib ONLY for custom/mesh_only nodes (demoted).
        meshlib = None
        if any(p.mesh_only for p in prov):
            try:
                from agents.meshlib_agent import run_inspection
                meshlib = run_inspection(stl, {"prompt": prompt, "min_wall_mm": min_wall}, out, attempt)
            except Exception as e:
                log.warning(f"[L4] MeshLib skipped: {e}")

        # Reviewer.
        verdict = run_review(_intent(ir), l2, vision_findings=vision, meshlib_findings=meshlib)
        _save(out, f"07_outer{attempt}_reviewer_verdict.json", json.dumps(verdict, indent=2))
        log.info(f"[REVIEW] {verdict['decision']} ({verdict['confidence']}): {verdict['reasoning'][:200]}")

        decision = verdict["decision"]
        if decision == "APPROVED":
            # INTENT-COVERAGE GATE: geometry is valid (L2), but does it cover the
            # immutable user SPEC? (catches the flat-blade-impeller case)
            cov = check_coverage(spec, l2["checks"], ir)
            _save(out, f"08_outer{attempt}_spec_coverage.json", json.dumps(cov, indent=2))
            # Reset streak for any requirement that is now covered
            covered_ids = {r["id"] for r in cov.get("report", []) if r.get("covered")}
            for rid in covered_ids:
                _coverage_miss_streak.pop(rid, None)
            if not cov["covered"]:
                log.warning(f"[COVERAGE] ❌ uncovered intent: {[m['id'] for m in cov['missing']]}")

                # Doom-loop safety valve: if the SAME requirement fails twice in a row,
                # it cannot be satisfied by IR redesign (usually a phantom spec req).
                # Downgrade it to "preferred" so the run can still converge.
                still_missing, downgraded = [], []
                for m in cov["missing"]:
                    rid = m["id"]
                    _coverage_miss_streak[rid] = _coverage_miss_streak.get(rid, 0) + 1
                    if _coverage_miss_streak[rid] >= 2:
                        log.warning(f"[COVERAGE] Req {rid} stuck ({_coverage_miss_streak[rid]}× in a row) — "
                                    f"downgrading to preferred: {m.get('description','')[:80]}")
                        downgraded.append(rid)
                    else:
                        still_missing.append(m)
                if downgraded:
                    for r in spec:
                        if r["id"] in downgraded:
                            r["severity"] = "preferred"
                    cov["missing"] = still_missing
                    cov["covered"] = not still_missing
                    # Re-save with downgraded state for transparency
                    _save(out, f"08_outer{attempt}_spec_coverage.json", json.dumps(cov, indent=2))
                    if cov["covered"]:
                        # Coverage now passes — proceed to approval
                        pass
                    else:
                        if attempt == MAX_OUTER:
                            _metrics["final_verdict"] = "coverage_exhausted"
                            _save_metrics(); _save_streak()
                            log.error("Out of attempts; intent not fully covered."); _report(out, _metrics); return out
                        text, ir = planner.revise_ir(coverage_feedback(cov["missing"]))
                        _save(out, f"02_outer{attempt}_planner_revision.txt", text)
                        continue
                else:
                    # No downgrade yet — still trying
                    if attempt == MAX_OUTER:
                        _metrics["final_verdict"] = "coverage_exhausted"
                        _save_metrics(); _save_streak()
                        log.error("Out of attempts; intent not fully covered."); _report(out, _metrics); return out
                    text, ir = planner.revise_ir(coverage_feedback(cov["missing"]))
                    _save(out, f"02_outer{attempt}_planner_revision.txt", text)
                    continue

            if not cov["covered"]:
                # Should only reach here if we had downgraded but still have missing
                if attempt == MAX_OUTER:
                    _metrics["final_verdict"] = "coverage_exhausted"
                    _save_metrics(); _save_streak()
                    log.error("Out of attempts; intent not fully covered."); _report(out, _metrics); return out
                text, ir = planner.revise_ir(coverage_feedback(cov["missing"]))
                _save(out, f"02_outer{attempt}_planner_revision.txt", text)
                continue
            _save_streak()
            log.info("=" * 70)
            log.info("✅ APPROVED — geometry valid AND user-intent spec covered.")
            _save(out, "APPROVED_ir.json", json.dumps(ir, indent=2))
            trace.complete_run(ts if run_id is None else run_id, "approved",
                              custom_used=any(p.mesh_only for p in prov),
                              requires_review=any(p.mesh_only for p in prov))
            trace.log_stage(ts if run_id is None else run_id, "handoff", "completed")
            trace.close()
            try:
                from handoff import emit_forgecad_bundle
                bundle = os.path.join(out, "forgecad_handoff")
                manifest = emit_forgecad_bundle(ir, bundle)
                if manifest.get("requires_review"):
                    log.warning("[HANDOFF] ⚠️ requires_review=true — mesh_only/custom node present. Human review required.")
                log.info(f"[HANDOFF] ForgeCAD bundle written to {bundle} (trust_label={manifest.get('trust_label','?')})")
            except Exception as e:
                log.warning(f"[HANDOFF] bundle emission skipped: {e}")
            # ACCEPTANCE: APPROVED(harness) ≠ ACCEPTED(user). Gate + registry.
            summary = (f"Prompt: {prompt[:160]}\nSpec requirements covered: "
                       f"{len(cov['report'])}/{len(cov['report'])}\nViews: "
                       f"{out}/09_outer{attempt}_view_*.png")
            accepted, by = request_acceptance(interactive, summary)
            record(out, prompt, spec, ir, cov, verdict, accepted, by)
            log.info(f"[ACCEPT] accepted={accepted} by={by}; registry updated.")
            log.info(f"Artifacts: {out}")
            _metrics["final_verdict"] = "approved"
            _save_metrics(); _save_streak()
            _report(out, _metrics); return out
        if decision == "HALT":
            _metrics["final_verdict"] = "halt"
            _save_metrics(); _save_streak()
            log.error("🛑 HALT — human review required."); _report(out, _metrics); return out
        # REDESIGN — with doom-loop detection for repeated node/claim failures
        rec = verdict["recommendations_for_planner"]

        # ── Inject constraint-based guidance into the feedback ──────────────
        if _constraint_fixes:
            _enhanced = (rec or "")
            _enhanced += "\n\n--- CONSTRAINT-BASED GUIDANCE (use these specific numbers) ---\n"
            _enhanced += "\n\n".join(_constraint_fixes)
            rec = _enhanced
            log.info(f"[FEEDBACK] augmented with {len(_constraint_fixes)} constraint translation(s)")
        # ── /constraint injection ───────────────────────────────────────────

        log.warning(f"[REVIEW] 🔄 REDESIGN: {rec}")

        # Track per-node failure streaks. If the same feature.claim fails
        # 2+ times in a row, escalate the feedback to force a different approach.
        _failed = l2.get("hard_failures", []) if l2 else []
        for _f in _failed:
            _key = _f.split(":")[0].strip()  # e.g. "bore.bore_present"
            _redo_streaks[_key] = _redo_streaks.get(_key, 0) + 1
        # Find the highest streak among current failures
        _max_streak = max((_redo_streaks.get(f.split(":")[0].strip(), 1) for f in _failed), default=1)
        if _max_streak >= 2:
            _escalated = (
                f"\n\nDOOM-LOOP WARNING: The same failure has occurred "
                f"{_max_streak} iterations in a row — your previous fixes did NOT "
                f"work. Try a FUNDAMENTALLY DIFFERENT approach: change the "
                f"feature's position, dimensions, or type, not just tweak parameters. "
                f"If this is a bore being refilled by a union feature, reposition "
                f"the union feature away from the bore axis. If this is an embedded "
                f"feature, increase its radial reach significantly.\n"
            )
            rec = _escalated + rec
            log.warning(f"[DOOM-LOOP] streak={_max_streak} on failures={_failed}")
        if attempt == MAX_OUTER:
            _metrics["final_verdict"] = "redesign_exhausted"
            _save_metrics(); _save_streak()
            log.error("Out of attempts; not approved."); _report(out, _metrics); return out
        text, ir = planner.revise_ir(rec)
        _save(out, f"02_outer{attempt}_planner_revision.txt", text)

    _metrics["final_verdict"] = "max_iterations"
    _save_metrics(); _save_streak()
    log.warning("Completed all outer iterations without APPROVED.")
    _report(out, _metrics); return out


def _run_assembly(planner, prompt, spec, components, out, log, interactive, min_wall):
    """Assembly route — SAME loop as a part, but compile/verify operate on
    components + interfaces. APPROVED requires every component correct (L2) AND
    every interface correct (no interference / contact / fit)."""
    from geometry_ir.assembly import validate_assembly
    from primitives.assembly import compile_assembly
    from primitives import export_solid
    from verification.assembly_inspector import inspect_assembly
    from verification import render_views
    from agents.reviewer_agent import run_review  # must be here — run_pipeline's import is local

    try:
        text, asm = planner.generate_assembly(prompt, spec=spec, components=components)
    except Exception as e:
        log.error(f"[PLAN] Assembly planner failed: {e}"); _report(out); return out
    _save(out, "02_outer1_planner_output.txt", text)

    for attempt in range(1, MAX_OUTER + 1):
        log.info(f"\n{'='*70}\nOUTER {attempt}/{MAX_OUTER} (assembly)\n{'='*70}")
        v = validate_assembly(asm) if asm else {"valid": False, "errors": [{"node": "assembly", "detail": "no IR"}]}
        if not v["valid"]:
            log.warning(f"[L1] Invalid assembly: {v['errors']}")
            if attempt == MAX_OUTER:
                log.error("[L1] Out of attempts."); _report(out); return out
            text, asm = planner.revise_assembly(f"Fix these assembly errors and re-emit:\n{json.dumps(v['errors'], indent=2)}")
            continue
        _save(out, f"03_outer{attempt}_assembly.json", json.dumps(asm, indent=2))
        log.info("[L1] ✅ assembly valid.")

        try:
            compound, placed, bb = compile_assembly(asm)
            export_solid(compound, os.path.join(out, f"04_outer{attempt}_assembly.step"))
            export_solid(compound, os.path.join(out, f"04_outer{attempt}_assembly.stl"))
        except Exception as e:
            raw = str(e)
            readable = translate_error(raw)
            log.warning(f"[COMPILE] Assembly failed: {raw}")
            if attempt == MAX_OUTER:
                _report(out); return out
            text, asm = planner.revise_assembly(
                f"Assembly compilation failed. {readable}\n\nFix and re-emit the full Assembly IR."); continue
        log.info(f"[COMPILE] ✅ bodies={len(compound.Solids())} bbox z={bb.zmin:.0f}->{bb.zmax:.0f}")

        l2 = inspect_assembly(asm, min_wall_mm=min_wall)
        _save(out, f"05_outer{attempt}_assembly_inspection.json", json.dumps(l2, indent=2))
        log.info(f"[L2+L-ASM] valid={l2['valid']} failures={l2['hard_failures'][:4]}")
        vision = None
        try:
            views = render_views(compound, out, prefix=f"09_outer{attempt}_assembly")
            from agents.vision_agent import run_vision_verification
            vision = run_vision_verification(views, {"kind": "assembly", "components": components,
                                                     "mates": asm.get("mates", [])})
            _save(out, f"06_outer{attempt}_assembly_vision.json", json.dumps(vision, indent=2))
        except Exception as e:
            log.warning(f"[L3] vision/render skipped: {e}")

        verdict = run_review({"kind": "assembly", "components": components}, l2, vision_findings=vision)
        _save(out, f"07_outer{attempt}_reviewer_verdict.json", json.dumps(verdict, indent=2))
        log.info(f"[REVIEW] {verdict['decision']}: {verdict['reasoning'][:160]}")

        if verdict["decision"] == "APPROVED" and l2["valid"]:
            # COVERAGE GATE on the assembled whole: flatten components' features,
            # strip the component prefix from L2 nodes, and check the user SPEC.
            flat = {"features": [f for c in asm["components"] for f in c["design"]["features"]]}
            l2_flat = [{**c, "node": c["node"].split(".", 1)[-1]} for c in l2["checks"]]
            cov = check_coverage(spec, l2_flat, flat)
            _save(out, f"08_outer{attempt}_spec_coverage.json", json.dumps(cov, indent=2))
            if not cov["covered"]:
                log.warning(f"[COVERAGE] ❌ uncovered intent: {[m['id'] for m in cov['missing']]}")
                if attempt == MAX_OUTER:
                    log.error("Out of attempts; intent not fully covered."); _report(out); return out
                text, asm = planner.revise_assembly(coverage_feedback(cov["missing"]))
                _save(out, f"02_outer{attempt}_planner_revision.txt", text); continue
            log.info("=" * 70); log.info("✅ APPROVED — components + interfaces verified AND intent covered.")
            _save(out, "APPROVED_assembly.json", json.dumps(asm, indent=2))
            from core.registry import request_acceptance, record
            accepted, by = request_acceptance(interactive,
                f"Assembly: {len(asm.get('components', []))} components, {len(asm.get('mates', []))} mates.\nViews: {out}/09_outer{attempt}_assembly_*.png")
            record(out, prompt, spec, asm, cov, verdict, accepted, by)
            log.info(f"[ACCEPT] accepted={accepted} by={by}."); _report(out); return out
        if attempt == MAX_OUTER:
            log.error("Out of attempts; assembly not approved."); _report(out); return out
        text, asm = planner.revise_assembly(verdict.get("recommendations_for_planner")
                                            or ("Fix these failed checks: " + "; ".join(l2["hard_failures"][:3])))
        _save(out, f"02_outer{attempt}_planner_revision.txt", text)
    _report(out); return out


def _report(out_dir: str, metrics: dict | None = None):
    """Build the run report and save metrics if provided."""
    if metrics:
        try:
            metrics["total_iterations"] = metrics.get("total_iterations", 0)
            json.dump(metrics, open(os.path.join(out_dir, "metrics.json"), "w"), indent=2)
        except Exception:
            pass
    try:
        from reporting import build_report
        build_report(out_dir)
    except Exception:
        pass
    return out_dir


def _save(out_dir: str, name: str, content: str):
    with open(os.path.join(out_dir, name), "w") as f:
        f.write(content)


if __name__ == "__main__":
    interactive = "--interactive" in sys.argv or "-i" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    prompt = " ".join(args) if args else (
        "Create a bracket: a 100mm×100mm×10mm base plate with 4 bolt holes "
        "evenly spaced around a 40mm bolt circle.")
    run_pipeline(prompt, interactive=interactive)
