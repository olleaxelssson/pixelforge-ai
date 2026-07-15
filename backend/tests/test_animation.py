from PIL import Image

from pixelforge.animation.actions import ANIMATION_ACTIONS, get_action
from pixelforge.animation.assembly import build_sprite_sheet, save_gif


def test_all_required_actions_present():
    ids = {a.id for a in ANIMATION_ACTIONS}
    assert ids == {
        "idle",
        "walk",
        "run",
        "attack",
        "death",
        "hurt",
        "jump",
        "cast",
        "mining",
        "fishing",
        "woodcutting",
        "crafting",
        "farming",
    }


def test_frame_descriptions_match_counts():
    for action in ANIMATION_ACTIONS:
        assert len(action.frame_descriptions) == action.frame_count


def test_get_action():
    assert get_action("walk").frame_count == 6
    assert get_action("nope") is None


def test_sprite_sheet_grid():
    frames = [Image.new("RGBA", (16, 16)) for _ in range(6)]
    sheet = build_sprite_sheet(frames, columns=3)
    assert sheet.size == (48, 32)


def test_gif_roundtrip(tmp_path):
    frames = [Image.new("RGBA", (8, 8), (i * 30, 0, 0, 255)) for i in range(3)]
    path = tmp_path / "anim.gif"
    save_gif(frames, str(path))
    gif = Image.open(path)
    assert gif.n_frames == 3
