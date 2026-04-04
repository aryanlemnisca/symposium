"""Output file content builders."""

from datetime import datetime, timezone


def build_transcript(messages: list, stats: dict, agent_names: list[str]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    mode = stats.get("mode", "brainstorm")
    title = "Stress Test Review — Full Transcript" if mode == "stress_test" else "Brainstorming Panel — Full Transcript"

    lines = [
        f"# {title}\n\n",
        f"**Date:** {ts}  |  **Model:** {stats.get('model', 'gemini')}\n",
        f"**Rounds:** {stats.get('total_rounds', '?')}/{stats.get('max_rounds', '?')}  |  "
        f"**Terminated:** {stats.get('terminated_by', '?')}\n",
        f"**Gate skips:** {stats.get('gate_skips', 0)}  |  "
        f"**Overseer injections:** {stats.get('overseer_injections', 0)}",
    ]

    if stats.get("phases_completed"):
        lines.append(f"  |  **Phases completed:** {stats['phases_completed']}")

    lines.append("\n\n---\n\n")

    msg_num = 0
    for msg in messages:
        src = getattr(msg, "source", "Unknown")
        content = getattr(msg, "content", "")
        if not (isinstance(content, str) and content.strip()):
            continue

        # Phase directive markers
        if src == "Overseer" and content.startswith("[PHASE"):
            lines.append(f"\n{'=' * 60}\n\n{content.strip()}\n\n{'=' * 60}\n\n")
        elif src == "Overseer" and content.startswith("[REVIEW CHAIR"):
            lines.append(f"### [REVIEW CHAIR]\n\n{content.strip()}\n\n---\n\n")
        elif src == "Overseer":
            lines.append(f"### [OVERSEER]\n\n{content.strip()}\n\n---\n\n")
        elif src in agent_names:
            msg_num += 1
            lines.append(f"### [{msg_num}] {src}\n\n{content.strip()}\n\n---\n\n")

    return "".join(lines)


def build_artifact(living_artifact: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    lines = ["# Brainstorming Panel — Living Artifact\n\n", f"*{ts}*\n\n" + "=" * 60 + "\n\n"]
    for section_name, content in living_artifact.items():
        lines.append(f"{content.strip()}\n\n{'─' * 60}\n\n")
    return "".join(lines)
