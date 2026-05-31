from __future__ import annotations

from io import BytesIO
import math

from PIL import Image, ImageDraw, ImageFont

from .cards import Card, VALUE_RANK
from .game import Phase, PokerTable, PlayerState


WIDTH = 1200
HEIGHT = 760
CARD_W = 74
CARD_H = 104
TABLE_BOX = (165, 105, WIDTH - 165, HEIGHT - 105)
RED_SUITS = {"h", "d"}
SUIT_MARKS = {"c": "♣", "d": "♦", "h": "♥", "s": "♠"}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


FONT_TITLE = _font(34, True)
FONT_LARGE = _font(28, True)
FONT_MEDIUM = _font(20, True)
FONT_SMALL = _font(16)
FONT_TINY = _font(13)


def render_table(table: PokerTable) -> BytesIO:
    image = Image.new("RGB", (WIDTH, HEIGHT), (18, 25, 34))
    draw = ImageDraw.Draw(image)
    _draw_background(draw)
    _draw_table(draw, table)
    _draw_board(draw, table)
    _draw_players(draw, table)
    _draw_status_panel(draw, table)

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def render_private_hand(cards: list[Card]) -> BytesIO:
    image = Image.new("RGB", (320, 180), (18, 25, 34))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((18, 18, 302, 162), radius=24, fill=(27, 38, 50), outline=(92, 112, 129), width=2)
    _draw_text_center(draw, (160, 42), "Your hand", FONT_MEDIUM, (236, 241, 245))
    start_x = 80
    for index, card in enumerate(cards):
        _draw_card(draw, start_x + index * 86, 64, card)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def _draw_background(draw: ImageDraw.ImageDraw) -> None:
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(16 + ratio * 8)
        g = int(24 + ratio * 14)
        b = int(32 + ratio * 16)
        draw.line((0, y, WIDTH, y), fill=(r, g, b))


def _draw_table(draw: ImageDraw.ImageDraw, table: PokerTable) -> None:
    shadow = (TABLE_BOX[0] + 10, TABLE_BOX[1] + 14, TABLE_BOX[2] + 10, TABLE_BOX[3] + 14)
    draw.ellipse(shadow, fill=(5, 8, 11))
    draw.ellipse(TABLE_BOX, fill=(25, 93, 67), outline=(157, 114, 56), width=16)
    inner = (TABLE_BOX[0] + 42, TABLE_BOX[1] + 42, TABLE_BOX[2] - 42, TABLE_BOX[3] - 42)
    draw.ellipse(inner, fill=(20, 120, 78), outline=(38, 148, 98), width=4)
    draw.ellipse((430, 260, 770, 500), fill=(18, 103, 70), outline=(64, 153, 104), width=3)
    _draw_text_center(draw, (600, 300), "TEXAS HOLD'EM", FONT_TITLE, (220, 205, 151))
    _draw_text_center(draw, (600, 335), f"{table.small_blind}/{table.big_blind} blinds", FONT_SMALL, (188, 213, 199))


def _draw_board(draw: ImageDraw.ImageDraw, table: PokerTable) -> None:
    start_x = 405
    y = 362
    for index in range(5):
        x = start_x + index * (CARD_W + 10)
        if index < len(table.board):
            _draw_card(draw, x, y, table.board[index])
        else:
            _draw_empty_card(draw, x, y)
    pot = sum(player.committed for player in table.players.values())
    draw.rounded_rectangle((500, 486, 700, 530), radius=18, fill=(16, 65, 49), outline=(94, 179, 125), width=2)
    _draw_text_center(draw, (600, 508), f"Pot {pot}", FONT_LARGE, (246, 231, 166))


def _draw_players(draw: ImageDraw.ImageDraw, table: PokerTable) -> None:
    players = table.seat_order()
    roles = table.seat_roles()
    for index, player in enumerate(players):
        cx, cy = _seat_position(index, max(len(players), 2))
        _draw_seat(draw, table, player, index, cx, cy, roles.get(player.user_id, []))


def _draw_seat(
    draw: ImageDraw.ImageDraw,
    table: PokerTable,
    player: PlayerState,
    seat_index: int,
    cx: int,
    cy: int,
    roles: list[str],
) -> None:
    active = player.user_id == table.current_user_id
    folded = player.folded
    seat_color = (39, 54, 70)
    outline = (93, 117, 139)
    if active:
        seat_color = (56, 75, 48)
        outline = (239, 197, 87)
    if folded:
        seat_color = (49, 50, 55)
        outline = (90, 93, 99)

    panel = (cx - 115, cy - 47, cx + 115, cy + 54)
    draw.rounded_rectangle((panel[0] + 4, panel[1] + 6, panel[2] + 4, panel[3] + 6), radius=18, fill=(7, 10, 14))
    draw.rounded_rectangle(panel, radius=18, fill=seat_color, outline=outline, width=3)

    draw.ellipse((panel[0] + 12, panel[1] + 15, panel[0] + 58, panel[1] + 61), fill=(26, 33, 42), outline=(117, 135, 151), width=2)
    _draw_text_center(draw, (panel[0] + 35, panel[1] + 38), str(seat_index + 1), FONT_SMALL, (229, 236, 242))

    name = _fit_text(player.name, 15)
    draw.text((panel[0] + 70, panel[1] + 14), name, fill=(238, 243, 247), font=FONT_MEDIUM)
    draw.text((panel[0] + 70, panel[1] + 41), f"{player.chips} chips", fill=(192, 207, 218), font=FONT_SMALL)

    status = _player_status(player, roles)
    draw.text((panel[0] + 14, panel[3] - 24), status, fill=(241, 214, 131), font=FONT_TINY)
    if player.bet > 0:
        _draw_chip_stack(draw, cx - 18, cy + 62, player.bet)

    cards = _visible_cards(table, player)
    if cards:
        card_x = cx - CARD_W - 4
        card_y = cy - 124 if cy > HEIGHT / 2 else cy + 62
        for index, card in enumerate(cards):
            if card is None:
                _draw_card_back(draw, card_x + index * 46, card_y)
            else:
                _draw_card(draw, card_x + index * 46, card_y, card, scale=0.76)


def _visible_cards(table: PokerTable, player: PlayerState) -> list[Card | None]:
    if not table.hand_running and table.phase != Phase.FINISHED:
        return []
    if len(player.hole) == 2:
        return player.hole
    if len(player.offline_cards) == 2 and table.phase == Phase.FINISHED:
        return player.offline_cards
    if table.hand_running and not player.folded:
        return [None, None]
    return []


def _player_status(player: PlayerState, roles: list[str]) -> str:
    tags = list(roles)
    if player.folded:
        tags.append("FOLD")
    elif player.all_in:
        tags.append("ALL-IN")
    elif player.bet:
        tags.append(f"BET {player.bet}")
    return " | ".join(tags) if tags else "PLAYING"


def _seat_position(index: int, total: int) -> tuple[int, int]:
    cx = WIDTH // 2
    cy = HEIGHT // 2
    rx = 470
    ry = 285
    angle = -math.pi / 2 + (2 * math.pi * index / total)
    return int(cx + rx * math.cos(angle)), int(cy + ry * math.sin(angle))


def _draw_status_panel(draw: ImageDraw.ImageDraw, table: PokerTable) -> None:
    draw.rounded_rectangle((22, 22, 354, 136), radius=18, fill=(24, 33, 43), outline=(72, 91, 108), width=2)
    draw.text((42, 38), f"{table.mode.upper()} TABLE", font=FONT_MEDIUM, fill=(240, 245, 248))
    draw.text((42, 66), f"Phase: {table.phase.value}", font=FONT_SMALL, fill=(195, 210, 221))
    current = table.players.get(table.current_user_id) if table.current_user_id else None
    turn = current.name if current else "-"
    call = table.amount_to_call(current.user_id) if current else 0
    draw.text((42, 91), f"Turn: {_fit_text(turn, 22)}", font=FONT_SMALL, fill=(239, 197, 87))
    draw.text((42, 113), f"To call: {call}", font=FONT_SMALL, fill=(195, 210, 221))

    if table.last_result:
        draw.rounded_rectangle((846, 22, 1178, 136), radius=18, fill=(24, 33, 43), outline=(72, 91, 108), width=2)
        lines = _wrap(table.last_result.replace("\n", " | "), 36)[:4]
        for index, line in enumerate(lines):
            draw.text((866, 38 + index * 22), line, font=FONT_TINY, fill=(226, 235, 240))


def _draw_card(draw: ImageDraw.ImageDraw, x: int, y: int, card: Card, scale: float = 1.0) -> None:
    w = int(CARD_W * scale)
    h = int(CARD_H * scale)
    radius = int(10 * scale)
    draw.rounded_rectangle((x, y, x + w, y + h), radius=radius, fill=(246, 247, 242), outline=(28, 32, 36), width=max(1, int(2 * scale)))
    rank = VALUE_RANK[card.rank]
    suit = SUIT_MARKS[card.suit]
    color = (177, 45, 57) if card.suit in RED_SUITS else (24, 28, 34)
    draw.text((x + int(8 * scale), y + int(6 * scale)), rank, font=_font(max(10, int(22 * scale)), True), fill=color)
    draw.text((x + int(10 * scale), y + int(30 * scale)), suit, font=_font(max(9, int(16 * scale)), True), fill=color)
    _draw_text_center(draw, (x + w // 2, y + h // 2 + int(10 * scale)), suit, _font(max(14, int(34 * scale)), True), color)


def _draw_card_back(draw: ImageDraw.ImageDraw, x: int, y: int, scale: float = 0.76) -> None:
    w = int(CARD_W * scale)
    h = int(CARD_H * scale)
    draw.rounded_rectangle((x, y, x + w, y + h), radius=int(9 * scale), fill=(41, 76, 154), outline=(218, 225, 233), width=2)
    inner = (x + 8, y + 8, x + w - 8, y + h - 8)
    draw.rounded_rectangle(inner, radius=int(6 * scale), outline=(122, 157, 225), width=2)
    _draw_text_center(draw, (x + w // 2, y + h // 2), "P", FONT_MEDIUM, (218, 225, 233))


def _draw_empty_card(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.rounded_rectangle((x, y, x + CARD_W, y + CARD_H), radius=10, fill=(23, 93, 67), outline=(64, 152, 103), width=2)


def _draw_chip_stack(draw: ImageDraw.ImageDraw, x: int, y: int, amount: int) -> None:
    colors = [(192, 42, 59), (230, 220, 132), (52, 109, 192)]
    for index, color in enumerate(colors):
        draw.ellipse((x + index * 10, y - index * 3, x + 34 + index * 10, y + 16 - index * 3), fill=color, outline=(238, 242, 246))
    draw.rounded_rectangle((x + 42, y - 7, x + 105, y + 20), radius=10, fill=(22, 30, 39), outline=(98, 117, 133), width=1)
    _draw_text_center(draw, (x + 74, y + 6), str(amount), FONT_TINY, (240, 245, 248))


def _draw_text_center(
    draw: ImageDraw.ImageDraw,
    center: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    x = center[0] - (bbox[2] - bbox[0]) // 2
    y = center[1] - (bbox[3] - bbox[1]) // 2
    draw.text((x, y), text, font=font, fill=fill)


def _fit_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)] + "."


def _wrap(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        next_line = f"{current} {word}".strip()
        if len(next_line) > max_chars and current:
            lines.append(current)
            current = word
        else:
            current = next_line
    if current:
        lines.append(current)
    return lines
