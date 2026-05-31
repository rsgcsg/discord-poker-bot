from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from collections import OrderedDict
import secrets
import time
from typing import Iterable

from .cards import Card, Deck, cards_text, parse_cards
from .evaluator import best_hand, describe_score


class Phase(str, Enum):
    LOBBY = "lobby"
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    FINISHED = "finished"


class Action(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    RAISE_TO = "raise_to"
    ALL_IN = "all_in"


@dataclass
class PlayerState:
    user_id: int
    name: str
    chips: int
    hole: list[Card] = field(default_factory=list)
    folded: bool = False
    all_in: bool = False
    bet: int = 0
    committed: int = 0
    start_chips: int = 0
    offline_cards: list[Card] = field(default_factory=list)
    web_token: str = field(default_factory=lambda: secrets.token_urlsafe(18))

    def reset_for_hand(self) -> None:
        self.hole = []
        self.folded = False
        self.all_in = False
        self.bet = 0
        self.committed = 0
        self.start_chips = self.chips
        self.offline_cards = []


@dataclass
class PotAward:
    user_id: int
    amount: int
    reason: str


@dataclass
class PokerTable:
    channel_id: int
    mode: str
    small_blind: int
    big_blind: int
    starting_chips: int
    players: dict[int, PlayerState] = field(default_factory=dict)
    phase: Phase = Phase.LOBBY
    dealer_index: int = 0
    current_user_id: int | None = None
    deck: Deck | None = None
    board: list[Card] = field(default_factory=list)
    highest_bet: int = 0
    min_raise: int = 0
    acted: set[int] = field(default_factory=set)
    last_result: str = ""
    hand_running: bool = False
    stats_recorded: bool = False
    max_seats: int = 10
    last_action_at: float = field(default_factory=time.time)
    hand_timeout_seconds: int = 900
    game_over: bool = False

    def add_player(self, user_id: int, name: str) -> str:
        if self.hand_running:
            raise ValueError("A hand is already running.")
        if user_id in self.players:
            self.players[user_id].name = name
            return f"{name} is already seated."
        if len(self.players) >= self.max_seats:
            raise ValueError(f"This table is full. Maximum seats: {self.max_seats}.")
        self.players[user_id] = PlayerState(user_id, name, self.starting_chips)
        return f"{name} joined with {self.starting_chips} chips."

    def remove_player(self, user_id: int) -> str:
        if self.hand_running:
            raise ValueError("A hand is already running.")
        player = self.players.pop(user_id, None)
        if player is None:
            raise ValueError("You are not seated.")
        self.dealer_index %= max(1, len(self.players))
        return f"{player.name} left the table."

    def seat_order(self) -> list[PlayerState]:
        return list(self.players.values())

    def move_player_to_seat(self, user_id: int, seat_number: int) -> str:
        if self.hand_running:
            raise ValueError("Seats can only be changed between hands.")
        if user_id not in self.players:
            raise ValueError("Player is not seated.")
        if seat_number < 1 or seat_number > len(self.players):
            raise ValueError(f"Seat number must be between 1 and {len(self.players)}.")
        player = self.players[user_id]
        ordered = [item for item in self.players.items() if item[0] != user_id]
        ordered.insert(seat_number - 1, (user_id, player))
        self.players = OrderedDict(ordered)
        self.dealer_index %= len(self.players)
        return f"{player.name} moved to seat {seat_number}."

    def swap_seats(self, first_user_id: int, second_user_id: int) -> str:
        if self.hand_running:
            raise ValueError("Seats can only be changed between hands.")
        if first_user_id not in self.players or second_user_id not in self.players:
            raise ValueError("Both players must be seated.")
        items = list(self.players.items())
        first_index = next(index for index, item in enumerate(items) if item[0] == first_user_id)
        second_index = next(index for index, item in enumerate(items) if item[0] == second_user_id)
        items[first_index], items[second_index] = items[second_index], items[first_index]
        self.players = OrderedDict(items)
        self.dealer_index %= len(self.players)
        return f"{self.players[second_user_id].name} and {self.players[first_user_id].name} swapped seats."

    def start_hand(self) -> list[int]:
        self.expire_if_needed()
        if self.game_over:
            raise ValueError("This table is game over.")
        if self.hand_running:
            raise ValueError("A hand is already running.")
        seated = [player for player in self.players.values() if player.chips > 0]
        if len(seated) < 2:
            raise ValueError("At least 2 players with chips are required.")
        for player in seated:
            player.reset_for_hand()

        self.phase = Phase.PREFLOP
        self.hand_running = True
        self.board = []
        self.deck = Deck()
        self.highest_bet = 0
        self.min_raise = self.big_blind
        self.acted = set()
        self.last_result = ""
        self.stats_recorded = False
        self.last_action_at = time.time()
        self.game_over = False

        order = self.active_order(include_folded=True)
        self.dealer_index %= len(order)
        for player in order:
            player.hole = self.deck.draw(2) if self.mode == "online" else []

        sb_id, bb_id = self.blind_positions(order)
        self._commit(sb_id, min(self.small_blind, self.players[sb_id].chips))
        self._commit(bb_id, min(self.big_blind, self.players[bb_id].chips))
        self.highest_bet = max(self.players[sb_id].bet, self.players[bb_id].bet)
        if self.players[sb_id].chips == 0:
            self.players[sb_id].all_in = True
        if self.players[bb_id].chips == 0:
            self.players[bb_id].all_in = True

        starter = self.next_to_act_after(bb_id) if len(order) > 2 else sb_id
        self.current_user_id = self._first_actionable_from(starter)
        self._auto_advance_if_needed()
        return [player.user_id for player in order]

    def blind_positions(self, order: list[PlayerState]) -> tuple[int, int]:
        if len(order) == 2:
            small = order[self.dealer_index].user_id
            big = order[(self.dealer_index + 1) % len(order)].user_id
        else:
            small = order[(self.dealer_index + 1) % len(order)].user_id
            big = order[(self.dealer_index + 2) % len(order)].user_id
        return small, big

    def seat_roles(self) -> dict[int, list[str]]:
        roles: dict[int, list[str]] = {player.user_id: [] for player in self.seat_order()}
        order = self.active_order(include_folded=True)
        if not order:
            return roles
        dealer = order[self.dealer_index % len(order)].user_id
        roles.setdefault(dealer, []).append("D")
        if self.hand_running:
            small, big = self.blind_positions(order)
            roles.setdefault(small, []).append("SB")
            roles.setdefault(big, []).append("BB")
        return roles

    def active_order(self, include_folded: bool = False) -> list[PlayerState]:
        order = list(self.players.values())
        return [
            player
            for player in order
            if player.start_chips > 0 or (not self.hand_running and player.chips > 0)
            if include_folded or not player.folded
        ]

    def not_folded(self) -> list[PlayerState]:
        return [player for player in self.players.values() if player.start_chips > 0 and not player.folded]

    def actionable(self) -> list[PlayerState]:
        return [
            player
            for player in self.not_folded()
            if not player.all_in and player.chips > 0
        ]

    def amount_to_call(self, user_id: int) -> int:
        return max(0, self.highest_bet - self.players[user_id].bet)

    def apply_action(self, user_id: int, action: Action, amount: int | None = None) -> str:
        self.expire_if_needed()
        if self.phase not in {Phase.PREFLOP, Phase.FLOP, Phase.TURN, Phase.RIVER}:
            raise ValueError("No betting round is active.")
        if user_id != self.current_user_id:
            current = self.players.get(self.current_user_id)
            raise ValueError(f"It is {current.name if current else 'another player'}'s turn.")
        player = self.players[user_id]
        if player.folded or player.all_in:
            raise ValueError("This player cannot act.")

        call_amount = self.amount_to_call(user_id)
        message = ""
        if action == Action.FOLD:
            player.folded = True
            self.acted.add(user_id)
            message = f"{player.name} folds."
        elif action == Action.CHECK:
            if call_amount != 0:
                raise ValueError(f"Cannot check. Need {call_amount} to call.")
            self.acted.add(user_id)
            message = f"{player.name} checks."
        elif action == Action.CALL:
            paid = self._commit(user_id, min(call_amount, player.chips))
            self.acted.add(user_id)
            message = f"{player.name} calls {paid}."
        elif action == Action.ALL_IN:
            old_highest = self.highest_bet
            paid = self._commit(user_id, player.chips)
            player.all_in = True
            if player.bet > self.highest_bet:
                self.highest_bet = player.bet
                raise_size = player.bet - old_highest
                if raise_size >= self.min_raise:
                    self.min_raise = raise_size
                    self.acted = {user_id}
                else:
                    self.acted.add(user_id)
            else:
                self.acted.add(user_id)
            message = f"{player.name} goes all-in for {paid}."
        elif action == Action.RAISE_TO:
            if amount is None:
                raise ValueError("Raise amount is required.")
            if amount <= self.highest_bet:
                raise ValueError(f"Raise total must exceed current bet {self.highest_bet}.")
            required = self.highest_bet + self.min_raise
            if amount < required and amount < player.bet + player.chips:
                raise ValueError(f"Minimum raise total is {required}.")
            to_pay = amount - player.bet
            if to_pay > player.chips:
                raise ValueError("Not enough chips for that raise.")
            old_highest = self.highest_bet
            paid = self._commit(user_id, to_pay)
            self.highest_bet = player.bet
            raise_size = self.highest_bet - old_highest
            if player.chips == 0:
                player.all_in = True
            if raise_size >= self.min_raise:
                self.min_raise = raise_size
                self.acted = {user_id}
            else:
                self.acted.add(user_id)
            message = f"{player.name} raises to {amount} ({paid} more)."

        self._after_action()
        self.last_action_at = time.time()
        return message

    def legal_actions_for(self, user_id: int) -> list[str]:
        self.expire_if_needed()
        if user_id != self.current_user_id:
            return []
        player = self.players.get(user_id)
        if player is None or player.folded or player.all_in or player.chips <= 0:
            return []
        to_call = self.amount_to_call(user_id)
        if to_call > 0:
            return [Action.CALL.value, Action.RAISE_TO.value, Action.ALL_IN.value, Action.FOLD.value]
        return [Action.CHECK.value, Action.RAISE_TO.value, Action.ALL_IN.value]

    def can_start_next_hand(self) -> bool:
        return not self.hand_running and len([player for player in self.players.values() if player.chips > 0]) >= 2 and not self.game_over

    def expire_if_needed(self) -> bool:
        if not self.hand_running:
            return False
        if time.time() - self.last_action_at <= self.hand_timeout_seconds:
            return False
        for player in self.players.values():
            player.chips += player.committed
            player.bet = 0
            player.committed = 0
        self.phase = Phase.FINISHED
        self.current_user_id = None
        self.hand_running = False
        self.last_result = "Hand stopped: no action before the timeout. Current bets were refunded."
        self._update_game_over()
        return True

    def _commit(self, user_id: int, amount: int) -> int:
        if amount < 0:
            raise ValueError("Amount must be positive.")
        player = self.players[user_id]
        paid = min(amount, player.chips)
        player.chips -= paid
        player.bet += paid
        player.committed += paid
        if player.chips == 0:
            player.all_in = True
        return paid

    def _after_action(self) -> None:
        if len(self.not_folded()) == 1:
            self.finish_by_fold()
            return
        if self._betting_round_complete():
            self.advance_phase()
            return
        current = self.current_user_id
        assert current is not None
        self.current_user_id = self._first_actionable_from(self.next_to_act_after(current))

    def _betting_round_complete(self) -> bool:
        for player in self.not_folded():
            if player.all_in or player.chips == 0:
                continue
            if player.bet != self.highest_bet:
                return False
            if player.user_id not in self.acted:
                return False
        return True

    def advance_phase(self) -> None:
        for player in self.players.values():
            player.bet = 0
        self.highest_bet = 0
        self.min_raise = self.big_blind
        self.acted = set()

        if len(self.not_folded()) == 1:
            self.finish_by_fold()
            return
        if all(player.all_in or player.chips == 0 for player in self.not_folded()):
            self.deal_remaining_board()
            self.finish_showdown()
            return

        assert self.deck is not None
        if self.phase == Phase.PREFLOP:
            self.board.extend(self.deck.draw(3))
            self.phase = Phase.FLOP
        elif self.phase == Phase.FLOP:
            self.board.extend(self.deck.draw(1))
            self.phase = Phase.TURN
        elif self.phase == Phase.TURN:
            self.board.extend(self.deck.draw(1))
            self.phase = Phase.RIVER
        elif self.phase == Phase.RIVER:
            self.finish_showdown()
            return

        first = self.first_after_dealer()
        self.current_user_id = self._first_actionable_from(first)
        self._auto_advance_if_needed()

    def deal_remaining_board(self) -> None:
        assert self.deck is not None
        while len(self.board) < 5:
            self.board.extend(self.deck.draw(1))

    def finish_by_fold(self) -> None:
        winners = self.not_folded()
        if not winners:
            raise RuntimeError("No winner found.")
        total = sum(player.committed for player in self.players.values())
        winners[0].chips += total
        self.phase = Phase.FINISHED
        self.current_user_id = None
        self.hand_running = False
        self.last_result = f"{winners[0].name} wins {total} chips. Everyone else folded."
        self._rotate_dealer()
        self._update_game_over()

    def finish_showdown(self) -> list[PotAward]:
        self.phase = Phase.SHOWDOWN
        if self.mode == "offline":
            for player in self.not_folded():
                if player.offline_cards:
                    player.hole = player.offline_cards
        if len(self.board) != 5:
            raise ValueError("Showdown needs a 5-card board.")
        for player in self.not_folded():
            if len(player.hole) != 2:
                raise ValueError(f"{player.name} needs exactly 2 hole cards.")

        awards = self._award_side_pots()
        lines = []
        for player in self.not_folded():
            score, combo = best_hand(player.hole + self.board)
            lines.append(
                f"{player.name}: {describe_score(score)} with {cards_text(list(combo))}"
            )
        lines.append("Awards: " + ", ".join(f"{self.players[a.user_id].name} +{a.amount}" for a in awards))
        self.last_result = "\n".join(lines)
        self.phase = Phase.FINISHED
        self.current_user_id = None
        self.hand_running = False
        self._rotate_dealer()
        self._update_game_over()
        return awards

    def _award_side_pots(self) -> list[PotAward]:
        levels = sorted({player.committed for player in self.players.values() if player.committed > 0})
        previous = 0
        awards: list[PotAward] = []
        for level in levels:
            participants = [player for player in self.players.values() if player.committed >= level]
            pot = (level - previous) * len(participants)
            eligible = [player for player in participants if not player.folded]
            if pot <= 0 or not eligible:
                previous = level
                continue
            best_scores = {player.user_id: best_hand(player.hole + self.board)[0] for player in eligible}
            best = max(best_scores.values())
            winners = [player for player in eligible if best_scores[player.user_id] == best]
            share, remainder = divmod(pot, len(winners))
            for index, winner in enumerate(winners):
                amount = share + (1 if index < remainder else 0)
                winner.chips += amount
                awards.append(PotAward(winner.user_id, amount, f"side pot up to {level}"))
            previous = level
        return awards

    def set_offline_board(self, cards: str) -> str:
        parsed = parse_cards(cards, expected=5)
        self.board = parsed
        return f"Board set to {cards_text(self.board)}."

    def set_offline_cards(self, user_id: int, cards: str) -> str:
        if user_id not in self.players:
            raise ValueError("Player is not seated.")
        parsed = parse_cards(cards, expected=2)
        known = list(self.board)
        for player in self.players.values():
            if player.user_id != user_id:
                known.extend(player.offline_cards)
        duplicates = set(parsed).intersection(known)
        if duplicates:
            raise ValueError("Those cards duplicate an existing board/player card.")
        self.players[user_id].offline_cards = parsed
        return f"{self.players[user_id].name}'s cards set."

    def manual_award(self, winner_ids: Iterable[int]) -> str:
        winners = [self.players[user_id] for user_id in winner_ids if user_id in self.players]
        if not winners:
            raise ValueError("At least one valid winner is required.")
        total = sum(player.committed for player in self.players.values())
        share, remainder = divmod(total, len(winners))
        for index, winner in enumerate(winners):
            winner.chips += share + (1 if index < remainder else 0)
        self.phase = Phase.FINISHED
        self.current_user_id = None
        self.hand_running = False
        self.last_result = "Manual award: " + ", ".join(
            f"{winner.name} +{share + (1 if index < remainder else 0)}"
            for index, winner in enumerate(winners)
        )
        self._rotate_dealer()
        self._update_game_over()
        return self.last_result

    def _update_game_over(self) -> None:
        self.game_over = len([player for player in self.players.values() if player.chips > 0]) < 2

    def hand_finished_needs_stats(self) -> bool:
        return self.phase == Phase.FINISHED and not self.stats_recorded

    def snapshot(self) -> dict[str, object]:
        return {
            "channel_id": self.channel_id,
            "mode": self.mode,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "starting_chips": self.starting_chips,
            "phase": self.phase.value,
            "hand_running": self.hand_running,
            "dealer_index": self.dealer_index,
            "current_user_id": self.current_user_id,
            "board": [card.label() for card in self.board],
            "pot": sum(player.committed for player in self.players.values()),
            "highest_bet": self.highest_bet,
            "last_action_at": self.last_action_at,
            "hand_timeout_seconds": self.hand_timeout_seconds,
            "can_start_next_hand": self.can_start_next_hand(),
            "game_over": self.game_over,
            "players": [
                {
                    "seat": index + 1,
                    "user_id": player.user_id,
                    "name": player.name,
                    "chips": player.chips,
                    "folded": player.folded,
                    "all_in": player.all_in,
                    "bet": player.bet,
                    "committed": player.committed,
                    "start_chips": player.start_chips,
                }
                for index, player in enumerate(self.players.values())
            ],
            "last_result": self.last_result,
        }

    def _auto_advance_if_needed(self) -> None:
        while self.hand_running and self.phase in {Phase.PREFLOP, Phase.FLOP, Phase.TURN, Phase.RIVER}:
            if len(self.not_folded()) == 1:
                self.finish_by_fold()
                return
            if self.actionable():
                if self.current_user_id is None:
                    self.current_user_id = self._first_actionable_from(self.first_after_dealer())
                return
            self.deal_remaining_board()
            self.finish_showdown()
            return

    def _first_actionable_from(self, start_user_id: int | None) -> int | None:
        order = self.active_order(include_folded=True)
        if not order:
            return None
        start_index = 0
        if start_user_id is not None:
            for index, player in enumerate(order):
                if player.user_id == start_user_id:
                    start_index = index
                    break
        for offset in range(len(order)):
            player = order[(start_index + offset) % len(order)]
            if not player.folded and not player.all_in and player.chips > 0:
                return player.user_id
        return None

    def next_to_act_after(self, user_id: int) -> int | None:
        order = self.active_order(include_folded=True)
        for index, player in enumerate(order):
            if player.user_id == user_id:
                return order[(index + 1) % len(order)].user_id
        return order[0].user_id if order else None

    def first_after_dealer(self) -> int | None:
        order = self.active_order(include_folded=True)
        if not order:
            return None
        return order[(self.dealer_index + 1) % len(order)].user_id

    def _rotate_dealer(self) -> None:
        order = [player for player in self.players.values() if player.chips > 0]
        if order:
            self.dealer_index = (self.dealer_index + 1) % len(order)

    def table_summary(self, reveal_hole: bool = False) -> str:
        lines = [
            f"Mode: {self.mode} | Phase: {self.phase.value}",
            f"Blinds: {self.small_blind}/{self.big_blind} | Board: {cards_text(self.board)}",
            f"Pot: {sum(player.committed for player in self.players.values())} | Current bet: {self.highest_bet}",
        ]
        if self.current_user_id is not None and self.current_user_id in self.players:
            current = self.players[self.current_user_id]
            lines.append(f"Turn: {current.name} | To call: {self.amount_to_call(current.user_id)}")
        roles = self.seat_roles()
        for index, player in enumerate(self.players.values()):
            status = "folded" if player.folded else "all-in" if player.all_in else "active"
            cards = f" | Cards: {cards_text(player.hole)}" if reveal_hole and player.hole else ""
            tag_text = f" [{' '.join(roles.get(player.user_id, []))}]" if roles.get(player.user_id) else ""
            lines.append(
                f"- Seat {index + 1}{tag_text} {player.name}: {player.chips} chips, bet {player.bet}, committed {player.committed}, {status}{cards}"
            )
        if self.last_result:
            lines.append("")
            lines.append(self.last_result)
        return "\n".join(lines)
