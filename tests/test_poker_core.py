import unittest

from poker_bot.cards import parse_cards
from poker_bot.evaluator import best_hand
from poker_bot.game import Action, Phase, PokerTable


class PokerCoreTests(unittest.TestCase):
    def test_flush_beats_straight(self):
        flush = best_hand(parse_cards("Ah Jh 8h 5h 2h Kc Qd"))[0]
        straight = best_hand(parse_cards("9c 8d 7h 6s 5c Ah Kd"))[0]
        self.assertGreater(flush, straight)

    def test_wheel_straight(self):
        score = best_hand(parse_cards("Ah 2d 3s 4c 5h Kd Qc"))[0]
        self.assertEqual(score, (4, (5,)))

    def test_heads_up_hand_can_finish_by_fold(self):
        table = PokerTable(1, "online", 10, 20, 1000)
        table.add_player(1, "Alice")
        table.add_player(2, "Bob")
        table.start_hand()
        table.apply_action(table.current_user_id, Action.FOLD)
        self.assertEqual(table.phase, Phase.FINISHED)
        self.assertEqual(sum(player.chips for player in table.players.values()), 2000)

    def test_seats_can_be_reordered_between_hands(self):
        table = PokerTable(1, "online", 10, 20, 1000)
        table.add_player(1, "Alice")
        table.add_player(2, "Bob")
        table.add_player(3, "Carol")
        table.move_player_to_seat(3, 1)
        self.assertEqual([player.name for player in table.seat_order()], ["Carol", "Alice", "Bob"])
        table.swap_seats(1, 2)
        self.assertEqual([player.name for player in table.seat_order()], ["Carol", "Bob", "Alice"])

    def test_seats_cannot_be_reordered_during_hand(self):
        table = PokerTable(1, "online", 10, 20, 1000)
        table.add_player(1, "Alice")
        table.add_player(2, "Bob")
        table.start_hand()
        with self.assertRaises(ValueError):
            table.move_player_to_seat(2, 1)

    def test_showdown_side_pot_total_is_conserved(self):
        table = PokerTable(1, "offline", 10, 20, 100)
        table.add_player(1, "Alice")
        table.add_player(2, "Bob")
        table.add_player(3, "Carol")
        table.start_hand()
        for player in table.players.values():
            player.hole = []
        table.players[1].hole = parse_cards("Ah Ad")
        table.players[2].hole = parse_cards("Kh Kd")
        table.players[3].hole = parse_cards("Qh Qd")
        table.board = parse_cards("2c 3d 7s 8h 9c")
        table.players[1].committed = 50
        table.players[2].committed = 100
        table.players[3].committed = 100
        for player in table.players.values():
            player.chips = 0
        table.finish_showdown()
        self.assertEqual(sum(player.chips for player in table.players.values()), 250)
        self.assertGreater(table.players[1].chips, 0)


if __name__ == "__main__":
    unittest.main()
