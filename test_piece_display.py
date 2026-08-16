from types import SimpleNamespace

from serve_crownline import _piece_dict


class _FakeGame:
    def __init__(self, cooldown):
        self.cooldown = cooldown

    def piece_cooldown(self, owner, value):
        return self.cooldown


def test_normal_piece_face_value_keeps_identity_and_cooldown():
    piece = SimpleNamespace(owner="W", value=5, king=False)
    payload = _piece_dict(_FakeGame(2), (0, 0), piece)

    assert payload["piece_id"] == 5
    assert payload["face_value"] == 5
    assert payload["value"] == "5²"
    assert payload["cooldown"] == 2


def test_king_face_value_doubles_without_changing_piece_identity():
    piece = SimpleNamespace(owner="B", value=5, king=True)
    payload = _piece_dict(_FakeGame(3), (0, 0), piece)

    assert payload["piece_id"] == 5
    assert payload["face_value"] == 10
    assert payload["value"] == "10³"
    assert payload["cooldown"] == 3
