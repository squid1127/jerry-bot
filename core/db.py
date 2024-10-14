""""""

# External imports
from discord.ext import commands

# Postgres database
import asyncpg

# Bot Shell
from .shell import ShellCore

# Async
import asyncio

# Typing
from typing import Literal

class DatabaseCore:
    def __init__(
        self,
        bot: commands.Bot,
        postgres_connection: str,
        postgres_password: str = None,
        postgres_pool: int = 20,
    ):
        self.bot = bot
        self.postgres_connection = postgres_connection
        self.postgres_password = postgres_password
        self.postgres_max_pool = postgres_pool
        self.pool = None
        self.working = False

    async def start(self) -> bool:
        """
        Continuously attempts to establish a connection to the database and create a connection pool.
        This method will keep trying to connect to the database until successful. Once connected, it will
        check the status of the database and set the `working` attribute accordingly. If the connection
        fails, it will retry after a 10-second delay.
        Returns:
            bool: True if the database connection is successful and the connection pool is created, False otherwise.
        """
        # Continuously attempt to connect to the database
        while True:
            # Attempt to create the connection pool
            try:
                await self.create_pool()
            except Exception as e:
                print(f"[Core.Database] Failed to connect to database: {e}")
            else:
                print("[Core.Database] Database connection pool created")
                
                # If the connection pool is created, check the status of the database
                try:
                    status = await self.check_status()
                    if status == 2:
                        print("[Core.Database] Database connection successful")
                        self.working = True
                        return True
                    elif status == 1:
                        print("[Core.Database] Database connected but no tables found")
                        self.working = True
                        return True
                    else:
                        print("[Core.Database] Database connection failed")
                except Exception as e:
                    print(f"[Core.Database] Failed to check database status: {e}")

            # If the connection fails, retry after a 10-second delay
            print("[Core.Database] Failed to connect to database, retrying in 10 seconds")
            await asyncio.sleep(10)

    # * Database Queries & Functions
    # Create connection pool
    async def create_pool(self):
        """
        Creates a connection pool for the database.
        """
        self.pool = await asyncpg.create_pool(
            dsn=self.postgres_connection,
            password=self.postgres_password,
            max_size=self.postgres_max_pool,
        )
    # Basic query function
    async def query(self, query: str, *args):
        """
        Fetches a SQL query from the database and returns the result.
        Note: This fuction should be used to retrieve data from the database, not to modify it.
        Args:
            query (str): The SQL query to be executed.
            *args: Additional arguments to be passed to the query.
        Returns:
            The result of the query execution.
        """

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                return await connection.fetch(query, *args)

    async def execute(self, query: str, *args):
        """
        Executes a given SQL query with the provided arguments.
        Note: This function should be used to modify the database. It (should) not return any data.
        Args:
            query (str): The SQL query to be executed.
            *args: Variable length argument list to be used in the SQL query.
        Returns:
            The result of the executed query.
        """
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                return await connection.execute(query, *args)
            
    async def check_status(self) -> int:
        """
        Checks the status of the database connection.
        Returns:
            The status of the database connection as an integer:
                0: Not connected
                1: Connected but no tables found
                2: Connected and ready
        """
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    tables = await connection.fetch(
                        """
                            SELECT table_schema, table_name
                            FROM information_schema.tables
                            WHERE table_type = 'BASE TABLE'
                            ORDER BY table_schema, table_name;
                        """
                    )
            if tables:
                return 2
            return 1
        except Exception as e:
            return 0
        

    # Tables
    async def table_read_all(self, table: str):
        """
        Reads all the data from a table.
        Args:
            table (str): The table to read from.
        Returns:
            The data from the table. (list of dict)
        """
        data = await self.query(f"SELECT * FROM {table}")


class DatabaseHandler(commands.Cog):
    def __init__(self, bot: commands.Bot, core: DatabaseCore, shell: ShellCore):
        self.core = core
        self.bot = bot
        self.shell = shell
        print("[Core.Database] Database enabled")

    # Start database connection
    @commands.Cog.listener()
    async def on_ready(self):
        print("[Core.Database] Connecting to database")

        success = await self.core.start()
        if success != True:
            if success == False:
                await self.shell.log(
                    f"Failed to connect to database: {self.core.postgres_connection}",
                    title="Database Connection Error",
                    msg_type="error",
                    cog="DatabaseHandler",
                )
            else:
                await self.shell.log(
                    f"Failed to connect to database: {success}",
                    title="Database Connection Error",
                    msg_type="error",
                    cog="DatabaseHandler",
                )
    
    # Cog Status
    async def cog_status(self) -> str:
        print("[Core.Database] Checking database status")
        
        # Connection status (Check schema)
        tables = None
        try:
            async with self.core.pool.acquire() as connection:
                async with connection.transaction():
                    tables = await connection.fetch(
                        # List schema
                        """
                            SELECT table_schema, table_name
                            FROM information_schema.tables
                            WHERE table_type = 'BASE TABLE'
                            ORDER BY table_schema, table_name;
                        """
                    )
            if tables:
                print("[Core.Database] Database status: Connected")
                
                return "Connected and ready"
            
            print("[Core.Database] Database status: Connected but no tables found")
            return "Connected but no tables found"
        except Exception as e:
            print(f"[Core.Database] Database status: Error - {e}")
            return f"Error Connecting: {e}"
        