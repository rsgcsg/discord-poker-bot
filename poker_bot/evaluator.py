from __future__ import annotations

from collections import Counter
from itertools import combinations

from .cards import Card, VALUE_RANK, cards_text


CATEGORY_NAME = {
    8: "Straight Flush",
    7: "Four of a Kind",
    6: "Full House",
    5: "Flush",
    4: "Straight",
    3: "Three of a Kind",
    2: "Two Pair",
    1: "Pair",
    0: "High Card",
}


def _straight_high(ranks: list[int]) -> int | None:
    unique = sorted(set(ranks), reverse=True)
    if 14 in unique:
        unique.append(1)
    for index in range(len(unique) - 4):
        window = unique[index : index + 5]
        if window[0] - window[4] == 4 and len(set(window)) == 5:
            return 5 if window[0] == 5 else window[0]
    return None


def evaluate_five(cards: tuple[Card, ...]) -> tuple[int, tuple[int, ...]]:
    ranks = [card.rank for card in cards]
    suits = [card.suit for card in cards]
    counts = Counter(ranks)
    count_groups = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
    is_flush = len(set(suits)) == 1
    straight = _straight_high(ranks)

    if is_flush and straight:
        return 8, (straight,)

    if count_groups[0][1] == 4:
        quad = count_groups[0][0]
        kicker = max(rank for rank in ranks if rank != quad)
        return 7, (quad, kicker)

    if count_groups[0][1] == 3 and count_groups[1][1] == 2:
        return 6, (count_groups[0][0], count_groups[1][0])

    if is_flush:
        return 5, tuple(sorted(ranks, reverse=True))

    if straight:
        return 4, (straight,)

    if count_groups[0][1] == 3:
        trip = count_groups[0][0]
        kickers = sorted((rank for rank in ranks if rank != trip), reverse=True)
        return 3, (trip, *kickers)

    pairs = sorted((rank for rank, count in counts.items() if count == 2), reverse=True)
    if len(pairs) == 2:
        kicker = max(rank for rank in ranks if rank not in pairs)
        return 2, (pairs[0], pairs[1], kicker)

    if len(pairs) == 1:
        pair = pairs[0]
        kickers = sorted((rank for rank in ranks if rank != pair), reverse=True)
        return 1, (pair, *kickers)

    return 0, tuple(sorted(ranks, reverse=True))


def best_hand(cards: list[Card]) -> tuple[tuple[int, tuple[int, ...]], tuple[Card, ...]]:
    if len(cards) < 5:
        raise ValueError("At least 5 cards are required.")
    best_score: tuple[int, tuple[int, ...]] | None = None
    best_cards: tuple[Card, ...] | None = None
    for combo in combinations(cards, 5):
        score = evaluate_five(combo)
        if best_score is None or score > best_score:
            best_score = score
            best_cards = combo
    assert best_score is not None and best_cards is not None
    return best_score, best_cards


def describe_score(score: tuple[int, tuple[int, ...]]) -> str:
    category, tie_breakers = score
    ranks = " ".join(VALUE_RANK.get(value, str(value)) for value in tie_breakers)
    return f"{CATEGORY_NAME[category]} ({ranks})"


def describe_best(cards: list[Card]) -> str:
    score, combo = best_hand(cards)
    return f"{describe_score(score)}: {cards_text(list(combo))}"
