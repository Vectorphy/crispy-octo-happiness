"""Compatibility entrypoint for hosts that invoke main.py by default."""

from bot import BOT_DEVELOPER_ID, TOKEN, cpo, logger


if __name__ == "__main__":
    if not TOKEN:
        logger.error("DISCORD_BOT_TOKEN not found in .env file")
    elif not BOT_DEVELOPER_ID:
        logger.warning("BOT_DEVELOPER_ID not found or invalid in .env file. Some features may be limited.")
        cpo.run(TOKEN)
    else:
        logger.info("Starting the bot...")
        cpo.run(TOKEN)