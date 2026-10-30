"""Plan lifecycle: record, adopt, review and list; the gates live in plsi.policy.gates.

World access only via plsi.map (registry, mapper). Plan state is a pure fold over plan_status events (plsi.policy.fold).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from plsi.clock import now
from plsi.errors import GateFailed, NotFound, PlsiError, violation
from plsi.events import NewEvent
from plsi.files import load_json
from plsi.map import mapper, registry
from plsi.models import parse
from plsi.paths import new_id
from plsi.policy import gates
from plsi.policy.fold import LIVE_STATES, PlanView, plans, window
from plsi.policy.models import Plan, PlanInput, PlanStatusPayload, Prediction, PredictionInput, PredictionScore, ReviewInput
from plsi.vocab import EventType, GateId, PlanDecision, PlanState, ScoreStatus


# ---------------------------------------------------------------- lifecycle

def _record(instance: str, plan: PlanInput, views: dict[str, PlanView] | None = None) -> dict[str, Any]:
    input_hash = plan.compute_input_hash()
    views = plans(instance) if views is None else views
    for pid, view in views.items():
        if view.plan.input_hash == input_hash:
            return {"plan_id": pid, "created": False, "ids": view.plan.ids, "state": view.state.value}
    ctx = gates.require(instance, plan, views=views)
    for m in ctx.maps.values():
        registry.snapshot(instance, m)
    prefix = {**{a.local_id: "act" for a in plan.actions}, **{c.local_id: "clm" for c in plan.claims},
              **{p.local_id: "pred" for p in plan.predictions}}
    ids = {local: new_id(pfx) for local, pfx in prefix.items()}
    predictions = []
    for p in plan.predictions:
        m, state = ctx.maps[p.map_id], ctx.states[p.map_id]
        baseline = state.coordinates.get(p.coordinate)
        predictions.append(Prediction(**p.model_dump(), id=ids[p.local_id], unit=m.coordinate(p.coordinate).unit,
                                      baseline=baseline if gates.numeric(baseline) else None,
                                      map_version=m.map_version, map_hash=m.compute_hash(),
                                      state_ref={"state_hash": state.state_hash, "as_of": state.as_of}))
    stored = Plan(**plan.model_dump(exclude={"predictions"}), predictions=predictions, id=new_id("plan"),
                  subject_id=mapper.subject(instance).subject_id, input_hash=input_hash, ids=ids,
                  screening_event_ids=[ctx.screening[a.local_id].id for a in plan.actions], created_at=now())
    status = PlanStatusPayload(plan_id=stored.id, state_after=PlanState.PROPOSED, at=now())
    mapper.event_store(instance).append_many([NewEvent(EventType.PLAN, stored, dedupe_key=input_hash),
                                              NewEvent(EventType.PLAN_STATUS, status)])
    return {"plan_id": stored.id, "created": True, "ids": ids, "state": PlanState.PROPOSED.value}


def record(instance: str, file: str) -> dict[str, Any]:
    """`plan record`: same gates; assign ids, per-prediction state_ref and baseline; append plan + plan_status(proposed)."""
    return _record(instance, gates.parse_plan(load_json(file)))


def _view(instance: str, views: dict[str, PlanView], plan_id: str, allowed: tuple[PlanState, ...]) -> PlanView:
    view = views.get(plan_id)
    if view is None:
        raise NotFound(f"plan {plan_id!r} not found", code="PLAN_NOT_FOUND", hint=f"plsi plan list --instance {instance}")
    if view.state not in allowed:
        raise PlsiError(f"plan {plan_id} is {view.state.value}; needs {' or '.join(s.value for s in allowed)}", code="PLAN_STATE")
    return view


def as_input(plan: Plan) -> PlanInput:
    data = plan.model_dump(mode="json", include=set(PlanInput.model_fields), exclude_none=True)
    data["predictions"] = [{k: v for k, v in p.items() if k in PredictionInput.model_fields} for p in data["predictions"]]
    return PlanInput.model_validate(data)


def adopt(instance: str, plan_id: str, start_on: date | None = None) -> dict[str, Any]:
    """`plan adopt`: re-run G1-G7 now; append plan_status(adopt -> adopted) with start, horizons and review_at."""
    view = _view(instance, plans(instance), plan_id, (PlanState.PROPOSED,))
    gates.require(instance, as_input(view.plan), skip=frozenset({GateId.G8}))
    start = start_on or now().date()
    horizons = {p.id: start + timedelta(days=p.horizon_days) for p in view.plan.predictions}
    review_at = start + timedelta(days=view.plan.revision_rule.review_after_days)
    status = PlanStatusPayload(plan_id=plan_id, decision=PlanDecision.ADOPT, state_after=PlanState.ADOPTED, at=now(),
                               start=start, horizons=horizons, review_at=review_at)
    mapper.event_store(instance).append(EventType.PLAN_STATUS, status)
    return {"plan_id": plan_id, "state": PlanState.ADOPTED.value, "start": start, "horizons": horizons, "review_at": review_at}


def _voidable(instance: str, view: PlanView) -> list[str]:
    """Unscored predictions whose window has not opened (never-adopted plans: all of them)."""
    horizons = (view.adoption.horizons if view.adoption else None) or {}
    unscored = [p for p in view.plan.predictions if p.id not in view.scores]
    return [p.id for p in unscored if p.id not in horizons
            or now() < window(registry.load_snapshot(instance, p.map_id, p.map_hash), p, horizons[p.id])[0]]


def review(instance: str, plan_id: str, file: str) -> dict[str, Any]:
    """`plan review --plan ID --file review.json` (ReviewInput)."""
    r = parse(ReviewInput, load_json(file), "review")
    allowed = LIVE_STATES if r.decision in (PlanDecision.MODIFY, PlanDecision.STOP) else (PlanState.ADOPTED,)
    views = plans(instance)
    view = _view(instance, views, plan_id, allowed)
    state_after = {PlanDecision.CONTINUE: PlanState.ADOPTED, PlanDecision.MODIFY: PlanState.SUPERSEDED,
                   PlanDecision.STOP: PlanState.STOPPED, PlanDecision.COMPLETE: PlanState.COMPLETED}[r.decision]
    replacement_id = None
    review_at = view.adoption.review_at if view.adoption else None
    if r.decision == PlanDecision.COMPLETE and (review_at is None or now().date() < review_at):
        raise PlsiError(f"complete is allowed from review_at ({review_at})", code="PLAN_STATE")
    if r.decision == PlanDecision.MODIFY:
        if r.replacement.supersedes not in (None, plan_id):
            raise GateFailed([violation("replacement.supersedes", GateId.G8, f"replacement must supersede {plan_id}")])
        replacement_id = _record(instance, r.replacement.model_copy(update={"supersedes": plan_id}), views)["plan_id"]
    voided = _voidable(instance, view) if r.decision in (PlanDecision.MODIFY, PlanDecision.STOP) else []
    status = PlanStatusPayload(plan_id=plan_id, decision=r.decision, state_after=state_after, at=now(),
                               rationale=r.rationale, replacement_plan_id=replacement_id)
    events = [NewEvent(EventType.PLAN_STATUS, status)]
    events += [NewEvent(EventType.PREDICTION_SCORE, PredictionScore(prediction_id=pid, status=ScoreStatus.VOID, scored_at=now()),
                         dedupe_key=f"score:{pid}", dedupe=True) for pid in voided]
    mapper.event_store(instance).append_many(events)
    out: dict[str, Any] = {"plan_id": plan_id, "state": state_after.value, "voided": voided}
    if replacement_id:
        out["replacement_plan_id"] = replacement_id
    return out


def list_plans(instance: str) -> list[dict[str, Any]]:
    """`plan list`: [{plan_id, objective, maps, state, created_at, start?, review_at?, predictions: n}] from the fold."""
    out = []
    for pid, view in plans(instance).items():
        item = {"plan_id": pid, "objective": view.plan.objective, "maps": view.plan.map_ids(), "state": view.state.value,
                "created_at": view.plan.created_at.isoformat(), "predictions": len(view.plan.predictions)}
        for field in ("start", "review_at"):
            if view.adoption and getattr(view.adoption, field):
                item[field] = getattr(view.adoption, field).isoformat()
        out.append(item)
    return out
