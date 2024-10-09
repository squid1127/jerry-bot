import discord
import aiomysql
import tabulate

class Database:
    def __init__(self, creds: list):
        self.creds = creds
        self.working = False
        self.data = self.DbData()
        self.last_used_cred = None

    # Check if credentials are set (not empty)
    def creds_check(self) -> bool:
        """Check if database credentials are set"""
        if len(self.creds) > 0:
            return True
        return False

    # Periodic Task: Test all database connections
    async def test_all_connections(self):
        """Test all database connections and return the working ones"""
        print("[Database] Testing all connections...")
        self.functioning_creds = []
        for cred in self.creds:
            try:
                async with aiomysql.connect(
                    host=cred["host"],
                    port=cred.get("port", 3306),
                    user=cred["user"],
                    password=cred["password"],
                    db=cred["db"],
                ) as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT 1")
                        print(
                            f"[Database] Connection to {cred['name']} successful!"
                        )
                        self.functioning_creds.append(cred)
                    conn.close()
            except Exception as e:
                if e.args[0] == 2003:
                    print(
                        f"[Database] Connection to {cred['name']} failed: Host not found"
                    )
                else:
                    print(f"[Database] Connection to {cred['name']} failed: {e}")
        if len(self.functioning_creds) == 0:
            print("[Database] No working connections found!")
            raise Exception("No working database connections found")
        print(f"[Database] {len(self.functioning_creds)} connections working!")
        return self.functioning_creds

    # Connect to the database with specified credentials
    async def connect(self, cred: dict):
        """Connect to the database with specified credentials"""
        try:
            conn = await aiomysql.connect(
                host=cred["host"],
                port=cred.get("port", 3306),
                user=cred["user"],
                password=cred["password"],
                db=cred["db"],
            )
            self.last_used_cred = cred
            return conn
        except Exception as e:
            print(f"[Database] Connection to {cred['name']} failed: {e}")
            return None

    # Auto-connect (Connect to the first working database)
    async def auto_connect(self) -> aiomysql.Connection:
        """Automatically connect to the first working database connection"""
        if not hasattr(self, "functioning_creds"):
            await self.test_all_connections()
        if len(self.functioning_creds) > 0:
            for cred in self.functioning_creds:
                conn = await self.connect(cred)
                if conn:
                    return conn
        return None

    # Check database format
    async def check_database(self):
        """Check if the database is formatted correctly, if not, format it"""
        print("[Database] Checking database format...")
        print("[Database] Connecting to database...")
        try:
            conn = await self.auto_connect()
            if conn is None:
                raise Exception("No working database connections")
        except Exception as e:
            print(f"[Database] Error connecting to database: {e}")
            return

        # Fetch all tables
        async with conn.cursor() as cur:
            await cur.execute("SHOW TABLES")
            tables = await cur.fetchall()
            await cur.close()
        tables = [table[0] for table in tables]
        print(f"[Database] Tables: {tables}")

        # Check if tables exist, create if not
        tables_created = 0
        tables_failed = 0

        # Check admins table
        if "admin_users" not in tables:
            print("[Database] Admins table not found, creating...")
            query = """
            DROP TABLE IF EXISTS admin_users;
            CREATE TABLE
            admin_users (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                discord_id BIGINT NOT NULL,
                username VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL
            );
            """
            try:
                await self.execute_query(query, conn)
                print("[Database] Admins table created!")
                tables_created += 1
            except Exception as e:
                print(f"[Database] Error creating admins table: {e}")
                tables_failed += 1

        # Check guilds table
        if ("guilds" not in tables) or ("channels" not in tables):
            print("[Database] Guilds and/or channels table not found, creating...")
            query = """
            DROP TABLE IF EXISTS channels;

            DROP TABLE IF EXISTS guilds;

            CREATE TABLE
            guilds (
                guild_id BIGINT NOT NULL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                enable_owen_mode BOOLEAN DEFAULT FALSE,
                enable_brainrot BOOLEAN DEFAULT FALSE,
                admin_mode BOOLEAN DEFAULT FALSE
            );

            CREATE TABLE
            channels (
                channel_id BIGINT NOT NULL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                guild_id BIGINT NOT NULL REFERENCES guilds(guild_id),
                channel_mode VARCHAR(255) DEFAULT 'Normal',
                disable_brainrot BOOLEAN DEFAULT FALSE
            );
            """
            try:
                await self.execute_query(query, conn)
                print("[Database] Guilds & Members tables created!")
                tables_created += 1
            except Exception as e:
                print(f"[Database] Error creating tables: {e}")
                tables_failed += 1

        # Config table
        if "config" not in tables:
            print("[Database] Config table not found, creating...")
            query = """
            DROP TABLE IF EXISTS config;
            CREATE TABLE
            config (
                id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                value VARCHAR(255) NOT NULL,
                hidden BOOLEAN DEFAULT FALSE
            );
            """
            try:
                await self.execute_query(query, conn)
                print("[Database] Config table created!")
                tables_created += 1
            except Exception as e:
                print(f"[Database] Error creating config table: {e}")
                tables_failed += 1

        # Close connection
        print("[Database] Closing connection...")
        if conn is not None:
            conn.close()

        # Print summary
        print("[Database] Done checking database format!")
        if tables_created > 0:
            print(f"[Database] Created {tables_created} tables")
        if tables_failed > 0:
            print(f"[Database] ERROR: Failed to create {tables_failed} tables")
            return

        print("[Database] Database is good to go!")
        self.working = True

    # Read data from a table
    async def read_table(self, table: str, conn: aiomysql.Connection):
        """Read data from a specified table"""
        async with conn.cursor() as cur:
            await cur.execute(f"SELECT * FROM {table}")
            result = await cur.fetchall()
            description = cur.description
            await cur.close()

        if result:
            return await self.convert_to_dict(result, description)
        return result

    async def add_entry(self, table: str, data: dict, conn: aiomysql.Connection):
        """Add an entry to a table, such as "sigma" to the brainrot table"""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        values = tuple(data.values())
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        print(query)

        async with conn.cursor() as cur:
            await cur.execute(query, values)
            await conn.commit()
            await cur.close()

        #!await self.execute_query(query, conn) #! This doesn't work for some reason

        print(f"[Database] Added entry to {table}: {data}")

    async def update_entry(
        self, table: str, target: dict, data: dict, conn: aiomysql.Connection
    ):
        """Update an entry in a table, such as changing "sigma" to "owen" in the brainrot table"""

        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        values = tuple(data.values())
        target_columns = ", ".join(target.keys())
        target_placeholders = ", ".join(["%s"] * len(target))
        target_values = tuple(target.values())
        query = f"UPDATE {table} SET {columns} = {placeholders} WHERE {target_columns} = {target_placeholders}"
        await self.execute_query(query, conn, values + target_values)
        await conn.commit()
        print(f"[Database] Updated entry in {table}: {target} -> {data}")

    async def delete_entry(self, table: str, data: dict, conn: aiomysql.Connection):
        """Delete an entry from a table, such as removing "sigma" from the brainrot table"""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        values = tuple(data.values())
        query = f"DELETE FROM {table} WHERE {columns} = {placeholders}"
        await self.execute_query(query, conn, values)
        await conn.commit()
        print(f"[Database] Deleted entry from {table}: {data}")

    # Execute generic SQL query
    async def execute_query(
        self,
        query: str,
        conn: aiomysql.Connection,
        values: tuple = None,
        pretty_table: bool = False,
    ):
        """Execute a generic SQL query, such as `SELECT * FROM table`"""
        print(f"[Database] Executing query: {query} ({values})")

        async with conn.cursor() as cur:
            await cur.execute(query, values)
            result = await cur.fetchall()
            description = cur.description

            await cur.close()

        if result:
            if pretty_table:
                try:
                    table = tabulate.tabulate(
                        result,
                        headers=[column[0] for column in description],
                        tablefmt="simple_grid",
                    )
                    print(f"[Database] Query result is a table:\n{table}")
                    return table
                except:
                    pass
            try:
                print(f"[Database] Query result is a list of dictionaries")
                return await self.convert_to_dict(result, description)
            except:
                pass
        print(f"[Database] Query result is unknown")
        return result, description

    async def convert_to_dict(self, result: list, description: list):
        """Convert a SQL result to a list of dictionaries, with column names as keys"""
        return [
            dict(zip([column[0] for column in description], row)) for row in result
        ]

    # Read and update all tables
    async def update_all_conn(self, conn: aiomysql.Connection):
        """Read and update all tables from a connection"""
        print("[Database] Reading all tables...")
        guilds = await self.read_table("guilds", conn)
        channels = await self.read_table("channels", conn)
        brainrot = await self.read_table("brainrot", conn)
        whitelist = await self.read_table("whitelist", conn)
        admins = await self.read_table("admin_users", conn)
        config = await self.read_table("config", conn)

        # Write to data object
        self.data.update(
            guilds=guilds,
            channels=channels,
            brainrot=brainrot,
            whitelist=whitelist,
            admins=admins,
            config=config,
        )

        print(f"[Database] Done reading all tables!\n{self.data}")

    # Autmatically connect and read all tables
    async def update_all_auto(self):
        """Automatically connect and read and update all tables; run this after a database change"""
        conn = await self.auto_connect()
        if conn is None:
            print("[Database] No working database connections")
            return
        await self.update_all_conn(conn)
        conn.close()

    # Config management
    async def config_get(self, name: str):
        """Get a config entry value"""
        for entry in self.data.config:
            if entry["name"] == name:
                return entry["value"]
        return None

    async def config_set(
        self, name: str, value: str, conn: aiomysql.Connection = None
    ):
        """Set a config entry value"""
        if conn is None:
            conn = await self.auto_connect()
        for entry in self.data.config:
            if entry["name"] == name:
                await self.update_entry(
                    "config", {"name": name}, {"value": value}, conn
                )
                if conn is None:
                    conn.close()
                return True
        await self.add_entry("config", {"name": name, "value": value}, conn)
        if conn is None:
            conn.close()
        return True

    class DbData:
        """Database data object, stores all data from the database"""

        def __init__(self):
            # Database tables
            self.guilds = []
            self.channels = []
            self.brainrot = []
            self.whitelist = []
            self.admins = []
            self.config = []
            self.write_count = 0

        def __str__(self):
            return f"""Database Data:
Guilds: {self.guilds}
Channels: {self.channels}
Banned Words: {self.brainrot}
Whitelist: {self.whitelist}
Admins: {self.admins}"""

        def embed_fields(self, embed: discord.Embed = None):
            """Generate embed fields for all database data"""
            print("[Database Data] Generating embed fields...")
            try:
                brainrot = [word["word"] for word in self.brainrot]
                whitelist = [word["word"] for word in self.whitelist]
                admins = [admin["name"] for admin in self.admins]
                guilds = [guild["name"] for guild in self.guilds]
                channels = [
                    f"{guild['name']} -> {channel['name']}"
                    for channel in self.channels
                    for guild in self.guilds
                    if guild["guild_id"] == channel["guild_id"]
                ]
                config = [
                    f"{entry['name']}: {entry['value']}" for entry in self.config
                ]
            except Exception as e:
                print(f"[Database Data] Error generating embed fields: {e}")
                return embed
            fields = [
                {
                    "name": "Banned Words",
                    "value": "- " + "\n- ".join(map(str, brainrot)),
                    "inline": False,
                },
                {
                    "name": "Whitelist",
                    "value": "- " + "\n- ".join(map(str, whitelist)),
                    "inline": False,
                },
                {
                    "name": "Admins",
                    "value": "- " + "\n- ".join(map(str, admins)),
                    "inline": False,
                },
                {
                    "name": "Guilds",
                    "value": "- " + "\n- ".join(map(str, guilds)),
                    "inline": False,
                },
                {
                    "name": "Channels",
                    "value": "- " + "\n- ".join(map(str, channels)),
                    "inline": False,
                },
                {
                    "name": "Config",
                    "value": "- " + "\n- ".join(map(str, config)),
                },
            ]
            if embed:
                for field in fields:
                    print(field)
                    embed.add_field(
                        name=field["name"], value=field["value"], inline=False
                    )
                return embed
            print("[Database Data] Done generating embed fields!")
            return fields

        def update(
            self,
            guilds: list = None,
            channels: list = None,
            brainrot: list = None,
            whitelist: list = None,
            admins: list = None,
            config: list = None,
        ):
            """Update the database data object, do this after reading from the database"""
            if guilds:
                self.guilds = guilds
            if channels:
                self.channels = channels
            if brainrot:
                self.brainrot = brainrot
            if whitelist:
                self.whitelist = whitelist
            if admins:
                self.admins = admins
            if config:
                self.config = config
            self.write_count += 1

        def is_data_empty(self):
            if (
                len(self.guilds) == 0
                and len(self.channels) == 0
                and len(self.brainrot) == 0
                and len(self.whitelist) == 0
                and len(self.admins) == 0
            ):
                return True
            return False

        def clear(self):
            self.guilds = []
            self.channels = []
            self.brainrot = []
            self.whitelist = []
            self.admins = []
            self.config = []
            self.write_count = 0

        # Config table functions

        def config_has(self, name: str):
            """Deprecated: Check if a config entry exists"""
            for entry in self.config:
                if entry["name"] == name:
                    return True
            return False

        def config_get(self, name: str):
            """Deprecated: Get a config entry value"""
            for entry in self.config:
                if entry["name"] == name:
                    return entry["value"]
            return None

