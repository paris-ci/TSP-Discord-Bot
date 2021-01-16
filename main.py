# Setting up asyncio to use uvloop if possible, a faster implementation on the event loop
import asyncio

try:
    # noinspection PyUnresolvedReferences
    import uvloop
except ImportError:
    print("Using the not-so-fast default asyncio event loop. Consider installing uvloop.")
    pass
else:
    print("Using the fast uvloop asyncio event loop")
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

print("Loading...")

# Importing the discord API warpper

print("Loading discord...")
import discord

print("Import bot...")
from utils.bot import CustomBot

print("Creating bot...")
bot = CustomBot(case_insensitive=True)
logger = bot.logger

logger.info("Created logger!")



logger.debug("Loading cogs : ")

######################
#                 |  #
#   ADD COGS HERE |  #
#                 V  #
# ###############   ##

cogs = ['jishaku',
        'cogs.error_handling',
        'cogs.moodle',
        'cogs.notes',
        'cogs.profile',
        'cogs.trombi',
        ]

for extension in cogs:
    try:
        bot.load_extension(extension)
        logger.debug(f"> {extension} loaded!")
    except Exception as e:
        logger.exception('> Failed to load extension {}\n{}: {}'.format(extension, type(e).__name__, e))

logger.info("Everything seems fine, we are now connecting to discord.")

try:
    # bot.loop.set_debug(True)
    bot.loop.run_until_complete(bot.start(bot.token))
except KeyboardInterrupt:
    pass
finally:
    logger.warning("Quitting -- Bye")
    game = discord.Game(name=f"Restarting...")
    bot.loop.run_until_complete(bot.change_presence(status=discord.Status.dnd, activity=game))

    bot.loop.run_until_complete(bot.logout())

    bot.loop.run_until_complete(asyncio.sleep(3))
    bot.loop.close()
    logger.warning("Exited -- Bye")