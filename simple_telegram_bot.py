#!/usr/bin/env python3
"""
Simple Ventuals Liquidation Alert Bot using requests
Works with Python 3.13 without telegram library issues
"""

import asyncio
import json
import aiohttp
import ssl
import logging
import requests
import time
import os
from threading import Thread
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot token from environment variable
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
    exit(1)

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Store subscribed users
subscribed_users = {}

# Store last alert times to prevent spam
last_alerts = {}

def get_updates(offset=None):
    """Get updates from Telegram"""
    try:
        url = f"{BASE_URL}/getUpdates"
        params = {'offset': offset, 'timeout': 30}
        response = requests.get(url, params=params, timeout=35)
        return response.json()
    except Exception as e:
        logger.error(f"Error getting updates: {e}")
        return None

def send_message(chat_id, text, parse_mode='Markdown'):
    """Send message to Telegram"""
    try:
        url = f"{BASE_URL}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
        response = requests.post(url, data=data, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return None

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
                    return result
                else:
                    logger.error(f"API error: {response.status}")
                    return {}
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return {}

def handle_start_command(chat_id, args):
    """Handle /start command"""
    if len(args) == 0:
        send_message(chat_id, 
            "🤖 **Ventuals Liquidation Alert Bot**\n\n"
            "**Welcome!** I'll monitor your Ventuals positions and alert you when you're close to liquidation.\n\n"
            "**📋 Usage:**\n"
            "`/start <wallet_address> [threshold] [duration]`\n\n"
            "**📊 Parameters:**\n"
            "• `wallet_address` - Your Ventuals wallet address (required)\n"
            "• `threshold` - Alert when within X% of liquidation (default: 5%)\n"
            "• `duration` - Minutes between alerts in seconds (default: 300 = 5min)\n\n"
            "**💡 Examples:**\n"
            "`/start 0x2BD5A85BFdBFB9B6CD3FB17F552a39E899BFcd40`\n"
            "→ Default: 5% threshold, 5-minute alerts\n\n"
            "`/start 0x2BD5A85BFdBFB9B6CD3FB17F552a39E899BFcd40 3 600`\n"
            "→ 3% threshold, 10-minute alerts\n\n"
            "`/start 0x2BD5A85BFdBFB9B6CD3FB17F552a39E899BFcd40 2 120`\n"
            "→ 2% threshold, 2-minute alerts\n\n"
            "**⚙️ Other Commands:**\n"
            "`/status` - Check current positions\n"
            "`/account` - View comprehensive account overview\n"
            "`/settings` - Change alert settings\n"
            "`/stop` - Stop monitoring\n"
            "`/help` - Detailed help\n\n"
            "Ready to protect your positions! 🛡️\n\n"
            "Built by [aomine](https://x.com/ololade_eth)"
        )
        return
    
    wallet_address = args[0]
    alert_threshold = 5.0  # Default threshold (5% of liquidation price)
    
    alert_duration = 300  # Default 5 minutes
    
    if len(args) > 1:
        try:
            alert_threshold = float(args[1])
        except ValueError:
            send_message(chat_id, "❌ Invalid threshold. Please use a number.")
            return
    
    if len(args) > 2:
        try:
            alert_duration = int(args[2])
            if alert_duration < 60:  # Minimum 1 minute
                send_message(chat_id, "❌ Alert duration must be at least 60 seconds (1 minute).")
                return
        except ValueError:
            send_message(chat_id, "❌ Invalid duration. Please use a number in seconds.")
            return
    
    # Add user to monitoring
    subscribed_users[chat_id] = {
        'wallet_address': wallet_address,
        'alert_threshold': alert_threshold,
        'alert_duration': alert_duration
    }
    
    duration_minutes = alert_duration // 60
    duration_seconds = alert_duration % 60
    duration_text = f"{duration_minutes}m {duration_seconds}s" if duration_seconds > 0 else f"{duration_minutes}m"
    
    message = f"""✅ **Monitoring Started**

**Wallet:** `{wallet_address}`
**Alert Threshold:** {alert_threshold}%
**Alert Duration:** {duration_text}

I'll monitor your Ventuals positions and alert you when you're within {alert_threshold}% of liquidation price.
Alerts will be sent every {duration_text} to prevent spam.

**Available Commands:**
• `/status` - Check current positions
• `/account` - View comprehensive account overview
• `/stop` - Stop monitoring
• `/settings` - Change alert settings"""
    
    send_message(chat_id, message)

async def handle_status_command(chat_id):
    """Handle /status command"""
    if chat_id not in subscribed_users:
        send_message(chat_id, "❌ You're not being monitored. Use `/start <wallet_address>` to begin.")
        return
    
    wallet_address = subscribed_users[chat_id]['wallet_address']
    alert_threshold = subscribed_users[chat_id]['alert_threshold']
    alert_duration = subscribed_users[chat_id]['alert_duration']
    
    user_data = await get_user_positions(wallet_address)
    
    if not user_data or not user_data.get('assetPositions'):
        send_message(chat_id, "📊 No active positions found.")
        return
    
    positions = user_data['assetPositions']
    margin_summary = user_data.get('marginSummary', {})
    
    duration_minutes = alert_duration // 60
    duration_seconds = alert_duration % 60
    duration_text = f"{duration_minutes}m {duration_seconds}s" if duration_seconds > 0 else f"{duration_minutes}m"
    
    # Portfolio summary
    try:
        account_value = float(margin_summary.get('accountValue', 0))
        total_margin_used = float(margin_summary.get('totalMarginUsed', 0))
        total_raw_usd = float(margin_summary.get('totalRawUsd', 0))
    except (ValueError, TypeError):
        account_value = 0
        total_margin_used = 0
        total_raw_usd = 0
    
    # Calculate account PnL (Account Value - $500)
    account_pnl = account_value - 500
    
    message = f"📊 **Account Status**\n\n"
    message += f"**Wallet:** `{wallet_address}`\n\n"
    
    message += f"**Alert Settings:**\n"
    message += f"• Threshold: {alert_threshold}%\n"
    message += f"• Duration: {duration_text}\n\n"
    
    message += f"**Active Positions:**\n\n"
    
    total_unrealized_pnl = 0
    
    for i, position in enumerate(positions, 1):
        try:
            pos = position['position']
            coin = pos['coin']
            size = float(pos['szi'])
            unrealized_pnl = float(pos['unrealizedPnl'])
            liquidation_price = pos['liquidationPx']
            position_value = float(pos['positionValue'])
            
            # Handle None liquidation price (cross-margin positions)
            if liquidation_price is None:
                # Calculate liquidation price for cross-margin positions
                entry_price = float(pos['entryPx'])
                leverage = pos['leverage']['value']
                
                if size > 0:  # Long position
                    liquidation_price = entry_price * (1 - 1/leverage)
                else:  # Short position
                    liquidation_price = entry_price * (1 + 1/leverage)
            else:
                liquidation_price = float(liquidation_price)
            
            # Add to total PnL
            total_unrealized_pnl += unrealized_pnl
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Error processing position {i}: {e}")
            continue
        
        # Calculate current price
        current_price = position_value / abs(size) if size != 0 else 0
        
        # Calculate percentage distance to liquidation
        if size > 0:  # Long position
            price_distance = current_price - liquidation_price
            percentage_distance = (price_distance / liquidation_price) * 100
        else:  # Short position
            price_distance = liquidation_price - current_price
            percentage_distance = (price_distance / liquidation_price) * 100
        
        # Calculate dollar distance
        dollar_distance = price_distance * abs(size)
        
        # Calculate entry and current position values in dollars
        entry_price = float(pos['entryPx'])
        entry_value = entry_price * abs(size)
        current_value = position_value
        
        # Status emoji based on percentage distance
        if percentage_distance <= alert_threshold:
            status_emoji = "🔴"
        elif percentage_distance <= alert_threshold * 2:
            status_emoji = "🟡"
        else:
            status_emoji = "🟢"
        
        # Clean token name (remove vntls: prefix)
        clean_coin = coin.replace('vntls:', '') if coin.startswith('vntls:') else coin
        
        message += f"{status_emoji} **{clean_coin}**\n"
        message += f"   Size: {size}\n"
        message += f"   Entry Price: ${entry_price:.4f}\n"
        message += f"   Entry Value: ${entry_value:,.2f}\n"
        message += f"   Current Price: ${current_price:.4f}\n"
        message += f"   Current Value: ${current_value:,.2f}\n"
        
        # Display liquidation info
        message += f"   Liquidation Price: ${liquidation_price:.4f}\n"
        message += f"   Distance to Liquidation: {percentage_distance:.1f}% (${dollar_distance:,.2f})\n"
        
        message += f"   PnL: ${unrealized_pnl:,.2f}\n\n"
    
    # Add total PnL summary
    pnl_emoji = "🟢" if total_unrealized_pnl >= 0 else "🔴"
    message += f"**Total Unrealized PnL:** {pnl_emoji} ${total_unrealized_pnl:,.2f}\n"
    
    send_message(chat_id, message)

def handle_stop_command(chat_id):
    """Handle /stop command"""
    if chat_id in subscribed_users:
        del subscribed_users[chat_id]
        send_message(chat_id, "🛑 Monitoring stopped. You won't receive liquidation alerts anymore.")
    else:
        send_message(chat_id, "❌ You're not being monitored.")

def handle_settings_command(chat_id, args):
    """Handle /settings command"""
    if chat_id not in subscribed_users:
        send_message(chat_id, "❌ You're not being monitored. Use `/start <wallet_address>` to begin.")
        return
    
    if len(args) == 0:
        current_settings = subscribed_users[chat_id]
        duration_minutes = current_settings['alert_duration'] // 60
        duration_seconds = current_settings['alert_duration'] % 60
        duration_text = f"{duration_minutes}m {duration_seconds}s" if duration_seconds > 0 else f"{duration_minutes}m"
        
        send_message(chat_id, f"""⚙️ **Current Settings**

**Alert Threshold:** {current_settings['alert_threshold']}%
**Alert Duration:** {duration_text}

**To change settings:**
`/settings <threshold> [duration_seconds]`

**Examples:**
`/settings 3` - Change threshold to 3%
`/settings 5 600` - Change threshold to 5% and duration to 10 minutes
`/settings 2 120` - Change threshold to 2% and duration to 2 minutes""")
        return
    
    # Update threshold
    try:
        new_threshold = float(args[0])
        if new_threshold <= 0 or new_threshold > 50:
            send_message(chat_id, "❌ Threshold must be between 0.1% and 50%.")
            return
    except ValueError:
        send_message(chat_id, "❌ Invalid threshold. Please use a number.")
        return
    
    # Update duration if provided
    new_duration = subscribed_users[chat_id]['alert_duration']  # Keep current if not specified
    if len(args) > 1:
        try:
            new_duration = int(args[1])
            if new_duration < 60:
                send_message(chat_id, "❌ Alert duration must be at least 60 seconds (1 minute).")
                return
        except ValueError:
            send_message(chat_id, "❌ Invalid duration. Please use a number in seconds.")
            return
    
    # Update settings
    subscribed_users[chat_id]['alert_threshold'] = new_threshold
    subscribed_users[chat_id]['alert_duration'] = new_duration
    
    duration_minutes = new_duration // 60
    duration_seconds = new_duration % 60
    duration_text = f"{duration_minutes}m {duration_seconds}s" if duration_seconds > 0 else f"{duration_minutes}m"
    
    send_message(chat_id, f"""✅ **Settings Updated**

**New Alert Threshold:** {new_threshold}%
**New Alert Duration:** {duration_text}

Your monitoring settings have been updated!""")

async def handle_account_command(chat_id):
    """Handle /account command - show comprehensive account information"""
    if chat_id not in subscribed_users:
        send_message(chat_id, "❌ You're not being monitored. Use `/start <wallet_address>` to begin.")
        return
    
    wallet_address = subscribed_users[chat_id]['wallet_address']
    
    try:
        # Get account data
        user_data = await get_user_positions(wallet_address)
        if not user_data:
            send_message(chat_id, "❌ Unable to fetch account data. Please try again.")
            return
        
        # Get user fills for trading statistics
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        
        async with aiohttp.ClientSession(connector=connector) as session:
            fills_data = {
                'type': 'userFills',
                'user': wallet_address,
                'dex': 'vntls'
            }
            
            async with session.post('https://api.hyperliquid-testnet.xyz/info', json=fills_data) as response:
                if response.status == 200:
                    fills = await response.json()
                    
                    # Calculate trading statistics
                    total_trades = len(fills)
                    profitable_trades = 0
                    losing_trades = 0
                    total_realized_pnl = 0
                    largest_win = 0
                    largest_loss = 0
                    largest_win_token = ""
                    largest_loss_token = ""
                    
                    for fill in fills:
                        closed_pnl = float(fill.get('closedPnl', 0))
                        coin = fill.get('coin', '')
                        clean_coin = coin.replace('vntls:', '') if coin.startswith('vntls:') else coin
                        total_realized_pnl += closed_pnl
                        
                        if closed_pnl != 0:
                            if closed_pnl > 0:
                                profitable_trades += 1
                                if closed_pnl > largest_win:
                                    largest_win = closed_pnl
                                    largest_win_token = clean_coin
                            else:
                                losing_trades += 1
                                if closed_pnl < largest_loss:
                                    largest_loss = closed_pnl
                                    largest_loss_token = clean_coin
                    
                    win_rate = (profitable_trades / max(profitable_trades + losing_trades, 1)) * 100
                    
                    # Get current positions data
                    margin_summary = user_data.get('marginSummary', {})
                    positions = user_data.get('assetPositions', [])
                    
                    account_value = float(margin_summary.get('accountValue', 0))
                    total_unrealized_pnl = 0
                    
                    for position in positions:
                        pos = position['position']
                        unrealized_pnl = float(pos['unrealizedPnl'])
                        total_unrealized_pnl += unrealized_pnl
                    
                    # Calculate total account PnL
                    total_account_pnl = total_realized_pnl + total_unrealized_pnl
                    
                    # Format the message
                    message = f"📊 **Account Overview**\n\n"
                    message += f"**Wallet Address:**\n`{wallet_address}`\n\n"
                    
                    message += f"**📈 Trading Statistics:**\n"
                    message += f"• Total Trades: {total_trades:,}\n"
                    message += f"• Win Rate: {win_rate:.1f}%\n"
                    message += f"• Profitable Trades: {profitable_trades:,}\n"
                    message += f"• Losing Trades: {losing_trades:,}\n"
                              
                    # Add largest win/loss
                    if largest_win > 0 or largest_loss < 0:
                        message += f"• Largest Win: 🟢 +${largest_win:,.2f} ({largest_win_token})\n"
                        message += f"• Largest Loss: 🔴 ${largest_loss:,.2f} ({largest_loss_token})\n"
                    else:
                        message += f"• Largest Win: No completed wins\n"
                        message += f"• Largest Loss: No completed losses\n"
                    message += "\n"
                    
                    message += f"**💰 PnL Breakdown:**\n"
                    realized_emoji = "🟢" if total_realized_pnl >= 0 else "🔴"
                    unrealized_emoji = "🟢" if total_unrealized_pnl >= 0 else "🔴"
                    total_emoji = "🟢" if total_account_pnl >= 0 else "🔴"
                    
                    message += f"• Realized PnL: {realized_emoji} ${total_realized_pnl:,.2f}\n"
                    message += f"• Unrealized PnL: {unrealized_emoji} ${total_unrealized_pnl:,.2f}\n\n"
                    
                    message += f"**🏦 Portfolio Summary:**\n"
                    message += f"• Account Value: ${account_value:,.2f}\n"
                    message += f"• Active Positions: {len(positions):,}\n"
                    
                    
                    send_message(chat_id, message)
                    
                else:
                    send_message(chat_id, "❌ Unable to fetch trading history. Please try again.")
                    
    except Exception as e:
        logger.error(f"Error in account command: {e}")
        send_message(chat_id, "❌ Error fetching account data. Please try again.")

def handle_help_command(chat_id):
    """Handle /help command"""
    help_text = """🤖 **Ventuals Liquidation Alert Bot**

**Commands:**
`/start <wallet_address> [threshold] [duration]` - Start monitoring
`/status` - Check current positions
`/account` - Show comprehensive account overview
`/settings [threshold] [duration]` - Change alert settings
`/stop` - Stop monitoring
`/help` - Show this help

**Examples:**
`/start 0x2BD5A85BFdBFB9B6CD3FB17F552a39E899BFcd40 3 600`
- Monitor wallet with 3% threshold and 10-minute alerts

`/start 0x2BD5A85BFdBFB9B6CD3FB17F552a39E899BFcd40 5`
- Monitor wallet with 5% threshold and default 5-minute alerts

**Default Settings:**
- Threshold: 5% from liquidation
- Duration: 5 minutes between alerts"""
    
    send_message(chat_id, help_text)

def process_update(update):
    """Process a single update"""
    try:
        message = update.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '')
        
        if not chat_id or not text:
            return
        
        logger.info(f"Processing command: {text} from user {chat_id}")
        
        # Parse command and arguments
        parts = text.split()
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if command == '/start':
            handle_start_command(chat_id, args)
        elif command == '/status':
            # Handle status command synchronously to avoid event loop issues
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(handle_status_command(chat_id))
            finally:
                loop.close()
        elif command == '/account':
            # Handle account command synchronously to avoid event loop issues
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(handle_account_command(chat_id))
            finally:
                loop.close()
        elif command == '/settings':
            handle_settings_command(chat_id, args)
        elif command == '/stop':
            handle_stop_command(chat_id)
        elif command == '/help':
            handle_help_command(chat_id)
        else:
            send_message(chat_id, "Unknown command. Use /help for available commands.")
            
    except Exception as e:
        logger.error(f"Error processing update: {e}")

async def monitor_positions():
    """Monitor all users for liquidation risk"""
    logger.info("Starting liquidation monitoring...")
    
    while True:
        try:
            for chat_id, user_data in subscribed_users.items():
                wallet_address = user_data['wallet_address']
                alert_threshold = user_data['alert_threshold']
                alert_duration = user_data['alert_duration']
                
                user_data = await get_user_positions(wallet_address)
                
                if not user_data or not user_data.get('assetPositions'):
                    continue
                    
                positions = user_data['assetPositions']
                
                for position in positions:
                    pos = position['position']
                    coin = pos['coin']
                    size = float(pos['szi'])
                    liquidation_price = pos['liquidationPx']
                    position_value = float(pos['positionValue'])
                    
                    # Handle None liquidation price (cross-margin positions)
                    if liquidation_price is None:
                        # Calculate liquidation price for cross-margin positions
                        entry_price = float(pos['entryPx'])
                        leverage = pos['leverage']['value']
                        
                        if size > 0:  # Long position
                            liquidation_price = entry_price * (1 - 1/leverage)
                        else:  # Short position
                            liquidation_price = entry_price * (1 + 1/leverage)
                    else:
                        liquidation_price = float(liquidation_price)
                    
                    # Calculate percentage distance to liquidation
                    current_price = position_value / abs(size) if size != 0 else 0
                    
                    if size > 0:  # Long
                        price_distance = current_price - liquidation_price
                        percentage_distance = (price_distance / liquidation_price) * 100
                    else:  # Short
                        price_distance = liquidation_price - current_price
                        percentage_distance = (price_distance / liquidation_price) * 100
                    
                    if percentage_distance <= alert_threshold:
                        # Check if we should send alert (prevent spam)
                        alert_key = f"{chat_id}_{coin}"
                        current_time = time.time()
                        
                        # Send alert only if it's been more than the user's custom duration since last alert for this position
                        if alert_key not in last_alerts or (current_time - last_alerts[alert_key]) > alert_duration:
                            # Clean token name
                            clean_coin = coin.replace('vntls:', '') if coin.startswith('vntls:') else coin
                            
                            # Calculate entry and current position values
                            entry_price = float(pos['entryPx'])
                            entry_value = entry_price * abs(size)
                            current_value = position_value
                            
                            message = f"""🚨 **LIQUIDATION ALERT** 🚨

**Position:** {clean_coin}
**Side:** {'LONG' if size > 0 else 'SHORT'}
**Size:** {size}
**Entry Price:** ${entry_price:.4f}
**Entry Value:** ${entry_value:.2f}
**Current Price:** ${current_price:.4f}
**Current Value:** ${current_value:.2f}
**Liquidation Price:** ${liquidation_price}
**Distance to Liquidation:** {percentage_distance:.1f}% (${price_distance * abs(size):.2f})

**Action Required:** Consider closing position or adding margin!"""
                            
                            send_message(chat_id, message)
                            last_alerts[alert_key] = current_time
                            duration_minutes = alert_duration // 60
                            duration_seconds = alert_duration % 60
                            duration_text = f"{duration_minutes}m {duration_seconds}s" if duration_seconds > 0 else f"{duration_minutes}m"
                            logger.info(f"Alert sent to user {chat_id} for {clean_coin} (next alert in {duration_text})")
                        else:
                            logger.info(f"Alert skipped for {coin} - too soon (cooldown active)")
            
            # Wait 30 seconds before next check
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            await asyncio.sleep(30)

def bot_main():
    """Main bot loop"""
    logger.info("🤖 Ventuals Liquidation Alert Bot starting...")
    
    offset = None
    
    while True:
        try:
            updates = get_updates(offset)
            if updates and updates.get('ok'):
                for update in updates.get('result', []):
                    process_update(update)
                    offset = update.get('update_id') + 1
            else:
                time.sleep(1)
        except Exception as e:
            logger.error(f"Error in bot main loop: {e}")
            time.sleep(5)

def main():
    """Main function"""
    print("🤖 Ventuals Liquidation Alert Bot starting...")
    
    # Start monitoring in background thread
    def run_monitoring():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(monitor_positions())
    
    monitoring_thread = Thread(target=run_monitoring, daemon=True)
    monitoring_thread.start()
    
    print("✅ Bot is ready! Users can now use /start to begin monitoring.")
    
    # Start main bot loop
    bot_main()

if __name__ == "__main__":
    main()
