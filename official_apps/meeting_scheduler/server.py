"""회의 일정 조율 앱 - 후보 시간을 돌리고, 가능한 사람이 가장 많은 때를 찾아 줍니다.

회의 잡을 때 메일이 스무 통씩 오가는 일을 줄이는 것이 목적입니다.
  1. 주최자가 후보 시간 몇 개를 걸어 조율표를 만듭니다 (create_poll)
  2. 참석자들의 응답을 넣습니다 (submit_availability)
  3. 가장 많은 사람이 되는 시간을 찾아 확정합니다 (best_slots -> confirm_meeting)

메일 발송은 이 앱이 하지 않습니다. 안내문 초안만 만들어 주고, 실제 발송은
메일 앱이 맡습니다. 잘못 보낸 메일은 되돌릴 수 없으니 확인 뒤에 보내야 합니다.

실행:  python -m meeting_scheduler.server   ->  http://localhost:9115/mcp
"""
import os

from mcp.server.fastmcp import FastMCP

from common.store import Store, today_iso

store = Store("meeting_scheduler")

mcp = FastMCP(
    "회의 일정 조율",
    instructions=(
        "참석자와 후보 시간을 받아 가능한 시간을 취합하고, 가장 많은 사람이 되는 "
        "시간으로 확정안과 안내문 초안을 만듭니다."
    ),
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "9115")),
)


def _replies(poll_id: str) -> list[dict]:
    return store.list("availability", poll_id=poll_id)


@mcp.tool()
def create_poll(
    organizer: str,
    title: str,
    participants: list[str],
    candidate_slots: list[str],
    duration_minutes: int = 60,
    reply_by: str = "",
    place: str = "",
) -> dict:
    """회의 시간 조율표를 만들고, 참석자에게 보낼 안내문 초안을 돌려줍니다.

    Args:
        organizer: 주최자 이름 또는 사번. 예) 김로아
        title: 회의 제목. 예) 차세대 MES 설계 리뷰
        participants: 참석자 목록. 예) ["이하늘", "최바다"]
        candidate_slots: 후보 시간 목록. 예) ["2026-09-22 10:00", "2026-09-22 14:00"]
        duration_minutes: 회의 예상 시간(분). 기본 60
        reply_by: 회신 기한. 예) 2026-09-20
        place: 장소. 예) 3층 대회의실
    """
    poll = store.put(
        "poll",
        {
            "title": title,
            "organizer": organizer,
            "participants": [str(p) for p in participants or []],
            "candidate_slots": [str(s) for s in candidate_slots or []],
            "duration_minutes": duration_minutes,
            "reply_by": reply_by,
            "place": place,
            "status": "조율중",
            "confirmed_slot": "",
        },
        user_id=organizer,
    )
    lines = [f"[회의 시간 조율] {title}", "", f"아래 후보 중 가능한 시간을 알려 주세요. (소요 {duration_minutes}분)"]
    lines += [f"  {i + 1}) {slot}" for i, slot in enumerate(poll["candidate_slots"])]
    lines.append("")
    if reply_by:
        lines.append(f"회신 기한: {reply_by}")
    if place:
        lines.append(f"장소: {place}")
    lines.append(f"주최: {organizer}")
    notice = "\n".join(lines)
    return {"poll_id": poll["id"], "poll": poll, "notice_draft": notice}


@mcp.tool()
def submit_availability(
    poll_id: str,
    participant: str,
    available_slots: list[str],
    comment: str = "",
) -> dict:
    """참석자 한 명의 가능한 시간을 조율표에 기록합니다. 다시 내면 덮어씁니다.

    Args:
        poll_id: 조율표 id
        participant: 참석자 이름. 예) 이하늘
        available_slots: 가능한 후보 시간들. 예) ["2026-09-22 10:00"]
        comment: 남길 말. 예) 10시는 30분 늦게 가능
    """
    poll = store.get(poll_id)
    if poll is None or poll.get("kind") != "poll":
        return {"ok": False, "error": f"조율표를 찾을 수 없습니다: {poll_id}"}

    slots = [str(s) for s in available_slots or []]
    unknown = [s for s in slots if s not in poll.get("candidate_slots", [])]
    existing = [r for r in _replies(poll_id) if r.get("participant") == participant]
    payload = {"poll_id": poll_id, "participant": participant, "slots": slots, "comment": comment}

    if existing:
        store.update(existing[0]["id"], **payload)
    else:
        store.put("availability", payload, user_id=participant)

    answer = {"ok": True, "poll_id": poll_id, "participant": participant, "recorded": len(slots)}
    if unknown:
        answer["ignored"] = unknown
        answer["hint"] = "후보에 없는 시간은 집계에 들어가지 않습니다."
    return answer


@mcp.tool()
def poll_status(poll_id: str) -> dict:
    """조율표 현황을 돌려줍니다. 누가 답했고 누가 아직 안 했는지 알 수 있습니다.

    Args:
        poll_id: 조율표 id
    """
    poll = store.get(poll_id)
    if poll is None or poll.get("kind") != "poll":
        return {"ok": False, "error": f"조율표를 찾을 수 없습니다: {poll_id}"}

    replies = _replies(poll_id)
    answered = {r.get("participant") for r in replies}
    participants = poll.get("participants", [])
    return {
        "title": poll.get("title"),
        "status": poll.get("status"),
        "confirmed_slot": poll.get("confirmed_slot", ""),
        "reply_by": poll.get("reply_by", ""),
        "answered": sorted(answered),
        "not_answered": [p for p in participants if p not in answered],
        "replies": [
            {"participant": r.get("participant"), "slots": r.get("slots", []), "comment": r.get("comment", "")}
            for r in replies
        ],
    }


@mcp.tool()
def best_slots(poll_id: str) -> dict:
    """가능한 사람이 많은 순서로 후보 시간을 정렬해 돌려줍니다.

    Args:
        poll_id: 조율표 id
    """
    poll = store.get(poll_id)
    if poll is None or poll.get("kind") != "poll":
        return {"ok": False, "error": f"조율표를 찾을 수 없습니다: {poll_id}"}

    replies = _replies(poll_id)
    participants = poll.get("participants", [])
    ranked = []
    for slot in poll.get("candidate_slots", []):
        available = [r.get("participant") for r in replies if slot in r.get("slots", [])]
        ranked.append({
            "slot": slot,
            "available_count": len(available),
            "available": available,
            "unavailable": [p for p in participants if p not in available and
                            p in {r.get("participant") for r in replies}],
        })
    ranked.sort(key=lambda row: (-row["available_count"], row["slot"]))
    everyone = [row for row in ranked if row["available_count"] == len(participants) and participants]
    return {
        "title": poll.get("title"),
        "ranked_slots": ranked,
        "all_available": [row["slot"] for row in everyone],
        "waiting_for": [p for p in participants if p not in {r.get("participant") for r in replies}],
    }


@mcp.tool()
def confirm_meeting(poll_id: str, slot: str, place: str = "") -> dict:
    """회의 시간을 확정하고, 참석자에게 보낼 확정 안내문 초안을 돌려줍니다.

    메일은 보내지 않습니다. 초안을 확인한 뒤 메일 앱으로 발송하세요.

    Args:
        poll_id: 조율표 id
        slot: 확정할 시간. 예) 2026-09-22 14:00
        place: 장소. 비우면 조율표에 적힌 장소를 씁니다
    """
    poll = store.get(poll_id)
    if poll is None or poll.get("kind") != "poll":
        return {"ok": False, "error": f"조율표를 찾을 수 없습니다: {poll_id}"}

    where = place or poll.get("place", "")
    store.update(poll_id, status="확정", confirmed_slot=slot, place=where, confirmed_on=today_iso())
    replies = _replies(poll_id)
    cannot = [
        r.get("participant") for r in replies
        if r.get("slots") and slot not in r.get("slots", [])
    ]
    lines = [
        f"[회의 확정] {poll.get('title')}",
        "",
        f"일시: {slot} ({poll.get('duration_minutes', 60)}분)",
    ]
    if where:
        lines.append(f"장소: {where}")
    lines.append(f"참석: {', '.join(poll.get('participants', []))}")
    lines += ["", "조율에 응해 주셔서 감사합니다.", f"주최: {poll.get('organizer')}"]
    notice = "\n".join(lines)
    answer = {"ok": True, "confirmed_slot": slot, "notice_draft": notice}
    if cannot:
        answer["conflicts"] = cannot
        answer["warning"] = "이 시간이 어렵다고 답한 사람이 있습니다. 확인하고 보내세요."
    return answer


@mcp.tool()
def draft_reminder(poll_id: str) -> dict:
    """아직 회신하지 않은 사람에게 보낼 리마인드 메일 초안을 만들어 줍니다.

    Args:
        poll_id: 조율표 id
    """
    status = poll_status(poll_id)
    if not status.get("title"):
        return status
    pending = status.get("not_answered", [])
    if not pending:
        return {"ok": True, "pending": [], "message": "모두 회신했습니다. 리마인드가 필요 없습니다."}

    poll = store.get(poll_id)
    lines = [
        f"[회신 요청] {poll.get('title')} 회의 시간",
        "",
        "아직 회신을 받지 못했습니다. 가능한 시간을 알려 주세요.",
    ]
    lines += [f"  {i + 1}) {s}" for i, s in enumerate(poll.get("candidate_slots", []))]
    if poll.get("reply_by"):
        lines += ["", f"회신 기한: {poll['reply_by']}"]
    draft = "\n".join(lines)
    return {"ok": True, "pending": pending, "reminder_draft": draft, "to": pending}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
