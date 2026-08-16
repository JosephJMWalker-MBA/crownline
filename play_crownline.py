from crownline import MeldChoiceRequired, new_set


def print_game_scores(crownline_set):
    game = crownline_set.current_game
    for color, name in (("W", "White"), ("B", "Black")):
        score = game.score(color)
        participant = crownline_set.participant_for_color(color)
        print(
            f"Player {participant} ({name}): capture={score.capture_bank} "
            f"board={score.board_value} melds={score.meld_count} "
            f"bonus={score.meld_bonus} total={score.total}"
        )


def print_set_scores(crownline_set):
    a, b = crownline_set.aggregate_scores()
    print(f"Aggregate set score: A={a} B={b}")


def choose_meld(game, move):
    options = game.meld_options_after(move)
    if len(options) <= 1:
        return None

    print("\nThis move completes multiple eligible Crownlines. Choose the meld to bank:")
    for index, meld in enumerate(options, start=1):
        print(f"  {index}. {'-'.join(meld.line)} using pieces {meld.piece_ids}")

    while True:
        choice = input("Meld> ").strip()
        try:
            index = int(choice) - 1
            if 0 <= index < len(options):
                return options[index].line
        except ValueError:
            pass
        print("Choose one of the listed meld numbers.")


def main():
    crownline_set = new_set(first_game_white="A")

    print("CROWNLINE — Official Rules v1.0")
    print("Player A is White/first in Game 1; colors swap automatically for Game 2.")
    print("Moves: d2-e3 or a3xc5xe7")
    print("Commands: score, set, moves, quit\n")

    while True:
        game = crownline_set.current_game
        print(game.render())
        print(
            f"Player {crownline_set.white_participant}=White | "
            f"Player {crownline_set.black_participant}=Black"
        )
        print_set_scores(crownline_set)
        print()

        if game.game_over:
            print_game_scores(crownline_set)
            print(f"Individual game winner: {game.winner()}\n")

            crownline_set = crownline_set.advance_game()
            if crownline_set.set_over:
                a, b = crownline_set.aggregate_scores()
                print(f"FINAL SET SCORE: A={a} B={b}")
                print(f"Crownline Set result: {crownline_set.winner()}")
                if crownline_set.winner() == "DRAW":
                    print("Official result: draw. A further complete set requires mutual agreement.")
                break

            print("Game 2 begins on the light squares with complementary Crown values.\n")
            continue

        legal = game.legal_moves()
        print("Legal:", ", ".join(move.notation() for move in legal))
        participant = crownline_set.participant_for_color(game.turn)
        command = input(f"\nPlayer {participant} ({game.turn})> ").strip().lower()

        if command in {"quit", "q", "exit"}:
            break
        if command == "moves":
            continue
        if command == "score":
            print()
            print_game_scores(crownline_set)
            print()
            continue
        if command == "set":
            print()
            print_set_scores(crownline_set)
            print()
            continue

        try:
            move = game.move_from_notation(command)
            meld_line = choose_meld(game, move)
            crownline_set = crownline_set.apply_move(move, meld_line=meld_line)
        except (ValueError, MeldChoiceRequired) as exc:
            print(f"\n{exc}\n")


if __name__ == "__main__":
    main()
