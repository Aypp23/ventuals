#!/usr/bin/env python3
"""
Simple Ventuals Liquidation Alert Bot
Minimal working version - Compatible with python-telegram-bot==13.15
"""

import asyncio
import json
import aiohttp
import ssl
import logging
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = "8466584047:AAG1eN3qwL3vjwUj1O-oThjk-CFfE3LkMLo"

# Store subscribed users
subscribed_users = {}

async def get_user_positions(wallet_address: str):
    """Get user positions from Ventuals API"""
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            data = {
                'type': 'clearinghouseState',
                'user': wallet_address,
                'dex': 'vntls'
            }
            
            async with session.post('https://api.hyperliquid-testnet.xyz/info', json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('assetPositions', [])
                else:
                    logger.error(f"API error: {response.status}")
                    return []
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return []

def start_command(update: Update, context: CallbackContext):
    """Handle /start command"""
    user_id = update.effective_user.id
    
    if len(context.args) == 0:
        update.message.reply_text(
            "🤖 **Ventuals Liquidation Alert Bot**\n\n"
            "Usage: `/start <wallet_address> [threshold]`\n\n"
            "Example: `/start 0x2BD5A85BFdBFB9B6CD3FB17F552a39E899BFcd40 5`\n\n"
            "This will monitor your positions and alert when within 5% of liquidation price.",
            parse_mode='Markdown'
        )
        return
    
    wallet_address = context.args[0]
    alert_threshold = 5.0  # Default threshold (5% of liquidation price)
    
    if len(context.args) > 1:
        try:
            alert_threshold = float(context.args[1])
        except ValueError:
            update.message.reply_text("❌ Invalid threshold. Please use a number.")
            return
    
    # Add user to monitoring
    subscribed_users[user_id] = {
        'wallet_address': wallet_address,
        'alert_threshold': alert_threshold
    }
    
    message = f"""
✅ **Monitoring Started**

**Wallet:** `{wallet_address}`
**Alert Threshold:** {alert_threshold}%

I'll monitor your Ventuals positions and alert you when you're within {alert_threshold}% of liquidation price.

Use `/status` to check your current positions.
Use `/stop` to stop monitoring.
    """
    
    update.message.reply_text(message, parse_mode='Markdown')

async def status_command_async(update: Update, context: CallbackContext):
    """Handle /status command"""
    user_id = update.effective_user.id
    
    if user_id not in subscribed_users:
        await update.message.reply_text("❌ You're not being monitored. Use `/start <wallet_address>` to begin.")
        return
    
    wallet_address = subscribed_users[user_id]['wallet_address']
    alert_threshold = subscribed_users[user_id]['alert_threshold']
    
    positions = await get_user_positions(wallet_address)
    
    if not positions:
        await update.message.reply_text("📊 No active positions found.")
        return
    
    message = f"📊 **Position Status**\n\n"
    message += f"**Wallet:** `{wallet_address}`\n"
    message += f"**Alert Threshold:** {alert_threshold}%\n\n"
    
    for i, position in enumerate(positions, 1):
        pos = position['position']
        coin = pos['coin']
        size = float(pos['szi'])
        unrealized_pnl = pos['unrealizedPnl']
        liquidation_price = float(pos['liquidationPx'])
        position_value = float(pos['positionValue'])
        
        # Calculate current price
        current_price = position_value / abs(size) if size != 0 else 0
        
        # Calculate percentage distance to liquidation
        if size > 0:  # Long position
            price_distance = current_price - liquidation_price
            percentage_distance = (price_distance / liquidation_price) * 100
        else:  # Short position
            price_distance = liquidation_price - current_price
            percentage_distance = (price_distance / liquidation_price) * 100
        
        # Calculate dollar distance for display
        dollar_distance = price_distance * abs(size)
        
        # Status emoji based on percentage distance
        if percentage_distance <= alert_threshold:
            status_emoji = "🔴"
        elif percentage_distance <= alert_threshold * 2:
            status_emoji = "🟡"
        else:
            status_emoji = "🟢"
        
        # Clean token name (remove vntls: prefix)
        clean_coin = coin.replace('vntls:', '') if coin.startswith('vntls:') else coin
        
        # Calculate entry and current position values in dollars
        entry_price = float(pos['entryPx'])
        entry_value = entry_price * abs(size)
        current_value = position_value
        
        message += f"{status_emoji} **{clean_coin}**\n"
        message += f"   Size: {size}\n"
        message += f"   Entry Price: ${entry_price:.4f}\n"
        message += f"   Entry Value: ${entry_value:.2f}\n"
        message += f"   Current Price: ${current_price:.4f}\n"
        message += f"   Current Value: ${current_value:.2f}\n"
        message += f"   Liquidation Price: ${liquidation_price:.4f}\n"
        message += f"   Distance to Liquidation: {percentage_distance:.1f}% (${dollar_distance:.2f})\n"
        message += f"   PnL: ${unrealized_pnl}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop command"""
    user_id = update.effective_user.id
    
    if user_id in subscribed_users:
        del subscribed_users[user_id]
        await update.message.reply_text("🛑 Monitoring stopped. You won't receive liquidation alerts anymore.")
    else:
        await update.message.reply_text("❌ You're not being monitored.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
🤖 **Ventuals Liquidation Alert Bot**

**Commands:**
`/start <wallet_address> [threshold]` - Start monitoring (default threshold: 5%)
`/status` - Check current positions
`/stop` - Stop monitoring
`/help` - Show this help

**Example:**
`/start 0x2BD5A85BFdBFB9B6CD3FB17F552a39E899BFcd40 3`

This will monitor the wallet and alert when positions are within 3% of liquidation price.
    """
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def monitor_positions():
    """Monitor all users for liquidation risk"""
    logger.info("Starting liquidation monitoring...")
    
    while True:
        try:
            for user_id, user_data in subscribed_users.items():
                wallet_address = user_data['wallet_address']
                alert_threshold = user_data['alert_threshold']
                
                positions = await get_user_positions(wallet_address)
                
                for position in positions:
                    pos = position['position']
                    coin = pos['coin']
                    size = float(pos['szi'])
                    liquidation_price = float(pos['liquidationPx'])
                    position_value = float(pos['positionValue'])
                    
                    # Calculate percentage distance to liquidation
                    current_price = position_value / abs(size) if size != 0 else 0
                    
                    if size > 0:  # Long
                        price_distance = current_price - liquidation_price
                        percentage_distance = (price_distance / liquidation_price) * 100
                    else:  # Short
                        price_distance = liquidation_price - current_price
                        percentage_distance = (price_distance / liquidation_price) * 100
                    
                    if percentage_distance <= alert_threshold:
                        # Clean token name
                        clean_coin = coin.replace('vntls:', '') if coin.startswith('vntls:') else coin
                        
                        # Calculate entry and current position values
                        entry_price = float(pos['entryPx'])
                        entry_value = entry_price * abs(size)
                        current_value = position_value
                        
                        message = f"""
🚨 **LIQUIDATION ALERT** 🚨

**Position:** {clean_coin}
**Side:** {'LONG' if size > 0 else 'SHORT'}
**Size:** {size}
**Entry Price:** ${entry_price:.4f}
**Entry Value:** ${entry_value:.2f}
**Current Price:** ${current_price:.4f}
**Current Value:** ${current_value:.2f}
**Liquidation Price:** ${liquidation_price}
**Distance to Liquidation:** {percentage_distance:.1f}% (${price_distance * abs(size):.2f})

**Action Required:** Consider closing position or adding margin!
                        """
                        
                        bot = Bot(token=BOT_TOKEN)
                        await bot.send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode='Markdown'
                        )
                        
                        logger.info(f"Alert sent to user {user_id} for {coin}")
            
            # Wait 30 seconds before next check
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            await asyncio.sleep(30)

def main():
    """Main function to start the bot"""
    print("🤖 Ventuals Liquidation Alert Bot starting...")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Start monitoring in background
    asyncio.create_task(monitor_positions())
    
    print("✅ Bot is ready! Users can now use /start to begin monitoring.")
    
    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()
