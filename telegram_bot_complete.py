#!/usr/bin/env python3
"""
Complete Telegram Bot for Ventuals Liquidation Alerts
Includes command handlers and webhook setup
"""

import asyncio
import json
import aiohttp
import ssl
import logging
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class VentualsLiquidationBot:
    def __init__(self, api_url: str = "https://api.hyperliquid-testnet.xyz/info"):
        self.api_url = api_url
        self.subscribed_users = {}
        
    async def get_user_positions(self, wallet_address: str):
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
                
                async with session.post(self.api_url, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('assetPositions', [])
                    else:
                        logger.error(f"API error: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    def calculate_liquidation_distance(self, position):
        """Calculate distance to liquidation in dollars"""
        try:
            pos = position['position']
            current_value = float(pos['positionValue'])
            liquidation_price = float(pos['liquidationPx'])
            entry_price = float(pos['entryPx'])
            size = float(pos['szi'])
            
            # Calculate current price (approximate from position value and size)
            current_price = current_value / abs(size) if size != 0 else 0
            
            # Calculate distance to liquidation
            if size > 0:  # Long position
                price_distance = current_price - liquidation_price
            else:  # Short position
                price_distance = liquidation_price - current_price
            
            # Convert to dollar distance
            dollar_distance = price_distance * abs(size)
            
            return dollar_distance, current_price, liquidation_price
        except Exception as e:
            logger.error(f"Error calculating liquidation distance: {e}")
            return None, None, None
    
    async def send_liquidation_alert(self, user_id: int, position_data: dict):
        """Send liquidation alert to user"""
        try:
            pos = position_data['position']
            coin = pos['coin']
            size = pos['szi']
            liquidation_price = pos['liquidationPx']
            unrealized_pnl = pos['unrealizedPnl']
            leverage = pos['leverage']['value']
            margin_type = pos['leverage']['type']
            
            dollar_distance, current_price, _ = self.calculate_liquidation_distance(position_data)
            
            message = f"""
🚨 **LIQUIDATION ALERT** 🚨

**Position:** {coin}
**Side:** {'LONG' if float(size) > 0 else 'SHORT'}
**Size:** {size}
**Leverage:** {leverage}x ({margin_type})
**Current Price:** ${current_price:.4f}
**Liquidation Price:** ${liquidation_price}

⚠️ **Distance to Liquidation:** ${dollar_distance:.2f}
📉 **Unrealized PnL:** ${unrealized_pnl}

**Action Required:** Consider closing position or adding margin!
            """
            
            # Get bot instance from context
            bot = Bot(token="8466584047:AAG1eN3qwL3vjwUj1O-oThjk-CFfE3LkMLo")
            await bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
            
            logger.info(f"Liquidation alert sent to user {user_id} for {coin}")
            
        except TelegramError as e:
            logger.error(f"Telegram error: {e}")
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
    
    async def check_positions_for_user(self, user_id: int, wallet_address: str, alert_threshold: float):
        """Check positions for a specific user and send alerts if needed"""
        positions = await self.get_user_positions(wallet_address)
        
        if not positions:
            return
        
        for position in positions:
            dollar_distance, current_price, liquidation_price = self.calculate_liquidation_distance(position)
            
            if dollar_distance is not None and dollar_distance <= alert_threshold:
                await self.send_liquidation_alert(user_id, position)
    
    async def monitor_all_users(self):
        """Monitor all subscribed users for liquidation risk"""
        logger.info("Starting liquidation monitoring...")
        
        while True:
            try:
                for user_id, user_data in self.subscribed_users.items():
                    wallet_address = user_data['wallet_address']
                    alert_threshold = user_data['alert_threshold']
                    
                    await self.check_positions_for_user(user_id, wallet_address, alert_threshold)
                
                # Wait 30 seconds before next check
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(30)
    
    async def get_user_status(self, user_id: int):
        """Get current status of user's positions"""
        if user_id not in self.subscribed_users:
            return "❌ You're not being monitored. Use `/start <wallet_address>` to begin."
        
        wallet_address = self.subscribed_users[user_id]['wallet_address']
        alert_threshold = self.subscribed_users[user_id]['alert_threshold']
        
        positions = await self.get_user_positions(wallet_address)
        
        if not positions:
            return "📊 No active positions found."
        
        message = f"📊 **Position Status**\n\n"
        message += f"**Wallet:** `{wallet_address}`\n"
        message += f"**Alert Threshold:** ${alert_threshold}\n\n"
        
        for i, position in enumerate(positions, 1):
            pos = position['position']
            coin = pos['coin']
            size = pos['szi']
            unrealized_pnl = pos['unrealizedPnl']
            leverage = pos['leverage']['value']
            margin_type = pos['leverage']['type']
            
            dollar_distance, current_price, liquidation_price = self.calculate_liquidation_distance(position)
            
            status_emoji = "🟢" if dollar_distance > alert_threshold else "🟡" if dollar_distance > alert_threshold/2 else "🔴"
            
            message += f"{status_emoji} **{coin}**\n"
            message += f"   Size: {size}\n"
            message += f"   PnL: ${unrealized_pnl}\n"
            message += f"   Distance to Liquidation: ${dollar_distance:.2f}\n\n"
        
        return message

# Global bot instance
ventuals_bot = VentualsLiquidationBot()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    
    if len(context.args) == 0:
        await update.message.reply_text(
            "🤖 **Ventuals Liquidation Alert Bot**\n\n"
            "Usage: `/start <wallet_address> [threshold]`\n\n"
            "Example: `/start 0x2BD5A85BFdBFB9B6CD3FB17F552a39E899BFcd40 10`\n\n"
            "This will monitor your positions and alert when within $10 of liquidation.",
            parse_mode='Markdown'
        )
        return
    
    wallet_address = context.args[0]
    alert_threshold = 5.0  # Default threshold
    
    if len(context.args) > 1:
        try:
            alert_threshold = float(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid threshold. Please use a number.")
            return
    
    # Add user to monitoring
    ventuals_bot.subscribed_users[user_id] = {
        'wallet_address': wallet_address,
        'alert_threshold': alert_threshold
    }
    
    message = f"""
✅ **Monitoring Started**

**Wallet:** `{wallet_address}`
**Alert Threshold:** ${alert_threshold}

I'll monitor your Ventuals positions and alert you when you're within ${alert_threshold} of liquidation.

Use `/status` to check your current positions.
Use `/stop` to stop monitoring.
    """
    
    await update.message.reply_text(message, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    user_id = update.effective_user.id
    status_message = await ventuals_bot.get_user_status(user_id)
    await update.message.reply_text(status_message, parse_mode='Markdown')

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stop command"""
    user_id = update.effective_user.id
    
    if user_id in ventuals_bot.subscribed_users:
        del ventuals_bot.subscribed_users[user_id]
        await update.message.reply_text("🛑 Monitoring stopped. You won't receive liquidation alerts anymore.")
    else:
        await update.message.reply_text("❌ You're not being monitored.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
🤖 **Ventuals Liquidation Alert Bot**

**Commands:**
`/start <wallet_address> [threshold]` - Start monitoring (default threshold: $5)
`/status` - Check current positions
`/stop` - Stop monitoring
`/help` - Show this help

**Example:**
`/start 0x2BD5A85BFdBFB9B6CD3FB17F552a39E899BFcd40 5`

This will monitor the wallet and alert when positions are within $5 of liquidation.

**Features:**
• Real-time position monitoring
• Customizable alert thresholds
• Support for all Ventuals synthetic assets
• Cross and isolated margin tracking
    """
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /list command (admin only)"""
    user_id = update.effective_user.id
    
    # Simple admin check (you can make this more sophisticated)
    if user_id != 123456789:  # Replace with your Telegram user ID
        await update.message.reply_text("❌ Access denied.")
        return
    
    if not ventuals_bot.subscribed_users:
        await update.message.reply_text("📋 No users currently being monitored.")
        return
    
    message = "📋 **Monitored Users:**\n\n"
    for user_id, user_data in ventuals_bot.subscribed_users.items():
        message += f"**User ID:** {user_id}\n"
        message += f"**Wallet:** `{user_data['wallet_address']}`\n"
        message += f"**Threshold:** ${user_data['alert_threshold']}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')

def main():
    """Main function to start the bot"""
    
    # Replace with your bot token from @BotFather
    BOT_TOKEN = "8466584047:AAG1eN3qwL3vjwUj1O-oThjk-CFfE3LkMLo"
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Please set your BOT_TOKEN in the code!")
        print("1. Message @BotFather on Telegram")
        print("2. Create a new bot with /newbot")
        print("3. Copy the token and replace 'YOUR_BOT_TOKEN_HERE'")
        return
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_users_command))
    
    # Start monitoring in background
    asyncio.create_task(ventuals_bot.monitor_all_users())
    
    print("🤖 Ventuals Liquidation Alert Bot starting...")
    print("✅ Bot is ready! Users can now use /start to begin monitoring.")
    
    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
