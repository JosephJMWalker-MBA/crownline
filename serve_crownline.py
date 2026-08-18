from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse

from crownline import MeldChoiceRequired, coord_to_alg, new_set, rules_mode_label
from crownline_ai import choose_computer_action
from crownline_maturity_product_candidate import RepeatAwareMaturityStructuralTTOpponent

ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
HOST = "127.0.0.1"
PORT = 8765

_lock = Lock()
# Browser play now launches into the v1.1 candidate profile. The v1.0 rules
# remain available as a selectable legacy/official profile; this only changes
# the interactive launch default, not the underlying rules definitions.
_session = new_set(first_game_white="A", rules_mode="candidate")

# Research opponents are intentionally long-lived. The p200 policy is based on
# exact afterstates produced earlier in the same game, so recreating this object
# on every HTTP request would silently erase the measured trajectory behavior.
# The engine itself clears memory when a new game/scenario is detected.
_RESEARCH_OPPONENTS = {
    participant: RepeatAwareMaturityStructuralTTOpponent(
        name=f"research-strong-{participant}",
        budget_ms=150.0,
        max_depth=4,
        repeat_penalty=200.0,
        maturity_weight=10.0,
    )
    for participant in ("A", "B")
}

_SUPERSCRIPT = {1: "¹", 2: "²", 3: "³"}
_LINE_NAMES = (
    "Top row",
    "Middle row",
    "Bottom row",
    "Left column",
    "Center column",
    "Right column",
    "Diagonal ↘",
    "Diagonal ↗",
)


def _meld_dict(meld):
    return {
        "line": list(meld.line),
        "piece_ids": list(meld.piece_ids),
        "points": meld.points,
        "royal": meld.royal,
    }


def _move_dict(move):
    return {
        "notation": move.notation(),
        "origin": coord_to_alg(move.path[0]),
        "destination": coord_to_alg(move.path[-1]),
        "path": [coord_to_alg(square) for square in move.path],
        "captured": [coord_to_alg(square) for square in move.captured],
        "is_capture": move.is_capture,
    }


def _piece_dict(game, position, piece):
    cooldown = game.piece_cooldown(piece.owner, piece.value)
    # The top face communicates current scoring consequence, while piece_id
    # preserves the underlying identity used by the rules engine. Kings therefore
    # show double their base value. A superscript remains the compact visual
    # countdown for own turns until that piece may score another Crownline.
    face_value = piece.value * (2 if piece.king else 1)
    display_value = f"{face_value}{_SUPERSCRIPT.get(cooldown, '')}"
    return {
        "square": coord_to_alg(position),
        "owner": piece.owner,
        "piece_id": piece.value,
        "face_value": face_value,
        "value": display_value,
        "king": piece.king,
        "cooldown": cooldown,
    }


def _diagnostic_dict(item):
    return {
        "line": list(item["line"]),
        "piece_ids": list(item["piece_ids"]),
        "reasons": [dict(reason) for reason in item["reasons"]],
    }


def _line_tracker(game, player):
    retired = game.retired_lines(player)
    return [
        {
            "index": index,
            "name": _LINE_NAMES[index],
            "line": list(line),
            "retired": line in retired,
        }
        for index, line in enumerate(game.variant.crown_lines)
    ]


def _feedback_before_move(game, move):
    return {
        "meld_diagnostics": [
            _diagnostic_dict(item)
            for item in game.crowned_meld_diagnostics_after(move)
        ],
    }


def _normalize_ai_profile(value) -> str:
    profile = "baseline" if value is None else str(value).strip().lower()
    aliases = {
        "computer": "baseline",
        "standard": "baseline",
        "strong": "research",
        "research-strong": "research",
    }
    profile = aliases.get(profile, profile)
    if profile not in ("baseline", "research"):
        raise ValueError("profile must be 'baseline' or 'research'")
    return profile


def _choose_computer_move(crownline_set, *, participant, profile, depth):
    """Choose an action and return transport-safe evidence about the AI used."""

    normalized = _normalize_ai_profile(profile)
    if normalized == "baseline":
        notation, meld_line = choose_computer_action(
            crownline_set,
            participant=participant,
            depth=depth,
        )
        return notation, meld_line, {
            "profile": "baseline",
            "label": f"Baseline A · depth {depth}",
            "depth": depth,
        }

    if crownline_set.rules_mode != "candidate":
        raise ValueError("Research / Strong AI is validated only for Crownline v1.1")

    engine = _RESEARCH_OPPONENTS[participant]
    notation, meld_line, stats = engine.choose_with_stats(crownline_set, participant)
    return notation, meld_line, {
        "profile": "research",
        "label": "Research / Strong · 150 ms",
        "budget_ms": engine.budget_ms,
        "max_depth": engine.max_depth,
        "repeat_penalty": engine.repeat_penalty,
        "maturity_weight": engine.maturity_weight,
        "elapsed_ms": stats.search.elapsed_ms,
        "completed_depth": stats.search.completed_depth,
        "attempted_depth": stats.search.attempted_depth,
        "timed_out": stats.search.timed_out,
        "search_nodes": stats.search.total_expanded_nodes,
        "repeat_candidates_at_root": stats.repeat_candidates_at_root,
        "selected_repeat_count": stats.selected_repeat_count,
    }


def state_payload():
    crownline_set = _session
    game = crownline_set.current_game
    score_w = game.score("W")
    score_b = game.score("B")
    aggregate_a, aggregate_b = crownline_set.aggregate_scores()
    legal_moves = game.legal_moves()

    pieces = [
        _piece_dict(game, position, piece)
        for position, piece in sorted(game.board.items(), key=lambda item: coord_to_alg(item[0]))
    ]

    crown_squares = [
        {"square": square, "value": value}
        for square, value in game.variant.crown_values
    ]

    return {
        "set": {
            "set_index": crownline_set.set_index,
            "game_number": crownline_set.game_number,
            "first_game_white": crownline_set.first_game_white,
            "white_participant": crownline_set.white_participant,
            "black_participant": crownline_set.black_participant,
            "rules": {
                "mode": crownline_set.rules_mode,
                "label": rules_mode_label(crownline_set.rules_mode),
                "experimental": crownline_set.rules_mode != "official",
            },
            "aggregate": {"A": aggregate_a, "B": aggregate_b},
            "completed_games": [
                {
                    "game_number": result.game_number,
                    "white_participant": result.white_participant,
                    "score_a": result.score_a,
                    "score_b": result.score_b,
                    "winner": result.winner,
                }
                for result in crownline_set.completed_games
            ],
            "set_over": crownline_set.set_over,
            "winner": crownline_set.winner(),
        },
        "game": {
            "variant": {
                "number": game.variant.number,
                "name": game.variant.name,
                "playable_parity": game.variant.playable_parity,
            },
            "turn": game.turn,
            "turn_participant": crownline_set.participant_for_color(game.turn),
            "ply": game.ply,
            "game_over": game.game_over,
            "end_reason": game.end_reason,
            "winner": game.winner(),
            "triggering_player": game.triggering_player,
            "capture_banks": {"W": game.capture_bank_w, "B": game.capture_bank_b},
            "cooldowns": {
                "W": dict(game.cooldowns_w),
                "B": dict(game.cooldowns_b),
            },
            "scores": {
                "W": {
                    "capture": score_w.capture_bank,
                    "board": score_w.board_value,
                    "melds": score_w.meld_count,
                    "meld_bonus": score_w.meld_bonus,
                    "total": score_w.total,
                },
                "B": {
                    "capture": score_b.capture_bank,
                    "board": score_b.board_value,
                    "melds": score_b.meld_count,
                    "meld_bonus": score_b.meld_bonus,
                    "total": score_b.total,
                },
            },
            "melds": {
                "W": [_meld_dict(meld) for meld in game.melds_w],
                "B": [_meld_dict(meld) for meld in game.melds_b],
            },
            "crownline_tracker": {
                "W": _line_tracker(game, "W"),
                "B": _line_tracker(game, "B"),
            },
            "pieces": pieces,
            "crown_squares": crown_squares,
            "crown_lines": [list(line) for line in game.variant.crown_lines],
            "legal_moves": [move.notation() for move in legal_moves],
            "legal_move_details": [_move_dict(move) for move in legal_moves],
        },
    }


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/state":
            with _lock:
                self._send_json(200, state_payload())
            return

        relative = "index.html" if path == "/" else path.lstrip("/")
        target = (WEB_ROOT / relative).resolve()
        if WEB_ROOT.resolve() not in target.parents and target != WEB_ROOT.resolve():
            self.send_error(403)
            return
        if not target.is_file():
            self.send_error(404)
            return

        raw = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        global _session
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            with _lock:
                if path == "/api/move":
                    notation = body.get("move")
                    if not notation:
                        raise ValueError("move is required")
                    meld_line = body.get("meld_line")
                    meld_line = tuple(meld_line) if meld_line else None
                    before = _session.current_game
                    move = before.move_from_notation(notation)
                    feedback = _feedback_before_move(before, move)
                    before_melds = len(before.melds(before.turn))
                    mover = before.turn
                    _session = _session.apply_move(move, meld_line=meld_line)
                    payload = state_payload()
                    after = _session.current_game
                    feedback["meld_scored"] = len(after.melds(mover)) > before_melds
                    payload["move_feedback"] = feedback
                    self._send_json(200, payload)
                    return

                if path == "/api/computer-move":
                    participant = body.get("participant", "B")
                    if participant not in ("A", "B"):
                        raise ValueError("participant must be 'A' or 'B'")
                    depth = int(body.get("depth", 2))
                    if depth < 1 or depth > 4:
                        raise ValueError("depth must be between 1 and 4")
                    profile = _normalize_ai_profile(body.get("profile"))
                    notation, meld_line, ai_evidence = _choose_computer_move(
                        _session,
                        participant=participant,
                        profile=profile,
                        depth=depth,
                    )
                    before = _session.current_game
                    move = before.move_from_notation(notation)
                    feedback = _feedback_before_move(before, move)
                    before_melds = len(before.melds(before.turn))
                    mover = before.turn
                    _session = _session.apply_move(move, meld_line=meld_line)
                    payload = state_payload()
                    after = _session.current_game
                    feedback["meld_scored"] = len(after.melds(mover)) > before_melds
                    payload["move_feedback"] = feedback
                    payload["computer_action"] = {
                        "participant": participant,
                        "move": notation,
                        "meld_line": list(meld_line) if meld_line else None,
                        **ai_evidence,
                    }
                    self._send_json(200, payload)
                    return

                if path == "/api/advance":
                    _session = _session.advance_game()
                    self._send_json(200, state_payload())
                    return

                if path == "/api/reset":
                    first = body.get("first_game_white", "A")
                    rules_mode = body.get("rules_mode", _session.rules_mode)
                    _session = new_set(first_game_white=first, rules_mode=rules_mode)
                    self._send_json(200, state_payload())
                    return

                if path == "/api/continue":
                    next_first = body.get("first_game_white")
                    if not next_first:
                        raise ValueError("first_game_white is required")
                    _session = _session.continue_tied_set(next_first)
                    self._send_json(200, state_payload())
                    return

            self._send_json(404, {"error": "unknown endpoint"})
        except MeldChoiceRequired as exc:
            self._send_json(
                409,
                {
                    "error": "meld_choice_required",
                    "message": str(exc),
                    "options": [_meld_dict(meld) for meld in exc.options],
                },
            )
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": "invalid_request", "message": str(exc)})

    def log_message(self, format, *args):
        return


def main():
    print(f"Crownline v1 browser prototype: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
