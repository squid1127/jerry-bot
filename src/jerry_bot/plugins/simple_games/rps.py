"""Simplified 2P Rock Paper Scissors game"""

from enum import Enum, IntEnum, auto
import discord

class Choice(Enum):
    ROCK = "🪨"
    PAPER = "📄"
    SCISSORS = "✂️"
    
DEFEATS = {
    Choice.ROCK: Choice.SCISSORS,
    Choice.PAPER: Choice.ROCK,
    Choice.SCISSORS: Choice.PAPER,
}
    
class GameState(IntEnum):
    PICK = auto()
    RESULT = auto()
    CANCELLED = auto()
    
class ChoiceButton(discord.ui.Button):
    def __init__(self, choice: Choice, game: "RPSGame"):
        super().__init__(emoji=choice.value, style=discord.ButtonStyle.secondary)
        self.choice = choice
        self.game = game

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=False)
        await self.game.player_vote(interaction.user, self.choice)

class RPSGame(discord.ui.LayoutView):
    def __init__(self, interaction: discord.Interaction, players: int = 2):
        super().__init__(timeout=120)
        
        self.interaction = interaction
        self.state = GameState.PICK
        self.choices: dict[discord.User, Choice] = {}
        self.players_count = players
        self.container = self.generate_container()
        self.add_item(self.container)
        
    def generate_container(self) -> discord.ui.Container:
        container = discord.ui.Container(accent_color=discord.Color.blue() if self.state == GameState.PICK else discord.Color.green())

        container.add_item(discord.ui.TextDisplay(content="### Rock, Paper, Scissors!"))
        # container.add_item(discord.ui.Separator())
        
        if self.state == GameState.PICK:
            container.add_item(discord.ui.TextDisplay(content="Make your choice:"))
            choices = discord.ui.ActionRow(*(ChoiceButton(choice, self) for choice in Choice))
            container.add_item(choices)
            
            container.add_item(discord.ui.Separator())
            if self.choices:
                players = ", ".join(user.display_name for user in self.choices.keys())
                container.add_item(discord.ui.TextDisplay(content=f"({len(self.choices)}/{self.players_count}) {players}"))
            else:
                container.add_item(discord.ui.TextDisplay(content=f"(0/{self.players_count}) No choices made yet.\n-# *Expires in 2 minutes*"))
            
        elif self.state == GameState.RESULT:
            winners = self.determine_winner()
            players = list(self.choices.keys())
            result_text = ""
            
            # Check for tie conditions
            if not winners or len(winners) == len(players):
                result_text += "**🤝 It's a tie!**\n"
                for player in players:
                    result_text += f"{player.display_name} - {self.choices[player].value}\n"
            else:
                # Show winners and losers
                for winner in winners:
                    result_text += f"🏆 **{winner.display_name}** - {self.choices[winner].value}\n"
                    players.remove(winner)
            
                for player in players:
                    result_text += f"❌ {player.display_name} - {self.choices[player].value}\n"
            container.add_item(discord.ui.TextDisplay(content=result_text))
            
        elif self.state == GameState.CANCELLED:
            container.add_item(discord.ui.TextDisplay(content="Game cancelled."))
            
        return container
    
    def determine_winner(self) -> list[discord.User]:
        """Determine the winner(s) of the game based on player choices.
        
        Multi-player RPS rules:
        - If only 1 choice type: tie (no winners)
        - If 2 choice types: players with winning choice win
        - If all 3 choice types: tie (everyone beats someone, everyone loses to someone)
        """
        if len(self.choices) < self.players_count:
            return []
        
        # Count how many players chose each option
        choice_counts = {choice: 0 for choice in Choice}
        for choice in self.choices.values():
            choice_counts[choice] += 1
        
        # Count how many distinct choices were made
        choices_present = sum(1 for count in choice_counts.values() if count > 0)
        
        # Tie cases: all same choice or all 3 choices
        if choices_present == 1 or choices_present == 3:
            return []  # Return empty to indicate tie
            
        # Normal case: 2 different choices, determine winners
        winners = []
        for user, choice in self.choices.items():
            defeated_choice = DEFEATS[choice]
            # Player wins if someone chose what they defeat
            if choice_counts[defeated_choice] > 0:
                winners.append(user)
                
        return winners
    
    async def player_vote(self, user: discord.User, choice: Choice):
        if self.state != GameState.PICK:
            return
        
        if len(self.choices) >= self.players_count:
            return
        
        self.choices[user] = choice
        
        if len(self.choices) >= self.players_count:
            self.state = GameState.RESULT
            
        await self.render()

    
    async def render(self):
        self.clear_items()
        self.container = self.generate_container()
        self.add_item(self.container)
        
        await self.interaction.edit_original_response(view=self)
        
    async def on_timeout(self):
        if self.state == GameState.PICK:
            self.state = GameState.CANCELLED
            await self.render()