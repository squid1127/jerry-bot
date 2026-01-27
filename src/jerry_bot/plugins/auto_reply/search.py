"""A simple search system for discord UI views."""

from tortoise import Model
import discord
from typing import Callable
from dataclasses import dataclass

DROPDOWN_MAX_OPTIONS = 25

@dataclass(frozen=True, order=True)
class SelectOptionData:
    """Data class for select option data."""

    option: discord.SelectOption
    model: Model
    value: str

class Search:
    """A simple search system for discord UI views."""

    def __init__(self, model: Model, search_fields: list[str], render: Callable[[Model], discord.SelectOption], callback: Callable[[discord.Interaction, Model], None], title: str = "Search"):
        """Initialize the Search system.

        Args:
            model (Model): The Tortoise ORM model to search.
            search_fields (list[str]): The fields to search within the model.
            title (str, optional): The title of the search modal. Defaults to "Search".
            render (Callable[[Model], discord.SelectOption]): A callable to render a model instance. 
            callback (Callable[[discord.Interaction, Model], None]): A callback to handle selection of a model instance.
        """
        self.model = model
        self.search_fields = search_fields
        self.title = title
        self.render = render
        self.callback = callback
        
        self.query: str | None = None
        
    async def fetch_results(self, max_results: int = DROPDOWN_MAX_OPTIONS, query: str | None = None) -> list[Model]:
        """Fetch search results based on the query.

        Args:
            max_results (int, optional): Maximum number of results to return. Defaults to DROPDOWN_MAX_OPTIONS.
            query (str | None, optional): The search query. If None, uses the stored search_text. Defaults to None.

        Returns:
            list[Model]: A list of model instances matching the search query.
        """
        if query is not None:
            self.query = query
            
        if not self.query:
            return await self.model.all().limit(max_results)
        
        filters = {}
        for field in self.search_fields:
            filters[f"{field}__icontains"] = self.query
            
        results = await self.model.filter(**filters).limit(max_results)
        return results
    
    def render_options(self, models: list[Model]) -> dict[str, SelectOptionData]:
        """Render a list of model instances into discord SelectOptions.

        Args:
            models (list[Model]): The list of model instances.

        Returns:
            dict[str, discord.SelectOption]: A dictionary mapping model IDs to SelectOptions.
        """
        options = {}
        for model in models:
            option = self.render(model)
            options[option.value] = SelectOptionData(
                option=option,
                model=model,
                value=option.value,
            )
        return options
    
    async def show_modal(self, interaction: discord.Interaction):
        """Show the search modal for the interaction.

        Args:
            interaction (discord.Interaction): The interaction object.
        """
        modal = SearchModal(self)
        await modal.render()
        await interaction.response.send_modal(modal)
        
class SearchModal(discord.ui.Modal):
    """A modal for searching within a model."""

    def __init__(self, search: Search):
        """Initialize the SearchModal.
        
        Warning: Must call render() after initialization to set up components.

        Args:
            search (Search): The Search instance.
        """
        super().__init__(title=search.title, timeout=600)
        self.search = search
        self.options: dict[str, SelectOptionData] = {}
        
    async def render(self):
        """
        Asyncronously render the modal components.

        Args:
            interaction (discord.Interaction): The interaction object.
        """
        self.clear_items()
        
        self.search_input = discord.ui.TextInput(
            style=discord.TextStyle.short,
            placeholder="Enter your search query here...",
            required=False,
            max_length=100,
        )
        self.add_item(discord.ui.Label(text="Search Query", component=self.search_input))
        
        results = await self.search.fetch_results(query=self.search_input.value)
        self.options = self.search.render_options(results)
        if results:
            self.dropdown = discord.ui.Select(
                placeholder="Select a result...",
                min_values=0,
                max_values=1,
                options=[opt.option for opt in self.options.values()],
                required=False,
            )
            self.add_item(discord.ui.Label(text="Results", component=self.dropdown))
        # elif self.search.query:
        #     self.dropdown = discord.ui.Select(
        #         placeholder="No results found.",
        #         min_values=0,
        #         max_values=0,
        #         options=[discord.SelectOption(label="No results found.", description="Try a different query.")],
        #         disabled=True,
        #         required=False,
        #     )
        #     self.add_item(discord.ui.Label(text="Results", component=self.dropdown))
        else:
            self.dropdown = None

    async def on_submit(self, interaction: discord.Interaction):
        """Handle the submission of the search query.

        Args:
            interaction (discord.Interaction): The interaction object.
        """
        query = self.search_input.value
        if query:
            self.search.query = query
        
        # Check if dropdown option picked
        if self.dropdown and self.dropdown.values:
            selected_value = self.dropdown.values[0]
            selected_model = self.options[selected_value].model
            await self.search.callback(interaction, selected_model)
            self.stop()

        # Else, open a new modal with results
        else:
            self.stop()
            await self.search.show_modal(interaction)
            
    async def on_timeout(self):
        # Modal timed out
        self.stop()