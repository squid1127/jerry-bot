"""Tic Tac Toe game implementation for Jerry Bot."""

from enum import Enum, IntEnum, auto
import discord
import uuid

class Player(Enum):
    P1 = "❌"
    P2 = "⭕"

class GameState(IntEnum):
    CHOOSE_OPPONENT = auto()
    IN_PROGRESS = auto()
    FINISHED = auto()
    CANCELLED = auto()

EMPTY_CELL = "➖"

"""
Board Indexing:
0 | 1 | 2
---------
3 | 4 | 5
---------
6 | 7 | 8
"""

WINNING_COMBINATIONS = [
    [0, 1, 2],
    [3, 4, 5],
    [6, 7, 8],
    [0, 3, 6],
    [1, 4, 7],
    [2, 5, 8],
    [0, 4, 8],
    [2, 4, 6],
]
    

class TicTacToeGame(discord.ui.LayoutView):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=120)
        self.uuid = str(uuid.uuid4())
        self.interaction = interaction
        self.state = GameState.CHOOSE_OPPONENT

        self.board: dict[int, Player | None] = {i: None for i in range(9)}
        self.players: dict[Player, discord.User] = {Player.P1: interaction.user}
        self.current_turn: Player = Player.P1

        self.container = self.generate_container()
        self.add_item(self.container)
        
    def render_board(self, container: discord.ui.Container, interactive: bool) -> None:
        """Render the Tic Tac Toe board."""
        for row in range(3):
            action_row = discord.ui.ActionRow()
            for col in range(3):
                index = row * 3 + col
                cell_value = self.board[index]
                button = discord.ui.Button(
                    label=cell_value.value if cell_value else EMPTY_CELL,
                    style=discord.ButtonStyle.secondary,
                    disabled=False if interactive else True,
                )
                if interactive:
                    button.callback = lambda interaction, idx=index: self.board_move_cb(interaction, idx)
                action_row.add_item(button)
            container.add_item(action_row)

    def generate_container(self) -> discord.ui.Container:
        container = discord.ui.Container(
            accent_color=(
                discord.Color.blue()
                if self.state in (GameState.CHOOSE_OPPONENT, GameState.IN_PROGRESS)
                else discord.Color.green()
            )
        )

        container.add_item(discord.ui.TextDisplay(content="### Tic Tac Toe!"))
        # container.add_item(discord.ui.Separator())

        if self.state == GameState.CHOOSE_OPPONENT:
            container.add_item(discord.ui.TextDisplay(content="Waiting for another player..."))
            button = discord.ui.Button(
                label=f"Join Game {Player.P2.value}", 
                style=discord.ButtonStyle.primary,
                custom_id=f"tictactoe:{self.uuid}:add_player"
            )
            button.callback = self.add_player_cb
            action_row = discord.ui.ActionRow()
            action_row.add_item(button)
            container.add_item(action_row)
            
        elif self.state == GameState.IN_PROGRESS:
            container.add_item(
                discord.ui.TextDisplay(
                    content=f"**Turn:** {self.players[self.current_turn].mention} ({self.current_turn.value})"
                )
            )
            self.render_board(container, interactive=True)
            
        elif self.state == GameState.FINISHED:
            winner = self.check_winner()
            if winner:
                container.add_item(
                    discord.ui.TextDisplay(
                        content=f"**Winner:** {self.players[winner].mention} ({winner.value})"
                    )
                )
            else:
                container.add_item(discord.ui.TextDisplay(content="**It's a draw!**"))
            self.render_board(container, interactive=False)

        elif self.state == GameState.CANCELLED:
            container.add_item(discord.ui.TextDisplay(content="Game cancelled."))
            self.render_board(container, interactive=False)
            
        # Show current players
        players = ", ".join(f"{p.value} {u.display_name}" for p, u in self.players.items())
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(players))
    
        return container
    
    def check_winner(self) -> Player | None:
        """Check if there's a winner."""
        for combo in WINNING_COMBINATIONS:
            values = [self.board[i] for i in combo]
            if values[0] is not None and all(v == values[0] for v in values):
                return values[0]
        return None
    
    def check_draw(self) -> bool:
        """Check if the game is a draw."""
        return all(v is not None for v in self.board.values())

    async def add_player_cb(self, interaction: discord.Interaction):
        """Button callback to add a second player."""
        if (Player.P2 not in self.players) and (interaction.user not in self.players.values()) and self.state == GameState.CHOOSE_OPPONENT:
            self.players[Player.P2] = interaction.user
            
            self.state = GameState.IN_PROGRESS
            await self.render(interaction=interaction)
            return
        await interaction.response.defer(thinking=False) # Only defer ifn not rendering

            
    async def board_move_cb(self, interaction: discord.Interaction, index: int):
        """Button callback for making a move on the board."""
        if self.state != GameState.IN_PROGRESS:
            await interaction.response.defer(thinking=False) # Only defer if not rendering

            return
        if interaction.user != self.players[self.current_turn]:
            await interaction.response.defer(thinking=False)
            
            return  # Not this player's turn
        if self.board[index] is not None:
            await interaction.response.defer(thinking=False) 
            
            return  # Cell already taken

        self.board[index] = self.current_turn

        # Check for win or draw
        if self.check_winner() or self.check_draw():
            self.state = GameState.FINISHED
            await self.render(interaction=interaction)
            return
        else:
            # Switch turns
            self.current_turn = Player.P1 if self.current_turn == Player.P2 else Player.P2

        await self.render(interaction=interaction)
        

    async def render(self, interaction: discord.Interaction) -> None:
        self.clear_items()
        self.container = self.generate_container()
        self.add_item(self.container)
        
        if interaction.response.is_done():
            await interaction.followup.send(view=self)
        else:
            await interaction.response.send_message(view=self)
        try:
            await self.interaction.delete_original_response()
        except discord.NotFound:
            pass
        self.interaction = interaction

    async def on_timeout(self):
        if self.state != GameState.FINISHED:
            self.state = GameState.CANCELLED
            await self.render(interaction=self.interaction)