from app.services.speech.azure import parse_response


def _topic(client, skill: str) -> dict:
    return client.get(f"/api/topics?skill={skill}").json()[0]


def test_catalog(client) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
    meta = client.get("/api/meta").json()
    assert [lvl["value"] for lvl in meta["levels"]] == ["A1", "A2", "B1", "B2", "C1"]
    skills = {t["skill"] for t in client.get("/api/topics").json()}
    assert skills == {"vocabulary", "grammar", "writing"}


def test_vocabulary_lesson_flow(client, wait_for) -> None:
    created = client.post("/api/lessons", json={"topic_id": _topic(client, "vocabulary")["id"], "level": "B1"})
    assert created.status_code == 201 and created.json()["status"] == "generating"
    lesson = wait_for(f"/api/lessons/{created.json()['id']}")
    assert lesson["status"] == "ready" and len(lesson["content"]["words"]) == 3
    # answers are hidden until attempted
    assert all(ex["result"] is None and "answers" not in ex for ex in lesson["exercises"])

    lid = lesson["id"]
    mc, fill, produce = lesson["exercises"]
    r = client.post(f"/api/lessons/{lid}/exercises/{mc['id']}/attempts", json={"answer": "a ticket"}).json()
    assert r["exercise"]["result"]["is_correct"] is False
    assert r["exercise"]["result"]["answers"] == ["a travel plan"]
    client.post(f"/api/lessons/{lid}/exercises/{mc['id']}/attempts", json={"answer": "a travel plan"})
    client.post(f"/api/lessons/{lid}/exercises/{fill['id']}/attempts", json={"answer": "souvenir"})
    r = client.post(
        f"/api/lessons/{lid}/exercises/{produce['id']}/attempts", json={"answer": "Show your boarding pass here."}
    ).json()
    assert r["lesson_status"] == "completed"
    assert r["lesson_score"] == round((100 + 100 + 90) / 3, 1)  # best attempt per exercise
    assert r["cards_added"] == 3

    stats = client.get("/api/vocab/stats").json()
    assert stats["total"] == 3 and stats["due"] == 3
    card = client.get("/api/vocab/cards?due=true").json()[0]
    assert set(card["intervals"]) == {"1", "2", "3", "4"}
    reviewed = client.post(f"/api/vocab/cards/{card['id']}/review", json={"rating": 4}).json()
    assert reviewed["reps"] == 1 and reviewed["due_at"] > card["due_at"]
    assert client.get("/api/vocab/stats").json()["reviewed_today"] == 1

    # adding the same lesson again does not duplicate words
    assert client.post(f"/api/lessons/{lid}/deck").json() == {"added": 0, "in_deck": 3}

    progress = client.get("/api/progress").json()
    assert progress["streak_days"] == 1
    vocab = next(s for s in progress["skills"] if s["skill"] == "vocabulary")
    assert vocab["completed"] >= 1


def test_regenerate_exercises_starts_new_round(client, wait_for) -> None:
    lid = client.post("/api/lessons", json={"topic_id": _topic(client, "vocabulary")["id"]}).json()["id"]
    lesson = wait_for(f"/api/lessons/{lid}")
    first = lesson["exercises"][0]
    client.post(f"/api/lessons/{lid}/exercises/{first['id']}/attempts", json={"answer": "a travel plan"})

    r = client.post(f"/api/lessons/{lid}/exercises/regenerate")
    assert r.status_code == 200 and r.json()["exercises_status"] == "generating"
    for _ in range(100):
        lesson = client.get(f"/api/lessons/{lid}").json()
        if lesson["exercises_status"] != "generating":
            break
    assert lesson["exercise_round"] == 2 and lesson["exercises_status"] is None
    assert [e["id"] for e in lesson["exercises"]] == ["r2e1", "r2e2"]
    assert all(e["result"] is None for e in lesson["exercises"])  # fresh round, old attempts not shown
    assert lesson["answered_count"] == 0 and lesson["content"]["words"]  # lesson body untouched

    for e, ans in zip(lesson["exercises"], ["a travel plan", "souvenir"], strict=True):
        out = client.post(f"/api/lessons/{lid}/exercises/{e['id']}/attempts", json={"answer": ans}).json()
    assert out["lesson_status"] == "completed" and out["lesson_score"] == 100


def test_failed_generation_can_be_retried(client, fake_ai, wait_for) -> None:
    fake_ai.fail_next = True
    lid = client.post("/api/lessons", json={"topic_id": _topic(client, "grammar")["id"], "level": "A2"}).json()["id"]
    lesson = wait_for(f"/api/lessons/{lid}")
    assert lesson["status"] == "failed" and lesson["error"] == "fake outage"
    assert client.post(f"/api/lessons/{lid}/retry").status_code == 200
    assert wait_for(f"/api/lessons/{lid}")["status"] == "ready"


def test_wrong_skill_topic_rejected(client) -> None:
    r = client.post("/api/lessons", json={"topic_id": _topic(client, "writing")["id"], "level": "B1"})
    assert r.status_code == 400


def test_writing_flow(client, wait_for) -> None:
    tid = client.post("/api/writing/tasks", json={"topic_id": _topic(client, "writing")["id"]}).json()["id"]
    task = wait_for(f"/api/writing/tasks/{tid}")
    assert task["status"] == "ready" and task["prompt"]["min_words"] == 50

    text = "Hi Sam, I start a new job last month and I like it very much. See you soon!"
    sub = client.post(f"/api/writing/tasks/{tid}/submissions", json={"text": text}).json()
    graded = wait_for(f"/api/writing/submissions/{sub['id']}")
    assert graded["status"] == "graded"
    assert graded["overall_score"] == 55  # mean of criteria, not the model's own number
    assert [c["original"] for c in graded["result"]["corrections"]] == ["I start"]  # unlocatable one dropped
    assert wait_for(f"/api/writing/tasks/{tid}")["status"] == "completed"


def test_azure_response_parsing() -> None:
    data = {
        "RecognitionStatus": "Success",
        "NBest": [
            {
                "Display": "Hello.",
                "AccuracyScore": 90,
                "FluencyScore": 80,
                "CompletenessScore": 100,
                "PronScore": 88,
                "Words": [
                    {
                        "Word": "hello",
                        "AccuracyScore": 90,
                        "ErrorType": "None",
                        "Phonemes": [{"Phoneme": "h", "AccuracyScore": 70}],
                    }
                ],
            }
        ],
    }
    a = parse_response(data)
    assert (a.pron_score, a.prosody, a.words[0].phonemes[0]["score"]) == (88, None, 70)
