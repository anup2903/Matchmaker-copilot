"""API smoke tests: every endpoint, the demo scenarios, and error handling."""

import uuid

from sqlalchemy import func, select

from app.models import Decision, FeedbackSignal, RejectionFeedback


def check(client, ids, who, cand):
    res = client.post("/api/profile-check", json={
        "client_id": ids["clients"][who], "candidate_id": ids["candidates"][cand]})
    assert res.status_code == 200, res.text
    return res.json()


# ---- infrastructure ------------------------------------------------------------------------------------------


def test_health(client):
    for path in ("/health", "/api/health"):
        body = client.get(path).json()
        assert body["status"] in ("ok", "degraded") and body["llm_mode"] == "demo"
        assert "key" not in str(body).lower()


def test_clients_and_candidates_lists(client):
    clients = client.get("/api/clients").json()
    candidates = client.get("/api/candidates").json()
    assert len(clients) >= 6 and len(candidates) >= 12
    assert {"id", "name", "age", "location"} <= set(clients[0])
    assert "smokes" in candidates[0] and "education_tier" in candidates[0]
    assert any(c["smokes"] is None for c in candidates)  # unknown stays unknown


def test_client_detail(client, ids):
    detail = client.get(f"/api/clients/{ids['clients']['Ananya']}").json()
    assert detail["name"] == "Ananya"
    prefs = {p["attribute"]: p for p in detail["preferences"]}
    assert prefs["smoking"]["preference_type"] == "dealbreaker" and prefs["smoking"]["label"] == "Non-smoker"
    assert prefs["intellectual_compatibility"]["preference_type"] == "strong"
    assert detail["recent_decisions"] and detail["preference_mirror"]
    assert client.get(f"/api/clients/{uuid.uuid4()}").status_code == 404
    assert client.get("/api/clients/not-a-uuid").status_code == 422


# ---- Check a Profile: mandatory scenarios --------------------------------------------------------------------


def test_red_smoker_for_ananya(client, ids):
    res = check(client, ids, "Ananya", "Rhea T.")
    assert res["status"] == "RED" and res["status_label"] == "RED — BLOCKED"
    reason = res["blocking_reasons"][0]
    assert reason["source"] == "dealbreaker" and "Non-smoker" in reason["evidence"]


def test_amber_repeated_long_distance_for_ananya(client, ids):
    res = check(client, ids, "Ananya", "Veer A.")
    assert res["status"] == "AMBER" and res["status_label"] == "AMBER — REVIEW"
    assert res["blocking_reasons"] == []
    warning = res["warnings"][0]
    assert warning["source"] == "past_rejection"
    assert warning["message"] == "Client rejected 3 recent profiles citing long distance."
    assert res["positive_signals"]  # positives are shown alongside warnings


def test_green_for_ananya(client, ids):
    res = check(client, ids, "Ananya", "Meher L.")
    assert res["status"] == "GREEN" and res["status_label"] == "GREEN — GOOD TO SHARE"
    assert res["positive_signals"] and not res["warnings"]
    assert all(p["evidence"] and p["source"] for p in res["positive_signals"])


def test_amber_with_mirror_suggestion_for_ananya(client, ids):
    res = check(client, ids, "Ananya", "Rey D.")
    assert res["status"] == "AMBER"
    assert res["preference_mirror"]["rule_key"] == "intellectual_pedigree"
    assert res["preference_mirror"]["confidence"] == "medium"


def test_unknown_dealbreaker_attribute_is_flagged_not_guessed(client, ids):
    res = check(client, ids, "Ananya", "Jai O.")
    assert res["status"] == "AMBER" and "unknown" in res["warnings"][0]["message"].lower()


def test_rohan_children_and_smoking_dealbreakers(client, ids):
    assert check(client, ids, "Rohan", "Zara P.")["status"] == "RED"
    assert check(client, ids, "Rohan", "Rhea T.")["status"] == "RED"
    assert check(client, ids, "Rohan", "Sasha R.")["status"] == "GREEN"
    assert check(client, ids, "Rohan", "Veer A.")["status"] == "AMBER"


def test_weak_mismatch_remains_green(client, ids):
    res = check(client, ids, "Priya", "Kiran M.")
    assert res["status"] == "GREEN" and res["notes"]


def test_seeded_confirmed_signal_makes_priya_amber(client, ids):
    res = check(client, ids, "Priya", "Veer A.")
    assert res["status"] == "AMBER" and res["warnings"][0]["source"] == "confirmed_signal"


def test_profile_check_errors(client, ids):
    bad = {"client_id": str(uuid.uuid4()), "candidate_id": ids["candidates"]["Rhea T."]}
    assert client.post("/api/profile-check", json=bad).status_code == 404
    bad = {"client_id": ids["clients"]["Ananya"], "candidate_id": str(uuid.uuid4())}
    assert client.post("/api/profile-check", json=bad).status_code == 404
    assert client.post("/api/profile-check", json={"client_id": ids["clients"]["Ananya"]}).status_code == 422


# ---- Structure Feedback ---------------------------------------------------------------------------------------


def test_structure_feedback_demo_mode(client, ids):
    note = client.get("/api/feedback/samples").json()[0]["note"]
    res = client.post("/api/feedback/structure", json={
        "client_id": ids["clients"]["Ananya"], "rejection_note": note})
    assert res.status_code == 200
    body = res.json()
    assert body["demo_mode"] is True and body["provider"] == "demo"
    first = body["signals"][0]
    assert {"category", "attribute", "violated_stated_preference", "violation_type", "confidence",
            "explanation", "evidence"} <= set(first)
    assert len(body["signals"]) == 2


def test_structure_feedback_validation(client, ids):
    assert client.post("/api/feedback/structure", json={
        "client_id": ids["clients"]["Ananya"], "rejection_note": "   "}).status_code == 422
    assert client.post("/api/feedback/structure", json={
        "client_id": str(uuid.uuid4()), "rejection_note": "too far"}).status_code == 404


def test_structure_feedback_llm_failures_return_clean_errors(client, ids):
    from app.api.feedback import provider_factory
    from app.main import app
    from app.services.llm.provider import InvalidModelOutputError, LLMProvider, LLMUnavailableError

    class Broken(LLMProvider):
        demo = False

        def __init__(self, exc):
            self.exc = exc

        def structure_rejection(self, note, client_preferences, correction=None):
            raise self.exc

    payload = {"client_id": ids["clients"]["Ananya"], "rejection_note": "too far"}

    app.dependency_overrides[provider_factory] = lambda: (lambda force_demo: Broken(LLMUnavailableError("timeout")))
    res = client.post("/api/feedback/structure", json=payload)
    assert res.status_code == 503 and res.json()["detail"]["fallback_available"] is True

    app.dependency_overrides[provider_factory] = lambda: (lambda force_demo: Broken(InvalidModelOutputError("bad")))
    res = client.post("/api/feedback/structure", json=payload)
    assert res.status_code == 502 and res.json()["detail"]["code"] == "llm_invalid_output"


def test_save_feedback_persists_signals_and_links_the_decision(client, ids, db):
    note = "Lives too far from me, and the age gap felt a bit large. He also mentioned he doesn’t want kids."
    structured = client.post("/api/feedback/structure", json={
        "client_id": ids["clients"]["Ananya"], "rejection_note": note}).json()
    before_fb = db.scalar(select(func.count()).select_from(RejectionFeedback))
    before_sig = db.scalar(select(func.count()).select_from(FeedbackSignal))

    res = client.post("/api/feedback/save", json={
        "client_id": ids["clients"]["Ananya"], "candidate_id": ids["candidates"]["Jai O."],
        "rejection_note": note, "matchmaker_id": "B", "signals": structured["signals"]})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["signal_count"] == 3 and body["decision_id"] and isinstance(body["preference_mirror"], list)

    db.expire_all()
    assert db.scalar(select(func.count()).select_from(RejectionFeedback)) == before_fb + 1
    assert db.scalar(select(func.count()).select_from(FeedbackSignal)) == before_sig + 3
    decision = db.get(Decision, uuid.UUID(body["decision_id"]))
    assert decision.status.value == "rejected" and decision.matchmaker_id == "B"


def test_save_feedback_accepts_edited_signals_but_revalidates(client, ids):
    structured = client.post("/api/feedback/structure", json={
        "client_id": ids["clients"]["Ananya"], "rejection_note": "Too far for me."}).json()["signals"]
    edited = [{**structured[0], "confidence": "low"}]
    ok = client.post("/api/feedback/save", json={
        "client_id": ids["clients"]["Ananya"], "rejection_note": "Too far for me.", "signals": edited})
    assert ok.status_code == 201 and ok.json()["decision_id"] is None
    bad = [{**structured[0], "category": "astrology"}]
    assert client.post("/api/feedback/save", json={
        "client_id": ids["clients"]["Ananya"], "rejection_note": "x", "signals": bad}).status_code == 422
    assert client.post("/api/feedback/save", json={
        "client_id": ids["clients"]["Ananya"], "rejection_note": "x", "signals": []}).status_code == 422


def test_unsaved_structuring_does_not_change_history(client, ids, db):
    before = db.scalar(select(func.count()).select_from(FeedbackSignal))
    client.post("/api/feedback/structure", json={
        "client_id": ids["clients"]["Ananya"], "rejection_note": "Too far for me."})
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(FeedbackSignal)) == before
