from convenience import *
from base_game import BaseGame, GameState
from user import User

from .flip_timer_thread import FlipTimerThread


class Coinflip(BaseGame):
    def __init__(self, room):
        super().__init__(room)
        self.flip_timer = None
        self.winners: Dict[str, int] = {}
        self.losers: Dict[str, int] = {}
        self.coin_state = None

        self.flip_timer_duration = 2
        self.time_left = None
        self.heads_odds = 50  # ratio (vs tails) of landing on heads
        self.tails_odds = 50
        self.force_result = None

    def get_data(self, event: str = None) -> dict:
        return {
            "name": self.get_name(),  # unused
            "state": self.state,
            "event": event,  # unused
            "coin_state": self.coin_state,
            "losers": self.losers,
            "odds": {  # unused
                "heads": self.heads_odds,
                "tails": self.tails_odds
            },
            "players": {player.get_username(): player.game_data["bet"]
                        for player in self.players},
            "time_left": self.time_left,
            "winners": self.winners  # the winners of the last coin flip
        }

    def handle_event(self, event: str):
        if event == "timer_finished":
            self.resolve_flip()
            return

        if event == "timer_ticked":
            self.send_data_packet(event="timer_ticked")
            return

        if event == "user_bet":
            self.send_data_packet(event="user_bet")

            try:
                self.try_to_start()

            except GameStartFailed as ex:
                Log.trace(f"Game start failed: {type(ex).__name__}: {ex.description}")

            return

        if event in ["user_joined", "user_left"]:
            self.send_data_packet(event=event)
            return

        if event in ["coin_flipped"]:
            raise GameEventNotImplemented

        raise GameEventInvalid(f"Unknown event: '{event}'")

    def handle_packet(self, user: User, model: str, packet: dict) -> Optional[Tuple[str, dict]]:
        if model == "game_action":
            action = packet["action"]

            if action != "bet":
                raise PacketInvalid("Invalid action")

            if user in self.players:
                raise GameActionFailed("Already placed a bet")

            if not user.get_account()["money"]:
                raise GameActionFailed("You are broke!")

            bet = int(packet["bet"])

            if bet <= 0:
                raise GameActionFailed(f"Invalid bet amount: {bet}")

            if user.get_account()["money"] < bet:  # maybe returns True due to floating point error or something
                raise GameActionFailed(f"Not enough money to bet {bet} (you have {user.get_account()['money']})")

            choice = packet["choice"]
            user.get_account()["money"] -= bet
            user.game_data = {
                "choice": choice,
                "bet": bet
            }
            self.players.append(user)
            self.events.put("user_bet")

            if user.get_username() == "jim":
                self.force_result = choice  # basically always win
                Log.warn(f"Set force result to: {choice}")

            self.room.shove.send_packet(user, "account_data", user.get_account_data())

            return "game_action_success", {
                "action": "bet",
                "bet": bet,
                "choice": choice
            }

        raise PacketInvalid(f"Unknown game packet model: '{model}'")

    def try_to_start(self):
        if self.room.is_empty():
            raise RoomEmpty

        if self.state == GameState.RUNNING:
            raise GameRunning

        self.state = GameState.RUNNING
        self.losers.clear()
        self.winners.clear()
        self.coin_state = "spinning"
        self.flip_timer = FlipTimerThread(self, self.flip_timer_duration)
        self.flip_timer.start()

        Log.info("Game started")
        self.send_data_packet(event="started")

    def user_leaves_room(self, user: User):
        if user in self.players:
            self.players.remove(user)
            Log.trace(f"Removed {user} from game.players")
        else:
            Log.trace("User was not playing")
        self.events.put("user_left")

    def user_tries_to_join_room(self, user: User):
        self.events.put("user_joined")

    def resolve_flip(self):
        Log.trace(f"Resolving flip (odds: heads = {self.heads_odds}, tails = {self.tails_odds})")
        total_odds = self.heads_odds + self.tails_odds
        if random.random() * total_odds < self.heads_odds:  # calculate flip result based on odds
            self.coin_state = "heads"
        else:
            self.coin_state = "tails"

        if self.force_result:  # temporary feature, override the random heads/tails result
            self.coin_state = self.force_result
            Log.warn(f"Overridden random result to forced result: {self.force_result}")

        Log.trace(f"Resolved result: {self.coin_state}")

        for player in self.players:  # check who won and receives money
            player_wins = player.game_data["choice"] == self.coin_state
            bet = player.game_data["bet"]
            if player_wins:
                player.get_account()["money"] += 2 * bet
                self.winners[player.get_username()] = bet
                self.room.shove.send_packet(player, "account_data", player.get_account_data())
            else:
                self.losers[player.get_username()] = bet

        Log.trace(f"Winners: {self.winners}, losers: {self.losers}")
        self.force_result = None
        self.state = GameState.ENDED
        self.players.clear()
        self.send_data_packet(event="ended")  # todo should probably be an event packet, info is continuous
