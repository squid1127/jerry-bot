"""Database models"""
from tortoise import fields
from tortoise.models import Model

class SupportThreadConfig(Model):
    """
    Configuration model for support threads in a Discord guild.
    
    Attributes:
        id (int): Primary key.
        guild_id (int): The ID of the Discord guild that owns this configuration.
        threads_channel_id (int): The ID of the channel where support threads will be created.
        support_role_id (int, optional): The ID of the role assigned to support staff.
        view_message_id (int, optional): The ID of the message created for a Discord UI view to open support threads.
        description (str, optional): A description for the support threads.
    """
    id = fields.IntField(pk=True)
    guild_id = fields.BigIntField()
    threads_channel_id = fields.BigIntField()
    support_role_id = fields.BigIntField(null=True)
    view_message_id = fields.BigIntField(null=True)
    description = fields.TextField(null=True)
    
    class Meta:
        table = "support_thread_configs"