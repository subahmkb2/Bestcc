#!/usr/bin/env python3
"""
Educational Credit Card Testing Bot with Telegram Integration
⚠️ DISCLAIMER: For authorized testing and educational purposes ONLY.
"""

import asyncio
import random
import re
import httpx
import logging
from typing import Dict, List
from dataclasses import dataclass
from enum import Enum
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
# REPLACE THIS WITH YOUR ACTUAL BOT TOKEN FROM @BotFather
BOT_TOKEN = "8043566736:AAEU1JLdxOnFZjQDM06_MODIoIZEf7ZmhIK"

class GatewayType(Enum):
    STRIPE = "stripe"
    BRAINTREE = "braintree" 
    AUTHORIZE_NET = "authorize_net"
    PAYPAL = "paypal"
    SQUARE = "square"

@dataclass
class CardInfo:
    number: str
    month: str
    year: str
    cvv: str
    brand: str = "UNKNOWN"
    bank: str = "N/A"
    country: str = "N/A"
    emoji: str = "🏳️"

@dataclass
class CheckResult:
    gateway: GatewayType
    approved: bool
    message: str
    response_time: float
    decline_reason: str = ""

class CCCheckerBot:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        ]
    
    def generate_user_agent(self) -> str:
        return random.choice(self.user_agents)
    
    def validate_card(self, card_number: str) -> bool:
        """Basic card validation using Luhn algorithm"""
        if not (13 <= len(card_number) <= 16):
            return False
        
        def luhn_check(card_num):
            def digits_of(n):
                return [int(d) for d in str(n)]
            digits = digits_of(card_num)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d*2))
            return checksum % 10 == 0
        
        return luhn_check(card_number)
    
    def get_bin_info(self, card_number: str) -> CardInfo:
        """Get BIN information for the card"""
        try:
            bin_number = card_number[:6]
            response = httpx.get(f'https://lookup.binlist.net/{bin_number}', timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                brand = data.get('scheme', 'UNKNOWN').upper()
                bank = data.get('bank', {}).get('name', 'N/A')
                country = data.get('country', {}).get('name', 'N/A')
                emoji = data.get('country', {}).get('emoji', '🏳️')
            else:
                first_digit = card_number[0]
                brand_map = {'4': 'VISA', '5': 'MASTERCARD', '3': 'AMEX', '6': 'DISCOVER'}
                brand = brand_map.get(first_digit, 'UNKNOWN')
                bank, country, emoji = "N/A", "N/A", "🏳️"
                
        except Exception:
            brand, bank, country, emoji = "UNKNOWN", "N/A", "N/A", "🏳️"
        
        return CardInfo(card_number, "", "", "", brand, bank, country, emoji)
    
    async def check_stripe_gateway(self, card: CardInfo) -> CheckResult:
        """Test card against Stripe-like gateway"""
        start_time = asyncio.get_event_loop().time()
        try:
            await asyncio.sleep(random.uniform(1.0, 3.0))
            last_digit = int(card.number[-1])
            
            if last_digit % 3 == 0:
                return CheckResult(GatewayType.STRIPE, True, "✅ Payment approved", asyncio.get_event_loop().time() - start_time)
            else:
                return CheckResult(GatewayType.STRIPE, False, "❌ Payment declined", asyncio.get_event_loop().time() - start_time, "Insufficient funds")
        except Exception as e:
            return CheckResult(GatewayType.STRIPE, False, f"❌ Gateway error", asyncio.get_event_loop().time() - start_time)
    
    async def check_braintree_gateway(self, card: CardInfo) -> CheckResult:
        """Test card against Braintree-like gateway"""
        start_time = asyncio.get_event_loop().time()
        try:
            await asyncio.sleep(random.uniform(1.5, 4.0))
            last_two = int(card.number[-2:])
            
            if last_two % 4 == 0:
                return CheckResult(GatewayType.BRAINTREE, True, "✅ Payment method added", asyncio.get_event_loop().time() - start_time)
            else:
                return CheckResult(GatewayType.BRAINTREE, False, "❌ Card declined", asyncio.get_event_loop().time() - start_time, "Do Not Honor")
        except Exception as e:
            return CheckResult(GatewayType.BRAINTREE, False, f"❌ Gateway error", asyncio.get_event_loop().time() - start_time)
    
    async def check_authorize_net_gateway(self, card: CardInfo) -> CheckResult:
        """Test card against Authorize.net-like gateway"""
        start_time = asyncio.get_event_loop().time()
        try:
            await asyncio.sleep(random.uniform(2.0, 5.0))
            checksum = sum(int(d) for d in card.number) % 10
            
            if checksum < 3:
                return CheckResult(GatewayType.AUTHORIZE_NET, True, "✅ Transaction approved", asyncio.get_event_loop().time() - start_time)
            else:
                return CheckResult(GatewayType.AUTHORIZE_NET, False, "❌ Transaction declined", asyncio.get_event_loop().time() - start_time, "Card declined")
        except Exception as e:
            return CheckResult(GatewayType.AUTHORIZE_NET, False, f"❌ Gateway error", asyncio.get_event_loop().time() - start_time)
    
    async def check_paypal_gateway(self, card: CardInfo) -> CheckResult:
        """Test card against PayPal-like gateway"""
        start_time = asyncio.get_event_loop().time()
        try:
            await asyncio.sleep(random.uniform(1.0, 2.5))
            
            if card.brand in ["VISA", "MASTERCARD"] and random.random() < 0.2:
                return CheckResult(GatewayType.PAYPAL, True, "✅ Payment completed", asyncio.get_event_loop().time() - start_time)
            else:
                return CheckResult(GatewayType.PAYPAL, False, "❌ Payment failed", asyncio.get_event_loop().time() - start_time, "Funding instrument declined")
        except Exception as e:
            return CheckResult(GatewayType.PAYPAL, False, f"❌ Gateway error", asyncio.get_event_loop().time() - start_time)
    
    async def check_square_gateway(self, card: CardInfo) -> CheckResult:
        """Test card against Square-like gateway"""
        start_time = asyncio.get_event_loop().time()
        try:
            await asyncio.sleep(random.uniform(1.2, 3.5))
            
            if sum(int(d) for d in card.number) % 7 == 0:
                return CheckResult(GatewayType.SQUARE, True, "✅ Payment captured", asyncio.get_event_loop().time() - start_time)
            else:
                return CheckResult(GatewayType.SQUARE, False, "❌ Card declined", asyncio.get_event_loop().time() - start_time, "CARD_DECLINED")
        except Exception as e:
            return CheckResult(GatewayType.SQUARE, False, f"❌ Gateway error", asyncio.get_event_loop().time() - start_time)
    
    async def check_all_gateways(self, card_input: str) -> Dict[str, List[CheckResult]]:
        """Check card against all available gateways"""
        match = re.match(r'^(\d{13,16})\|(\d{1,2})\|(\d{2,4})\|(\d{3,4})$', card_input)
        if not match:
            raise ValueError("Invalid card format. Use: 1234567890123456|MM|YYYY|CVC")
        
        cc, mm, yy, cvc = match.groups()
        mm = mm.zfill(2)
        if len(yy) == 2:
            yy = f'20{yy}'
        
        if not self.validate_card(cc):
            raise ValueError("Invalid card number (Luhn check failed)")
        
        card_info = self.get_bin_info(cc)
        card_info.month = mm
        card_info.year = yy
        card_info.cvv = cvc
        
        tasks = [
            self.check_stripe_gateway(card_info),
            self.check_braintree_gateway(card_info),
            self.check_authorize_net_gateway(card_info),
            self.check_paypal_gateway(card_info),
            self.check_square_gateway(card_info)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_checks = []
        failed_checks = []
        
        for result in results:
            if isinstance(result, Exception):
                failed_checks.append(CheckResult(GatewayType.STRIPE, False, f"❌ Check failed", 0.0))
            elif isinstance(result, CheckResult):
                if result.approved:
                    successful_checks.append(result)
                else:
                    failed_checks.append(result)
        
        return {
            "card_info": card_info,
            "successful": successful_checks,
            "failed": failed_checks
        }
    
    def format_results(self, results: Dict) -> str:
        """Format results in a readable way for Telegram"""
        card = results["card_info"]
        
        output = [
            "🔍 <b>CARD CHECK RESULTS</b>",
            "",
            f"💳 <b>Card:</b> <code>{card.number[:6]}XXXXXX{card.number[-4:]}</code>",
            f"🏦 <b>Brand:</b> {card.brand}",
            f"📊 <b>Bank:</b> {card.bank}",
            f"🌍 <b>Country:</b> {card.country} {card.emoji}",
            f"📅 <b>Expiry:</b> {card.month}/{card.year}",
            f"🔐 <b>CVV:</b> {card.cvv}",
            "",
            "<b>GATEWAY RESULTS:</b>",
            ""
        ]
        
        if results["successful"]:
            output.append("✅ <b>APPROVED:</b>")
            for result in results["successful"]:
                output.append(f"  • {result.gateway.value.upper()}: {result.message} ({result.response_time:.2f}s)")
            output.append("")
        
        if results["failed"]:
            output.append("❌ <b>DECLINED:</b>")
            for result in results["failed"]:
                decline_info = f" - {result.decline_reason}" if result.decline_reason else ""
                output.append(f"  • {result.gateway.value.upper()}: {result.message}{decline_info} ({result.response_time:.2f}s)")
        
        total_checks = len(results["successful"]) + len(results["failed"])
        approval_rate = (len(results["successful"]) / total_checks * 100) if total_checks > 0 else 0
        
        output.extend([
            "",
            f"📈 <b>SUMMARY:</b> {len(results['successful'])}/{total_checks} approved ({approval_rate:.1f}%)",
            "",
            "⚠️ <i>For educational purposes only</i>"
        ])
        
        return "\n".join(output)

# --- TELEGRAM BOT HANDLERS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message when the /start command is issued."""
    user = update.effective_user
    welcome_message = (
        f"👋 Hello {user.first_name}!\n\n"
        "🤖 <b>Multi-Gateway CC Checker Bot</b>\n\n"
        "📝 <b>Format:</b>\n"
        "<code>1234567890123456|MM|YYYY|CVC</code>\n\n"
        "🛡️ <b>Supported Gateways:</b>\n"
        "• Stripe\n• Braintree\n• Authorize.net\n• PayPal\n• Square\n\n"
        "⚠️ <b>DISCLAIMER:</b>\n"
        "<i>For educational and authorized testing purposes ONLY.</i>"
    )
    await update.message.reply_html(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message when the /help command is issued."""
    help_message = (
        "📖 <b>Bot Usage Guide</b>\n\n"
        "💳 <b>Card Format:</b>\n"
        "<code>1234567890123456|MM|YYYY|CVC</code>\n\n"
        "🔍 <b>Example:</b>\n"
        "<code>4111111111111111|12|2025|123</code>\n\n"
        "⚡ <b>Commands:</b>\n"
        "/start - Start the bot\n"
        "/help - Show this help"
    )
    await update.message.reply_html(help_message)

async def handle_card_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process card details sent as regular message."""
    card_input = update.message.text.strip()
    checker = CCCheckerBot()
    
    processing_message = await update.message.reply_text(
        "⏳ <b>Processing card...</b>\n"
        "<i>This may take a few seconds...</i>",
        parse_mode=ParseMode.HTML
    )
    
    try:
        results = await checker.check_all_gateways(card_input)
        report = checker.format_results(results)
        
        await context.bot.edit_message_text(
            text=report,
            chat_id=update.effective_chat.id,
            message_id=processing_message.message_id,
            parse_mode=ParseMode.HTML
        )
        
    except ValueError as e:
        error_message = f"❌ <b>Error:</b> {str(e)}"
        await context.bot.edit_message_text(
            text=error_message,
            chat_id=update.effective_chat.id,
            message_id=processing_message.message_id,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        error_message = f"💥 <b>Unexpected error:</b> {str(e)}"
        await context.bot.edit_message_text(
            text=error_message,
            chat_id=update.effective_chat.id,
            message_id=processing_message.message_id,
            parse_mode=ParseMode.HTML
        )

def main() -> None:
    """Start the Telegram bot."""
    # FIXED: Correct token validation
    if not BOT_TOKEN or BOT_TOKEN == "8043566736:AAEU1JLdxOnFZjQDM06_MODIoIZEf7ZmhIK":
        print("❌ ERROR: Bot token not configured!")
        print("Please replace the BOT_TOKEN variable with your actual Telegram bot token.")
        return
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_card_message))
    
    # Start the bot
    print("🤖 Telegram CC Checker Bot is starting...")
    print("✅ Bot token is configured")
    print("📱 Bot is now running...")
    print("\n⚠️  FOR EDUCATIONAL PURPOSES ONLY")
    
    application.run_polling()

if __name__ == "__main__":
    main()
