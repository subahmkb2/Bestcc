#!/usr/bin/env python3
"""
Professional Multi-Gateway Credit Card Testing Bot with Telegram Integration
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
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("cc_checker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- CONFIGURATION ---
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
    
    def parse_card_input(self, card_input: str) -> CardInfo:
        """Parse card input and return CardInfo object"""
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
        
        return card_info
    
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
        card_info = self.parse_card_input(card_input)
        
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
    
    async def check_single_gateway(self, card_input: str, gateway_type: GatewayType) -> Dict:
        """Check card against a single gateway"""
        card_info = self.parse_card_input(card_input)
        
        gateway_methods = {
            GatewayType.STRIPE: self.check_stripe_gateway,
            GatewayType.BRAINTREE: self.check_braintree_gateway,
            GatewayType.AUTHORIZE_NET: self.check_authorize_net_gateway,
            GatewayType.PAYPAL: self.check_paypal_gateway,
            GatewayType.SQUARE: self.check_square_gateway
        }
        
        result = await gateway_methods[gateway_type](card_info)
        
        return {
            "card_info": card_info,
            "result": result
        }
    
    def format_single_result(self, results: Dict) -> str:
        """Format single gateway result"""
        card = results["card_info"]
        result = results["result"]
        
        status_icon = "✅" if result.approved else "❌"
        status_text = "APPROVED" if result.approved else "DECLINED"
        
        output = [
            f"🔍 <b>SINGLE GATEWAY CHECK - {result.gateway.value.upper()}</b>",
            "",
            f"💳 <b>Card:</b> <code>{card.number[:6]}XXXXXX{card.number[-4:]}</code>",
            f"🏦 <b>Brand:</b> {card.brand}",
            f"📊 <b>Bank:</b> {card.bank}",
            f"🌍 <b>Country:</b> {card.country} {card.emoji}",
            f"📅 <b>Expiry:</b> {card.month}/{card.year}",
            f"🔐 <b>CVV:</b> {card.cvv}",
            "",
            f"<b>RESULT:</b> {status_icon} {status_text}",
            f"<b>Message:</b> {result.message}",
            f"<b>Response Time:</b> {result.response_time:.2f}s"
        ]
        
        if not result.approved and result.decline_reason:
            output.append(f"<b>Reason:</b> {result.decline_reason}")
        
        output.extend([
            "",
            "⚠️ <i>For educational purposes only</i>"
        ])
        
        return "\n".join(output)
    
    def format_results(self, results: Dict) -> str:
        """Format results in a readable way for Telegram"""
        card = results["card_info"]
        
        output = [
            "🔍 <b>MULTI-GATEWAY CHECK RESULTS</b>",
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
        "🤖 <b>Professional Multi-Gateway CC Checker Bot</b>\n\n"
        "📝 <b>Card Format:</b>\n"
        "<code>1234567890123456|MM|YYYY|CVC</code>\n\n"
        "⚡ <b>Available Commands:</b>\n"
        "/start - Start the bot\n"
        "/help - Show detailed help\n"
        "/all - Check all gateways\n"
        "/st - Check Stripe gateway\n"
        "/chk - Check Braintree gateway\n"
        "/pp - Check PayPal gateway\n"
        "/an - Check Authorize.net gateway\n"
        "/sq - Check Square gateway\n\n"
        "⚠️ <b>DISCLAIMER:</b>\n"
        "<i>For educational and authorized testing purposes ONLY.</i>"
    )
    await update.message.reply_html(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message when the /help command is issued."""
    help_message = (
        "📖 <b>Professional CC Checker Bot - Help Guide</b>\n\n"
        "💳 <b>Card Format:</b>\n"
        "<code>1234567890123456|MM|YYYY|CVC</code>\n\n"
        "🔍 <b>Example:</b>\n"
        "<code>4111111111111111|12|2025|123</code>\n\n"
        "⚡ <b>Available Commands:</b>\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/all - Check against all gateways\n"
        "/st - Check Stripe gateway only\n"
        "/chk - Check Braintree gateway only\n"
        "/pp - Check PayPal gateway only\n"
        "/an - Check Authorize.net gateway only\n"
        "/sq - Check Square gateway only\n\n"
        "🛡️ <b>Supported Gateways:</b>\n"
        "• Stripe - Payment processing\n"
        "• Braintree - PayPal's gateway\n"
        "• Authorize.net - Popular US gateway\n"
        "• PayPal - Digital payments\n"
        "• Square - Mobile payments\n\n"
        "⏱️ <b>Features:</b>\n"
        "• Real-time response simulation\n"
        "• BIN information lookup\n"
        "• Card validation (Luhn algorithm)\n"
        "• Professional reporting\n"
        "• Multi-gateway testing\n\n"
        "⚠️ <b>Important:</b>\n"
        "<i>This bot is for EDUCATIONAL purposes only. Always ensure you have proper authorization before testing any payment systems.</i>"
    )
    await update.message.reply_html(help_message)

async def send_processing_message(update: Update, gateway: str) -> int:
    """Send processing message and return message ID"""
    processing_message = await update.message.reply_text(
        f"⏳ <b>Processing {gateway} gateway check...</b>\n"
        "<i>Simulating real payment processing...</i>",
        parse_mode=ParseMode.HTML
    )
    return processing_message.message_id

async def all_gateways_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check card against all gateways"""
    if not context.args:
        await update.message.reply_html(
            "❌ <b>Usage:</b> <code>/all 1234567890123456|MM|YYYY|CVC</code>\n\n"
            "🔍 <b>Example:</b>\n"
            "<code>/all 4111111111111111|12|2025|123</code>"
        )
        return
    
    card_input = " ".join(context.args)
    checker = CCCheckerBot()
    
    message_id = await send_processing_message(update, "all")
    
    try:
        results = await checker.check_all_gateways(card_input)
        report = checker.format_results(results)
        
        await context.bot.edit_message_text(
            text=report,
            chat_id=update.effective_chat.id,
            message_id=message_id,
            parse_mode=ParseMode.HTML
        )
        
    except ValueError as e:
        error_message = f"❌ <b>Error:</b> {str(e)}"
        await context.bot.edit_message_text(
            text=error_message,
            chat_id=update.effective_chat.id,
            message_id=message_id,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        error_message = f"💥 <b>Unexpected error:</b> {str(e)}"
        await context.bot.edit_message_text(
            text=error_message,
            chat_id=update.effective_chat.id,
            message_id=message_id,
            parse_mode=ParseMode.HTML
        )

async def stripe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check card against Stripe gateway"""
    await handle_single_gateway(update, context, GatewayType.STRIPE, "stripe")

async def braintree_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check card against Braintree gateway"""
    await handle_single_gateway(update, context, GatewayType.BRAINTREE, "braintree")

async def paypal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check card against PayPal gateway"""
    await handle_single_gateway(update, context, GatewayType.PAYPAL, "paypal")

async def authorize_net_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check card against Authorize.net gateway"""
    await handle_single_gateway(update, context, GatewayType.AUTHORIZE_NET, "authorize.net")

async def square_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check card against Square gateway"""
    await handle_single_gateway(update, context, GatewayType.SQUARE, "square")

async def handle_single_gateway(update: Update, context: ContextTypes.DEFAULT_TYPE, gateway_type: GatewayType, gateway_name: str) -> None:
    """Handle single gateway check"""
    if not context.args:
        await update.message.reply_html(
            f"❌ <b>Usage:</b> <code>/{gateway_type.value} 1234567890123456|MM|YYYY|CVC</code>\n\n"
            "🔍 <b>Example:</b>\n"
            f"<code>/{gateway_type.value} 4111111111111111|12|2025|123</code>"
        )
        return
    
    card_input = " ".join(context.args)
    checker = CCCheckerBot()
    
    message_id = await send_processing_message(update, gateway_name)
    
    try:
        results = await checker.check_single_gateway(card_input, gateway_type)
        report = checker.format_single_result(results)
        
        await context.bot.edit_message_text(
            text=report,
            chat_id=update.effective_chat.id,
            message_id=message_id,
            parse_mode=ParseMode.HTML
        )
        
    except ValueError as e:
        error_message = f"❌ <b>Error:</b> {str(e)}"
        await context.bot.edit_message_text(
            text=error_message,
            chat_id=update.effective_chat.id,
            message_id=message_id,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        error_message = f"💥 <b>Unexpected error:</b> {str(e)}"
        await context.bot.edit_message_text(
            text=error_message,
            chat_id=update.effective_chat.id,
            message_id=message_id,
            parse_mode=ParseMode.HTML
        )

async def handle_card_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process card details sent as regular message (default to all gateways)"""
    card_input = update.message.text.strip()
    checker = CCCheckerBot()
    
    message_id = await send_processing_message(update, "all")
    
    try:
        results = await checker.check_all_gateways(card_input)
        report = checker.format_results(results)
        
        await context.bot.edit_message_text(
            text=report,
            chat_id=update.effective_chat.id,
            message_id=message_id,
            parse_mode=ParseMode.HTML
        )
        
    except ValueError as e:
        error_message = f"❌ <b>Error:</b> {str(e)}\n\n💡 <b>Tip:</b> Use commands for specific gateway checks:\n/all, /st, /chk, /pp, /an, /sq"
        await context.bot.edit_message_text(
            text=error_message,
            chat_id=update.effective_chat.id,
            message_id=message_id,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        error_message = f"💥 <b>Unexpected error:</b> {str(e)}"
        await context.bot.edit_message_text(
            text=error_message,
            chat_id=update.effective_chat.id,
            message_id=message_id,
            parse_mode=ParseMode.HTML
        )

def main() -> None:
    """Start the Telegram bot."""
    if not BOT_TOKEN or BOT_TOKEN == "8043566736:AAEU1JLdxOnFZjQDM06_MODIoIZEf7ZmhIK":
        print("❌ ERROR: Bot token not configured!")
        print("Please replace the BOT_TOKEN variable with your actual Telegram bot token.")
        return
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("all", all_gateways_command))
    application.add_handler(CommandHandler("st", stripe_command))
    application.add_handler(CommandHandler("chk", braintree_command))
    application.add_handler(CommandHandler("pp", paypal_command))
    application.add_handler(CommandHandler("an", authorize_net_command))
    application.add_handler(CommandHandler("sq", square_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_card_message))
    
    # Start the bot
    print("🤖 Professional CC Checker Bot is starting...")
    print("✅ Bot token is configured")
    print("📱 Bot is now running...")
    print("⚡ Available commands: /start, /help, /all, /st, /chk, /pp, /an, /sq")
    print("\n⚠️  FOR EDUCATIONAL PURPOSES ONLY")
    
    application.run_polling()

if __name__ == "__main__":
    main()