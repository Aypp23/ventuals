# 🤖 Ventuals Liquidation Alert Bot Setup

## Features

- **Real-time monitoring** of Ventuals positions
- **Customizable alert thresholds** (e.g., alert when within $5 of liquidation)
- **Telegram notifications** when positions are at risk
- **Support for all Ventuals synthetic assets** (vANDRL, vNLINK, vPOLY, etc.)
- **Cross and isolated margin tracking**
- **Position status checking**

## Quick Start

### 1. Create a Telegram Bot

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Send `/newbot`
3. Choose a name for your bot (e.g., "Ventuals Liquidation Alert Bot")
4. Choose a username (e.g., "ventuals_liquidation_bot")
5. Copy the bot token

### 2. Install Dependencies

```bash
pip install -r telegram_bot_requirements.txt
```

### 3. Configure the Bot

Edit `telegram_bot_complete.py` and replace `YOUR_BOT_TOKEN_HERE` with your actual bot token:

```python
BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"  # Your token here
```

### 4. Run the Bot

```bash
python telegram_bot_complete.py
```

## Usage

### Commands

- `/start <wallet_address> [threshold]` - Start monitoring
- `/status` - Check current positions
- `/stop` - Stop monitoring
- `/help` - Show help

### Examples

```
/start 0x2BD5A85BFdBFB9B6CD3FB17F552a39E899BFcd40
/start 0x2BD5A85BFdBFB9B6CD3FB17F552a39E899BFcd40 5
/status
/stop
```

## How It Works

1. **User subscribes** with `/start <wallet_address> [threshold]`
2. **Bot monitors** positions every 30 seconds
3. **Calculates liquidation distance** for each position
4. **Sends alerts** when distance ≤ threshold
5. **User can check status** anytime with `/status`

## Alert Example

```
🚨 LIQUIDATION ALERT 🚨

Position: vntls:vPOLY
Side: SHORT
Size: -200.593
Leverage: 10x (isolated)
Current Price: $9.9100
Liquidation Price: $10.455

⚠️ Distance to Liquidation: $8.50
📉 Unrealized PnL: $-47.47

Action Required: Consider closing position or adding margin!
```

## Deployment Options

### Local Development
```bash
python telegram_bot_complete.py
```

### Cloud Deployment (Heroku)
1. Create `Procfile`:
```
worker: python telegram_bot_complete.py
```
2. Deploy to Heroku
3. Scale worker dyno: `heroku ps:scale worker=1`

### VPS Deployment
1. Install dependencies
2. Use systemd service or screen/tmux
3. Set up monitoring for uptime

## Configuration

### Alert Thresholds
- **Default:** $10
- **Conservative:** $20-50
- **Aggressive:** $1-5
- **Custom:** Any amount

### Monitoring Frequency
- **Current:** Every 30 seconds
- **Adjustable:** Modify `await asyncio.sleep(30)` in code

### Supported Assets
All Ventuals synthetic assets:
- vntls:vANDRL (Anduril)
- vntls:vNLINK (Neuralink) 
- vntls:vPOLY (Polymarket)
- vntls:vSPACEX (SpaceX)
- vntls:vOAI (OpenAI)
- And 13+ more...

## Security Considerations

1. **Bot Token:** Keep secret, don't commit to git
2. **User Data:** Store minimal data (wallet address + threshold)
3. **Rate Limiting:** Built into python-telegram-bot
4. **Admin Commands:** Add user ID verification for `/list`

## Troubleshooting

### Bot Not Responding
- Check bot token is correct
- Verify internet connection
- Check bot is running (no errors in logs)

### No Alerts Received
- Verify wallet address is correct
- Check if positions exist (use `/status`)
- Ensure alert threshold is reasonable

### API Errors
- Check Hyperliquid API status
- Verify wallet address format
- Check network connectivity

## Advanced Features

### Custom Notifications
Modify `send_liquidation_alert()` to customize message format.

### Multiple Wallets
Extend to support multiple wallets per user:
```python
/start wallet1,wallet2,wallet3
```

### Price Alerts
Add price-based alerts:
```python
/price vntls:vPOLY > 10.5
```

### Portfolio Tracking
Add total portfolio value and PnL tracking.

## Support

For issues or feature requests:
1. Check logs for error messages
2. Verify API connectivity
3. Test with known working wallet
4. Check Telegram bot permissions

## License

MIT License - feel free to modify and distribute!
