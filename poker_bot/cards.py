from __future__ import annotations

from dataclasses import dataclass
import random


RANKS = "23456789TJQKA"
SUITS = "cdhs"
RANK_VALUE = {rank: index + 2 for index, rank in enumerate(RANKS)}
VALUE_RANK = {value: rank for rank, value in RANK_VALUE.items()}
SUIT_SYMBOL = {
    "c": "clubs",
    "d": "diamonds",
    "h": "hearts",
    "s": "spades",
}


@dataclass(frozen=True, order=True)
class Card:
    rank: int
    suit: str

    @classmethod
    def parse(cls, text: str) -> "Card":
        token = text.strip()
        if len(token) != 2:
            raise ValueError(f"Invalid card '{text}'. Use format like Ah, Td, 7c.")
        rank, suit = token[0].upper(), token[1].lower()
        if rank not in RANK_VALUE or suit not in SUITS:
            raise ValueError(f"Invalid card '{text}'. Use ranks 2-9TJQKA and suits cdhs.")
        return cls(RANK_VALUE[rank], suit)

    def label(self) -> str:
        return f"{VALUE_RANK[self.rank]}{self.suit}"

    def pretty(self) -> str:
        suit_mark = {"c": "C", "d": "D", "h": "H", "s": "S"}[self.suit]
        return f"{VALUE_RANK[self.rank]}{suit_mark}"


class Deck:
    def __init__(self) -> None:
        self.cards = [Card(rank, suit) for rank in range(2, 15) for suit in SUITS]
        random.shuffle(self.cards)

    def draw(self, count: int = 1) -> list[Card]:
        if count > len(self.cards):
            raise RuntimeError("Deck is empty.")
        drawn = self.cards[:count]
        del self.cards[:count]
        return drawn


def parse_cards(text: str, expected: int | None = None) -> list[Card]:
    cards = [Card.parse(part) for part in text.replace(",", " ").split() if part.strip()]
    if expected is not None and len(cards) != expected:
        raise ValueError(f"Expected {expected} cards, got {len(cards)}.")
    if len(set(cards)) != len(cards):
        raise ValueError("Duplicate cards are not allowed.")
    return cards


def cards_text(cards: list[Card]) -> str:
    return " ".join(card.pretty() for card in cards) if cards else "-"
