from crownline import new_game

def print_scores(game):
    for player, name in (("W", "White"), ("B", "Black")):
        s = game.score(player)
        print(
            f"{name}: capture={s.capture_bank} "
            f"board={s.board_value} melds={s.meld_count} "
            f"bonus={s.meld_bonus} total={s.total}"
        )

def main():
    game = new_game()

    print("CROWNLINE v0.1")
    print("Enter moves such as d2-e3 or a3xc5xe7.")
    print("Commands: moves, score, quit\n")

    while True:
        print(game.render())
        print()

        if game.game_over:
            print_scores(game)
            print(f"\nWinner: {game.winner()}")
            break

        legal = game.legal_moves()
        print("Legal:", ", ".join(m.notation() for m in legal))

        command = input(f"\n{game.turn}> ").strip().lower()

        if command in {"quit", "q", "exit"}:
            break
        if command == "moves":
            continue
        if command == "score":
            print()
            print_scores(game)
            print()
            continue

        try:
            game = game.apply_notation(command)
        except ValueError as exc:
            print(f"\n{exc}\n")


if __name__ == "__main__":
    main()
