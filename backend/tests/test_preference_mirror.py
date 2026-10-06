"""Preference Mirror: engine thresholds/confidence/wording (pure) + confirm/dismiss persistence (DB)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import ClientPreference, MirrorStatus, PreferenceMirrorSignal, PreferenceSource
from app.services import mirror_store
from app.services.domain import AcceptedIn, CandidateIn, FeedbackIn, PreferenceIn, SignalIn
from app.services.preference_mirror import FORBIDDEN_PHRASES, compute_mirror_cards

NOW = datetime(2026, 6, 1, tzinfo=UTC)
STATED = [PreferenceIn("intellectual_compatibility", {"importance": "high"}, "strong")]


def feedback(n, *, intellectual=True, pedigree=False, days=20):
    when = NOW - timedelta(days=days + n)
    signals = []
    if intellectual:
        signals.append(
            SignalIn(f"f{n}", "intellectual_fit", "intellectual compatibility", f"not intellectually aligned {n}",
                     "stated_preference", "high", when)
        )
    if pedigree:
        signals.append(
            SignalIn(f"f{n}", "career_education", "college pedigree", f"college wasn't strong enough {n}",
                     "new_signal", "medium", when)
        )
    return FeedbackIn(id=f"f{n}", created_at=when, signals=tuple(signals))


def accepted(n, tier="standard", level="senior"):
    return AcceptedIn(
        decision_id=f"d{n}",
        candidate=CandidateIn(id=f"c{n}", name=f"Cand {n}", location="Mumbai", education="State College",
                              education_tier=tier, career_level=level),
        decided_at=NOW - timedelta(days=5),
    )


def cards(fbs, acc=(), prefs=STATED):
    return compute_mirror_cards(prefs, list(fbs), list(acc), client_location="Mumbai", now=NOW)


# ---- engine --------------------------------------------------------------------------------------------------


def test_insufficient_evidence_shows_no_card():
    assert cards([]) == []
    assert cards([feedback(0, pedigree=True)], [accepted(0)]) == []  # a single rejection is never enough


def test_no_stated_preference_means_nothing_to_mirror():
    assert cards([feedback(i, pedigree=True) for i in range(3)], [accepted(0)], prefs=[]) == []


def test_assessment_example_renders_as_medium_with_expected_text():
    # 3 rejections mention intellectual fit, 2 of them college pedigree, 1 similar accepted profile
    fbs = [feedback(0, pedigree=True), feedback(1, pedigree=True), feedback(2)]
    (card,) = cards(fbs, [accepted(0)])
    assert card.confidence == "medium"
    assert card.stated_text == "Intellectual compatibility is important."
    assert card.observed_summary == "3 recent rejections mention intellectual fit; 2 mention college pedigree."
    assert card.possible_pattern == (
        "Education prestige may be acting as a proxy for perceived intellectual compatibility."
    )
    assert card.evidence_summary == "2 rejection examples + 1 similar accepted profile"
    assert card.mixed_evidence is False
    assert [e.kind for e in card.evidence].count("rejection") == 3
    assert [e.kind for e in card.evidence].count("accepted") == 1


def test_confidence_levels_follow_the_rules():
    two = [feedback(i) for i in range(2)]
    four = [feedback(i) for i in range(4)]
    assert cards(two, [accepted(0)])[0].confidence == "medium"  # 2-3 + accepted
    assert cards(four, [accepted(0)])[0].confidence == "high"  # 4+ + accepted
    assert cards(two)[0].confidence == "low"  # 2+ but no similar accepted profile
    assert cards(four)[0].confidence == "low"


def test_mixed_evidence_is_flagged_capped_and_uses_cautious_wording():
    fbs = [feedback(i, pedigree=True) for i in range(4)]
    (card,) = cards(fbs, [accepted(0), accepted(1)])  # would be High, but the client also accepts such profiles
    assert card.mixed_evidence is True
    assert card.confidence == "medium"  # High lowered one step
    assert card.possible_pattern.startswith("Mixed evidence")
    assert "may" in card.possible_pattern
    for text in (card.possible_pattern, card.observed_summary, card.evidence_summary):
        assert not any(bad in text.lower() for bad in FORBIDDEN_PHRASES)


def test_wording_is_cautious_for_every_rule_variant():
    fbs = [feedback(i, pedigree=(i < 2)) for i in range(3)]
    for card in cards(fbs, [accepted(0)]):
        text = card.possible_pattern.lower()
        assert any(w in text for w in ("may", "appears", "possible", "suggest"))
        assert not any(bad in text for bad in FORBIDDEN_PHRASES)


def test_old_rejections_outside_the_recent_window_do_not_count():
    old = [feedback(i, days=400) for i in range(3)]
    assert cards(old, [accepted(0)]) == []


def test_non_violations_and_unclear_notes_are_ignored():
    ignored = []
    for i in range(3):
        when = NOW - timedelta(days=10 + i)
        ignored.append(
            FeedbackIn(f"x{i}", when, (SignalIn(f"x{i}", "intellectual_fit", "x", "e", "unclear", "low", when),))
        )
    assert cards(ignored, [accepted(0)]) == []


# ---- persistence + human-in-the-loop ------------------------------------------------------------------------


def _client_id(client, ids, name):
    return uuid.UUID(ids["clients"][name])


def _mirror(client, ids, name):
    return client.get(f"/api/clients/{ids['clients'][name]}/preference-mirror").json()


def test_seeded_ananya_has_the_demo_card(client, ids):
    data = _mirror(client, ids, "Ananya")
    card = next(c for c in data["suggestions"] if c["rule_key"] == "intellectual_pedigree")
    assert card["confidence"] == "medium" and card["status"] == "suggested"
    assert card["stated_text"] == "Intellectual compatibility is important."
    assert card["observed_summary"] == "3 recent rejections mention intellectual fit; 2 mention college pedigree."
    assert card["evidence_summary"] == "2 rejection examples + 1 similar accepted profile"
    assert "does not change the client's preferences" in card["advisory_note"]


def test_client_without_enough_evidence_has_no_cards(client, ids):
    data = _mirror(client, ids, "Rohan")
    assert data["suggestions"] == [] and data["confirmed"] == []


def test_confirm_creates_a_soft_human_confirmed_preference_only(client, ids, db):
    cid = _client_id(client, ids, "Ananya")
    prefs_before = {p.attribute: p.preference_type.value for p in db.scalars(
        select(ClientPreference).where(ClientPreference.client_id == cid))}
    card = next(c for c in _mirror(client, ids, "Ananya")["suggestions"] if c["rule_key"] == "intellectual_pedigree")

    res = client.post(f"/api/preference-mirror/{card['id']}/confirm")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "confirmed" and body["human_confirmed"] is True and body["confirmed_at"]

    db.expire_all()
    row = db.get(PreferenceMirrorSignal, uuid.UUID(card["id"]))
    assert row.status == MirrorStatus.confirmed and row.human_confirmed and row.confirmed_at
    assert len(row.evidence_feedback_ids) == 3 and len(row.evidence_decision_ids) == 1

    soft = db.scalar(select(ClientPreference).where(
        ClientPreference.client_id == cid, ClientPreference.attribute == "mirror:intellectual_pedigree"))
    assert soft is not None
    assert soft.preference_type.value == "soft" and soft.source == PreferenceSource.human_confirmed
    # nothing else was touched: no new dealbreaker, onboarding preferences unchanged
    prefs_after = {p.attribute: p.preference_type.value for p in db.scalars(
        select(ClientPreference).where(ClientPreference.client_id == cid))}
    assert {k: v for k, v in prefs_after.items() if not k.startswith("mirror:")} == prefs_before
    assert "dealbreaker" not in [v for k, v in prefs_after.items() if k.startswith("mirror:")]

    again = _mirror(client, ids, "Ananya")
    assert any(c["rule_key"] == "intellectual_pedigree" for c in again["confirmed"])
    assert not any(c["rule_key"] == "intellectual_pedigree" for c in again["suggestions"])


def test_confirmed_signal_changes_future_profile_checks(client, ids):
    def check():
        return client.post("/api/profile-check", json={
            "client_id": ids["clients"]["Ananya"], "candidate_id": ids["candidates"]["Rey D."]}).json()

    before = check()
    assert before["status"] == "AMBER" and before["warnings"][0]["source"] == "observed_pattern"

    card = next(c for c in _mirror(client, ids, "Ananya")["suggestions"] if c["rule_key"] == "intellectual_pedigree")
    client.post(f"/api/preference-mirror/{card['id']}/confirm")
    after = check()
    assert after["status"] == "AMBER"
    assert after["warnings"][0]["source"] == "confirmed_signal"
    # a candidate without the trait is unaffected
    green = client.post("/api/profile-check", json={
        "client_id": ids["clients"]["Ananya"], "candidate_id": ids["candidates"]["Meher L."]}).json()
    assert green["status"] == "GREEN"


def test_dismiss_is_persisted_hides_the_card_and_keeps_evidence(client, ids, db):
    card = next(c for c in _mirror(client, ids, "Ananya")["suggestions"] if c["rule_key"] == "intellectual_pedigree")
    res = client.post(f"/api/preference-mirror/{card['id']}/dismiss")
    assert res.status_code == 200 and res.json()["status"] == "dismissed"

    db.expire_all()
    row = db.get(PreferenceMirrorSignal, uuid.UUID(card["id"]))
    assert row.status == MirrorStatus.dismissed and not row.human_confirmed and row.dismissed_at
    assert len(row.evidence_feedback_ids) == 3  # evidence kept for auditability
    assert db.scalar(select(ClientPreference).where(
        ClientPreference.attribute == "mirror:intellectual_pedigree")) is None  # not turned into a preference

    # stays hidden on re-read, and no longer affects profile checks
    assert not any(c["rule_key"] == "intellectual_pedigree" for c in _mirror(client, ids, "Ananya")["suggestions"])
    check = client.post("/api/profile-check", json={
        "client_id": ids["clients"]["Ananya"], "candidate_id": ids["candidates"]["Rey D."]}).json()
    assert check["status"] == "GREEN"


def test_dismissed_pattern_returns_only_with_materially_stronger_evidence(client, ids):
    card = next(c for c in _mirror(client, ids, "Ananya")["suggestions"] if c["rule_key"] == "intellectual_pedigree")
    client.post(f"/api/preference-mirror/{card['id']}/dismiss")

    def save(note, cand=None):
        signals = client.post("/api/feedback/structure", json={
            "client_id": ids["clients"]["Ananya"], "rejection_note": note}).json()["signals"]
        return client.post("/api/feedback/save", json={
            "client_id": ids["clients"]["Ananya"], "rejection_note": note, "matchmaker_id": "A", "signals": signals})

    note = "Didn’t seem intellectually aligned, and his college background wasn’t what I was hoping for."
    save(note)  # 4 supporting rejections: only +1 vs the 3 dismissed -> still hidden
    assert not any(c["rule_key"] == "intellectual_pedigree" for c in _mirror(client, ids, "Ananya")["suggestions"])
    save(note)  # 5 supporting: +2 over the dismissed evidence -> may resurface
    resurfaced = [c for c in _mirror(client, ids, "Ananya")["suggestions"] if c["rule_key"] == "intellectual_pedigree"]
    assert len(resurfaced) == 1 and resurfaced[0]["id"] != card["id"]


def test_cannot_confirm_dismissed_or_dismiss_confirmed(client, ids):
    cards_ = _mirror(client, ids, "Ananya")["suggestions"]
    a, b = cards_[0], cards_[1]
    client.post(f"/api/preference-mirror/{a['id']}/dismiss")
    assert client.post(f"/api/preference-mirror/{a['id']}/confirm").status_code == 409
    client.post(f"/api/preference-mirror/{b['id']}/confirm")
    assert client.post(f"/api/preference-mirror/{b['id']}/dismiss").status_code == 409
    # idempotent repeats are fine
    assert client.post(f"/api/preference-mirror/{b['id']}/confirm").status_code == 200
    assert client.post(f"/api/preference-mirror/{a['id']}/dismiss").status_code == 200


def test_unknown_signal_ids_404(client):
    missing = uuid.uuid4()
    assert client.post(f"/api/preference-mirror/{missing}/confirm").status_code == 404
    assert client.post(f"/api/preference-mirror/{missing}/dismiss").status_code == 404


def test_mixed_evidence_card_is_visible_for_meera(client, ids):
    card = _mirror(client, ids, "Meera")["suggestions"][0]
    assert card["mixed_evidence"] is True
    assert card["possible_pattern"].startswith("Mixed evidence")
    assert card["confidence"] != "high"


def test_sync_is_idempotent(db):
    from app.models import Client

    for _ in range(3):
        for c in db.scalars(select(Client)).all():
            mirror_store.sync_client_mirror(db, c)
        db.commit()
    assert len(db.scalars(select(PreferenceMirrorSignal)).all()) == 6
