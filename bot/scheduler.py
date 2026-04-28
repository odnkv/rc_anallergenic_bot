import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from bot import wb_parser, sheets

logger = logging.getLogger(__name__)

QUERY = "royal canin anallergenic для кошек"

scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


def format_prices_message(products: list[dict], is_alert: bool = False) -> str:
    if not products:
        return "❌ Товары не найдены."

    lines = ["🛒 *Royal Canin Anallergenic* — топ-5 цен:\n"]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    for i, p in enumerate(products):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        lines.append(
            f"{medal} *{p['price']:,}₽* — {p['brand']} {p['name']}\n"
            f"   [Открыть на WB]({p['url']})\n"
        )

    if is_alert:
        lines.insert(0, "🔔 *Найдена цена по вашему условию!*\n")

    return "\n".join(lines)


async def run_price_update(bot=None):
    """Fetch fresh prices, save to Sheets, notify subscribers if threshold met."""
    logger.info("Starting scheduled price update...")

    try:
        products = await wb_parser.fetch_top_prices(QUERY, top_n=5)
    except Exception as e:
        logger.error(f"Failed to fetch prices: {e}")
        return

    if not products:
        logger.warning("No products returned, skipping save.")
        return

    try:
        sheets.save_prices(products)
    except Exception as e:
        logger.error(f"Failed to save prices to Sheets: {e}")

    if bot is None:
        return

    # Check subscriptions
    try:
        subscriptions = sheets.get_active_subscriptions()
    except Exception as e:
        logger.error(f"Failed to load subscriptions: {e}")
        return

    min_price = products[0]["price"]

    for sub in subscriptions:
        try:
            user_id = int(sub["user_id"])
            threshold = int(sub["threshold"])
            direction = sub.get("direction", "below")

            triggered = (direction == "below" and min_price <= threshold)

            if triggered:
                alert_products = [p for p in products if p["price"] <= threshold]
                msg = format_prices_message(alert_products, is_alert=True)
                msg += f"\n💡 Ваш порог: ≤ {threshold:,}₽ | Минимальная цена сейчас: *{min_price:,}₽*"
                await bot.send_message(
                    chat_id=user_id,
                    text=msg,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
                logger.info(f"Alert sent to user {user_id}")
        except Exception as e:
            logger.error(f"Error notifying user {sub.get('user_id')}: {e}")


def start_scheduler(bot):
    """Start the hourly price update job."""
    scheduler.add_job(
        run_price_update,
        trigger=IntervalTrigger(hours=1),
        kwargs={"bot": bot},
        id="price_update",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started — price updates every hour.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
