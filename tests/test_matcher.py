from tender_radar.dedupe.matcher import normalize_buyer, score_pair


def test_normalize_buyer_strips_noise():
    assert normalize_buyer("The Coventry University Ltd.") == "coventry university"
    assert normalize_buyer("Barnet & Camden NHS Trust") == "barnet and camden nhs trust"
    assert normalize_buyer("DEFRA") == normalize_buyer("defra")


def test_identical_notice_scores_high():
    c = score_pair(
        "ocds-h6vhtk-1", "ocds-b5fd17-1",
        "Supply of laptops for schools", "Supply of laptops for schools",
        "30213100", "30213100", 250000.0, 250000.0,
    )
    assert c.confidence > 0.95
    assert c.cpv_match
    assert "title 1.00" in c.match_reason


def test_unrelated_notice_scores_low():
    c = score_pair(
        "ocds-h6vhtk-2", "ocds-b5fd17-2",
        "Grounds maintenance services", "Cyber security penetration testing",
        "77314000", "72810000", None, 80000.0,
    )
    assert c.confidence < 0.5


def test_missing_values_are_neutral():
    with_value = score_pair("a", "b", "Same title", "Same title", None, None, 100.0, 100.0)
    without_value = score_pair("a", "b", "Same title", "Same title", None, None, None, None)
    assert abs(with_value.confidence - without_value.confidence) < 0.01
