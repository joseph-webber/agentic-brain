#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Multilingual Customer Support Bot
=================================

Customer support bot with:
- Automatic language detection
- Response in customer's language
- Translation of internal knowledge base
- Cultural adaptation of responses
- Support for English, Spanish, French, German, Japanese, Chinese

Demo: International electronics retailer
"""

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Callable, Any
from collections import defaultdict


class Language(Enum):
    """Supported languages."""

    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    JAPANESE = "ja"
    CHINESE = "zh"

    @property
    def display_name(self) -> str:
        names = {
            "en": "English",
            "es": "Español",
            "fr": "Français",
            "de": "Deutsch",
            "ja": "日本語",
            "zh": "中文",
        }
        return names.get(self.value, self.value)

    @property
    def native_greeting(self) -> str:
        greetings = {
            "en": "Hello",
            "es": "Hola",
            "fr": "Bonjour",
            "de": "Hallo",
            "ja": "こんにちは",
            "zh": "你好",
        }
        return greetings.get(self.value, "Hello")


class CulturalContext(Enum):
    """Cultural context for adaptation."""

    WESTERN_INFORMAL = "western_informal"
    WESTERN_FORMAL = "western_formal"
    ASIAN_FORMAL = "asian_formal"
    LATIN_WARM = "latin_warm"


@dataclass
class TranslationEntry:
    """A translation entry in the knowledge base."""

    key: str
    category: str
    translations: dict[str, str]  # language_code -> text
    variables: list[str] = field(default_factory=list)
    cultural_notes: dict[str, str] = field(default_factory=dict)

    def get(self, language: Language, **kwargs) -> str:
        """Get translation with variable substitution."""
        text = self.translations.get(language.value, self.translations.get("en", ""))

        # Substitute variables
        for var in self.variables:
            if var in kwargs:
                text = text.replace(f"{{{var}}}", str(kwargs[var]))

        return text


@dataclass
class CustomerProfile:
    """Customer profile with language preferences."""

    id: str
    name: str
    email: str
    preferred_language: Language = Language.ENGLISH
    detected_language: Optional[Language] = None
    country: Optional[str] = None
    formality_preference: str = "formal"
    timezone: Optional[str] = None

    @property
    def effective_language(self) -> Language:
        """Get the effective language to use."""
        return self.detected_language or self.preferred_language


@dataclass
class Conversation:
    """Multilingual conversation."""

    id: str
    customer: CustomerProfile
    messages: list = field(default_factory=list)
    detected_languages: list = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

    @property
    def primary_language(self) -> Language:
        """Determine primary language from conversation."""
        if not self.detected_languages:
            return self.customer.effective_language

        # Count language occurrences
        counts = defaultdict(int)
        for lang in self.detected_languages:
            counts[lang.value] += 1

        # Return most common
        most_common = max(counts.items(), key=lambda x: x[1])
        return Language(most_common[0])


class LanguageDetector:
    """Detects language from text."""

    def __init__(self):
        # Character patterns for detection
        self.patterns = {
            Language.JAPANESE: re.compile(
                r"[\u3040-\u309F\u30A0-\u30FF]"
            ),  # Hiragana + Katakana
            Language.CHINESE: re.compile(r"[\u4E00-\u9FFF]"),  # CJK unified
            Language.GERMAN: re.compile(r"[äöüßÄÖÜ]"),
            Language.FRENCH: re.compile(r"[àâçéèêëîïôùûüÿœæ]", re.IGNORECASE),
            Language.SPANISH: re.compile(r"[áéíóúüñ¿¡]", re.IGNORECASE),
        }

        # Common word patterns
        self.word_patterns = {
            Language.ENGLISH: [
                "the",
                "is",
                "are",
                "what",
                "how",
                "can",
                "please",
                "thank",
                "hello",
                "hi",
            ],
            Language.SPANISH: [
                "el",
                "la",
                "que",
                "como",
                "donde",
                "por",
                "favor",
                "gracias",
                "hola",
                "quiero",
            ],
            Language.FRENCH: [
                "le",
                "la",
                "que",
                "comment",
                "où",
                "merci",
                "bonjour",
                "voulez",
                "pour",
                "est",
            ],
            Language.GERMAN: [
                "der",
                "die",
                "das",
                "wie",
                "was",
                "bitte",
                "danke",
                "haben",
                "können",
                "guten",
            ],
            Language.JAPANESE: [
                "です",
                "ます",
                "ください",
                "ありがとう",
                "すみません",
                "はい",
                "いいえ",
            ],
            Language.CHINESE: [
                "是",
                "的",
                "我",
                "你",
                "吗",
                "什么",
                "怎么",
                "谢谢",
                "请",
            ],
        }

    def detect(self, text: str) -> tuple[Language, float]:
        """Detect language with confidence score.

        Returns:
            Tuple of (detected_language, confidence)
        """
        if not text or len(text.strip()) < 2:
            return Language.ENGLISH, 0.0

        scores = defaultdict(float)

        # Check character patterns
        for lang, pattern in self.patterns.items():
            matches = len(pattern.findall(text))
            if matches > 0:
                scores[lang] += matches * 2  # Weight character matches higher

        # Check word patterns
        text_lower = text.lower()
        for lang, words in self.word_patterns.items():
            for word in words:
                if word in text_lower:
                    scores[lang] += 1

        if not scores:
            # Default to English if no patterns match
            return Language.ENGLISH, 0.5

        # Find best match
        best_lang = max(scores.items(), key=lambda x: x[1])

        # Calculate confidence (normalized)
        total_score = sum(scores.values())
        confidence = best_lang[1] / total_score if total_score > 0 else 0.5

        return best_lang[0], min(confidence, 0.95)

    def detect_with_fallback(self, text: str, fallback: Language) -> Language:
        """Detect language with fallback for low confidence."""
        lang, confidence = self.detect(text)

        if confidence < 0.4:
            return fallback
        return lang


class TranslationService:
    """Handles translation of content."""

    def __init__(self):
        self.cache: dict[str, str] = {}
        self.translations_count = 0

    def translate(
        self,
        text: str,
        source: Language,
        target: Language,
        context: Optional[str] = None,
    ) -> str:
        """Translate text between languages.

        Note: In production, this would call a translation API.
        For demo, we use a simplified mock translation.
        """
        if source == target:
            return text

        # Check cache
        cache_key = f"{source.value}:{target.value}:{hash(text)}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Mock translation (in production, call API like Google Translate)
        translated = self._mock_translate(text, source, target)

        self.cache[cache_key] = translated
        self.translations_count += 1

        return translated

    def _mock_translate(self, text: str, source: Language, target: Language) -> str:
        """Mock translation for demo purposes."""
        # Common phrase translations for demo
        phrase_translations = {
            ("en", "es"): {
                "Hello": "Hola",
                "Thank you": "Gracias",
                "How can I help you?": "¿Cómo puedo ayudarle?",
                "Please wait": "Por favor espere",
                "Your order": "Su pedido",
            },
            ("en", "fr"): {
                "Hello": "Bonjour",
                "Thank you": "Merci",
                "How can I help you?": "Comment puis-je vous aider?",
                "Please wait": "Veuillez patienter",
                "Your order": "Votre commande",
            },
            ("en", "de"): {
                "Hello": "Hallo",
                "Thank you": "Danke",
                "How can I help you?": "Wie kann ich Ihnen helfen?",
                "Please wait": "Bitte warten Sie",
                "Your order": "Ihre Bestellung",
            },
            ("en", "ja"): {
                "Hello": "こんにちは",
                "Thank you": "ありがとうございます",
                "How can I help you?": "どのようにお手伝いできますか？",
                "Please wait": "お待ちください",
                "Your order": "ご注文",
            },
            ("en", "zh"): {
                "Hello": "你好",
                "Thank you": "谢谢",
                "How can I help you?": "有什么可以帮您的吗？",
                "Please wait": "请稍等",
                "Your order": "您的订单",
            },
        }

        key = (source.value, target.value)
        if key in phrase_translations:
            for eng, trans in phrase_translations[key].items():
                text = text.replace(eng, trans)

        return text


class KnowledgeBase:
    """Multilingual knowledge base."""

    def __init__(self):
        self.entries: dict[str, TranslationEntry] = {}
        self._load_default_entries()

    def _load_default_entries(self):
        """Load default multilingual entries."""
        entries = [
            # Greetings
            TranslationEntry(
                key="greeting",
                category="general",
                translations={
                    "en": "Hello! Welcome to TechWorld. How can I help you today?",
                    "es": "¡Hola! Bienvenido a TechWorld. ¿En qué puedo ayudarle hoy?",
                    "fr": "Bonjour! Bienvenue chez TechWorld. Comment puis-je vous aider aujourd'hui?",
                    "de": "Hallo! Willkommen bei TechWorld. Wie kann ich Ihnen heute helfen?",
                    "ja": "こんにちは！TechWorldへようこそ。本日はどのようなご用件でしょうか？",
                    "zh": "您好！欢迎来到TechWorld。今天有什么可以帮您的吗？",
                },
            ),
            TranslationEntry(
                key="greeting_returning",
                category="general",
                translations={
                    "en": "Welcome back, {name}! Great to see you again. How can I assist you?",
                    "es": "¡Bienvenido de nuevo, {name}! Encantado de verle otra vez. ¿Cómo puedo ayudarle?",
                    "fr": "Bon retour, {name}! Ravi de vous revoir. Comment puis-je vous aider?",
                    "de": "Willkommen zurück, {name}! Schön Sie wiederzusehen. Wie kann ich Ihnen helfen?",
                    "ja": "{name}様、お帰りなさいませ！またお会いできて嬉しいです。ご用件をお聞かせください。",
                    "zh": "欢迎回来，{name}！很高兴再次见到您。有什么可以帮您的吗？",
                },
                variables=["name"],
            ),
            # Shipping
            TranslationEntry(
                key="shipping_info",
                category="shipping",
                translations={
                    "en": "We offer standard shipping (5-7 days, free over $50) and express shipping (2-3 days, $14.99). International shipping is available to select countries.",
                    "es": "Ofrecemos envío estándar (5-7 días, gratis en pedidos superiores a 50€) y envío exprés (2-3 días, 14,99€). Envío internacional disponible a países seleccionados.",
                    "fr": "Nous proposons la livraison standard (5-7 jours, gratuite à partir de 50€) et express (2-3 jours, 14,99€). Livraison internationale disponible dans certains pays.",
                    "de": "Wir bieten Standardversand (5-7 Tage, kostenlos ab 50€) und Expressversand (2-3 Tage, 14,99€). Internationaler Versand in ausgewählte Länder verfügbar.",
                    "ja": "通常配送（5-7日、5000円以上で送料無料）と速達配送（2-3日、1499円）をご用意しております。一部の国への国際配送も承っております。",
                    "zh": "我们提供标准配送（5-7天，满50美元免运费）和快递配送（2-3天，14.99美元）。部分国家可享受国际配送服务。",
                },
            ),
            TranslationEntry(
                key="shipping_status",
                category="shipping",
                translations={
                    "en": "Your order {order_id} was shipped on {ship_date} and is expected to arrive by {delivery_date}. Track it here: {tracking_url}",
                    "es": "Su pedido {order_id} fue enviado el {ship_date} y se espera que llegue antes del {delivery_date}. Rastréelo aquí: {tracking_url}",
                    "fr": "Votre commande {order_id} a été expédiée le {ship_date} et devrait arriver avant le {delivery_date}. Suivez-la ici: {tracking_url}",
                    "de": "Ihre Bestellung {order_id} wurde am {ship_date} versandt und wird voraussichtlich bis zum {delivery_date} eintreffen. Verfolgen Sie sie hier: {tracking_url}",
                    "ja": "ご注文 {order_id} は {ship_date} に発送され、{delivery_date} までにお届け予定です。追跡はこちら: {tracking_url}",
                    "zh": "您的订单 {order_id} 已于 {ship_date} 发货，预计 {delivery_date} 前送达。点击此处追踪: {tracking_url}",
                },
                variables=["order_id", "ship_date", "delivery_date", "tracking_url"],
            ),
            # Returns
            TranslationEntry(
                key="return_policy",
                category="returns",
                translations={
                    "en": "We accept returns within 30 days of purchase. Items must be unused and in original packaging. Refunds are processed within 5-7 business days.",
                    "es": "Aceptamos devoluciones dentro de los 30 días de la compra. Los artículos deben estar sin usar y en su embalaje original. Los reembolsos se procesan en 5-7 días hábiles.",
                    "fr": "Nous acceptons les retours dans les 30 jours suivant l'achat. Les articles doivent être neufs et dans leur emballage d'origine. Les remboursements sont traités sous 5-7 jours ouvrés.",
                    "de": "Wir akzeptieren Rückgaben innerhalb von 30 Tagen nach dem Kauf. Artikel müssen unbenutzt und in der Originalverpackung sein. Rückerstattungen werden innerhalb von 5-7 Werktagen bearbeitet.",
                    "ja": "ご購入から30日以内の返品を承っております。商品は未使用で、元のパッケージに入っている必要があります。返金は5-7営業日以内に処理されます。",
                    "zh": "我们接受购买后30天内的退货。商品必须是未使用过的，并保留原包装。退款将在5-7个工作日内处理。",
                },
            ),
            TranslationEntry(
                key="return_initiated",
                category="returns",
                translations={
                    "en": "Your return for order {order_id} has been initiated. Please print the return label and ship the item within 14 days. Refund reference: {return_id}",
                    "es": "Se ha iniciado la devolución de su pedido {order_id}. Imprima la etiqueta de devolución y envíe el artículo en un plazo de 14 días. Referencia de reembolso: {return_id}",
                    "fr": "Votre retour pour la commande {order_id} a été initié. Veuillez imprimer l'étiquette de retour et expédier l'article dans les 14 jours. Référence de remboursement: {return_id}",
                    "de": "Ihre Rücksendung für Bestellung {order_id} wurde eingeleitet. Bitte drucken Sie das Rücksendeetikett aus und senden Sie den Artikel innerhalb von 14 Tagen zurück. Rückerstattungsreferenz: {return_id}",
                    "ja": "ご注文 {order_id} の返品手続きが開始されました。返品ラベルを印刷し、14日以内に商品をお送りください。返金参照番号: {return_id}",
                    "zh": "您的订单 {order_id} 退货已开始处理。请打印退货标签并在14天内寄回商品。退款参考号: {return_id}",
                },
                variables=["order_id", "return_id"],
            ),
            # Products
            TranslationEntry(
                key="product_monitors",
                category="products",
                translations={
                    "en": 'We offer monitors from 22" to 34" including gaming, professional, and ultrawide options. Popular brands include Samsung, LG, Dell, and ASUS.',
                    "es": 'Ofrecemos monitores de 22" a 34" incluyendo opciones para gaming, profesionales y ultrapanorámicos. Las marcas populares incluyen Samsung, LG, Dell y ASUS.',
                    "fr": 'Nous proposons des moniteurs de 22" à 34", y compris des options gaming, professionnelles et ultra-larges. Marques populaires: Samsung, LG, Dell et ASUS.',
                    "de": 'Wir bieten Monitore von 22" bis 34" an, einschließlich Gaming-, Profi- und Ultrawide-Optionen. Beliebte Marken: Samsung, LG, Dell und ASUS.',
                    "ja": "22インチから34インチまで、ゲーミング、プロフェッショナル、ウルトラワイドなど各種モニターを取り揃えております。人気ブランド：Samsung、LG、Dell、ASUS。",
                    "zh": "我们提供22英寸至34英寸的显示器，包括游戏、专业和超宽屏选项。热门品牌包括三星、LG、戴尔和华硕。",
                },
            ),
            TranslationEntry(
                key="product_keyboards",
                category="products",
                translations={
                    "en": "We carry mechanical, membrane, and wireless keyboards. Gaming keyboards feature RGB lighting and programmable keys. Office keyboards prioritize comfort and quiet operation.",
                    "es": "Tenemos teclados mecánicos, de membrana e inalámbricos. Los teclados gaming cuentan con iluminación RGB y teclas programables. Los teclados de oficina priorizan la comodidad y el funcionamiento silencioso.",
                    "fr": "Nous proposons des claviers mécaniques, à membrane et sans fil. Les claviers gaming offrent un éclairage RGB et des touches programmables. Les claviers de bureau privilégient le confort et le silence.",
                    "de": "Wir führen mechanische, Membran- und kabellose Tastaturen. Gaming-Tastaturen bieten RGB-Beleuchtung und programmierbare Tasten. Bürotastaturen priorisieren Komfort und leisen Betrieb.",
                    "ja": "メカニカル、メンブレン、ワイヤレスキーボードを取り揃えております。ゲーミングキーボードはRGBライティングとプログラマブルキーを搭載。オフィスキーボードは快適性と静音性を重視しています。",
                    "zh": "我们提供机械键盘、薄膜键盘和无线键盘。游戏键盘配备RGB灯光和可编程按键。办公键盘注重舒适性和静音操作。",
                },
            ),
            TranslationEntry(
                key="product_cables",
                category="products",
                translations={
                    "en": "We stock HDMI, DisplayPort, USB-C, and ethernet cables in various lengths from 3ft to 50ft. All cables are certified and come with a lifetime warranty.",
                    "es": "Tenemos cables HDMI, DisplayPort, USB-C y ethernet en varias longitudes desde 1m hasta 15m. Todos los cables están certificados y tienen garantía de por vida.",
                    "fr": "Nous proposons des câbles HDMI, DisplayPort, USB-C et ethernet de diverses longueurs de 1m à 15m. Tous les câbles sont certifiés et bénéficient d'une garantie à vie.",
                    "de": "Wir führen HDMI-, DisplayPort-, USB-C- und Ethernet-Kabel in verschiedenen Längen von 1m bis 15m. Alle Kabel sind zertifiziert und haben lebenslange Garantie.",
                    "ja": "HDMI、DisplayPort、USB-C、イーサネットケーブルを1mから15mまで各種取り揃えております。すべてのケーブルは認定品で、永久保証付きです。",
                    "zh": "我们提供1米至15米不同长度的HDMI、DisplayPort、USB-C和以太网线缆。所有线缆均经过认证，享有终身保修。",
                },
            ),
            # Support phrases
            TranslationEntry(
                key="apology",
                category="support",
                translations={
                    "en": "I apologize for the inconvenience. Let me help resolve this for you right away.",
                    "es": "Le pido disculpas por las molestias. Permítame ayudarle a resolver esto de inmediato.",
                    "fr": "Je m'excuse pour ce désagrément. Permettez-moi de vous aider à résoudre ce problème immédiatement.",
                    "de": "Ich entschuldige mich für die Unannehmlichkeiten. Lassen Sie mich Ihnen helfen, das sofort zu lösen.",
                    "ja": "ご不便をおかけして申し訳ございません。すぐに解決のお手伝いをさせていただきます。",
                    "zh": "给您带来不便，深表歉意。让我立即帮您解决这个问题。",
                },
                cultural_notes={
                    "ja": "Use more formal apologetic language",
                    "zh": "Maintain respectful but efficient tone",
                },
            ),
            TranslationEntry(
                key="transfer_human",
                category="support",
                translations={
                    "en": "I'll connect you with a specialist who can better assist you. Please hold for a moment.",
                    "es": "Le conectaré con un especialista que podrá ayudarle mejor. Por favor, espere un momento.",
                    "fr": "Je vais vous mettre en contact avec un spécialiste qui pourra mieux vous aider. Veuillez patienter un instant.",
                    "de": "Ich verbinde Sie mit einem Spezialisten, der Ihnen besser helfen kann. Bitte warten Sie einen Moment.",
                    "ja": "より適切にサポートできる専門スタッフにおつなぎいたします。少々お待ちください。",
                    "zh": "我将为您转接专业人员，他们能更好地为您服务。请稍等片刻。",
                },
            ),
            TranslationEntry(
                key="closing",
                category="general",
                translations={
                    "en": "Is there anything else I can help you with today?",
                    "es": "¿Hay algo más en lo que pueda ayudarle hoy?",
                    "fr": "Y a-t-il autre chose que je puisse faire pour vous aujourd'hui?",
                    "de": "Kann ich Ihnen heute noch mit etwas anderem helfen?",
                    "ja": "他にご質問はございますか？",
                    "zh": "今天还有其他可以帮您的吗？",
                },
            ),
            TranslationEntry(
                key="goodbye",
                category="general",
                translations={
                    "en": "Thank you for contacting TechWorld. Have a great day!",
                    "es": "Gracias por contactar TechWorld. ¡Que tenga un buen día!",
                    "fr": "Merci d'avoir contacté TechWorld. Bonne journée!",
                    "de": "Vielen Dank, dass Sie TechWorld kontaktiert haben. Einen schönen Tag noch!",
                    "ja": "TechWorldにお問い合わせいただきありがとうございます。良い一日をお過ごしください！",
                    "zh": "感谢您联系TechWorld。祝您愉快！",
                },
            ),
        ]

        for entry in entries:
            self.entries[entry.key] = entry

    def get(self, key: str, language: Language, **kwargs) -> Optional[str]:
        """Get translated content."""
        entry = self.entries.get(key)
        if not entry:
            return None
        return entry.get(language, **kwargs)

    def search(self, query: str, language: Language) -> list[TranslationEntry]:
        """Search knowledge base."""
        results = []
        query_lower = query.lower()

        for entry in self.entries.values():
            text = entry.translations.get(
                language.value, entry.translations.get("en", "")
            )
            if query_lower in text.lower():
                results.append(entry)

        return results


class CulturalAdapter:
    """Adapts responses for cultural context."""

    def __init__(self):
        self.culture_map = {
            Language.ENGLISH: CulturalContext.WESTERN_INFORMAL,
            Language.SPANISH: CulturalContext.LATIN_WARM,
            Language.FRENCH: CulturalContext.WESTERN_FORMAL,
            Language.GERMAN: CulturalContext.WESTERN_FORMAL,
            Language.JAPANESE: CulturalContext.ASIAN_FORMAL,
            Language.CHINESE: CulturalContext.ASIAN_FORMAL,
        }

        self.formality_adjustments = {
            CulturalContext.WESTERN_INFORMAL: {
                "greeting_style": "casual",
                "use_first_name": True,
                "emoji_allowed": True,
            },
            CulturalContext.WESTERN_FORMAL: {
                "greeting_style": "formal",
                "use_first_name": False,
                "emoji_allowed": False,
            },
            CulturalContext.ASIAN_FORMAL: {
                "greeting_style": "very_formal",
                "use_first_name": False,
                "emoji_allowed": False,
                "extra_politeness": True,
            },
            CulturalContext.LATIN_WARM: {
                "greeting_style": "warm",
                "use_first_name": True,
                "emoji_allowed": True,
                "extra_warmth": True,
            },
        }

    def get_context(self, language: Language) -> CulturalContext:
        """Get cultural context for language."""
        return self.culture_map.get(language, CulturalContext.WESTERN_INFORMAL)

    def adapt_response(
        self, text: str, language: Language, customer_name: Optional[str] = None
    ) -> str:
        """Adapt response for cultural context."""
        context = self.get_context(language)
        adjustments = self.formality_adjustments.get(context, {})

        # Name adaptation
        if customer_name and not adjustments.get("use_first_name", True):
            # Use full name or honorific
            if language == Language.JAPANESE:
                text = text.replace(customer_name, f"{customer_name}様")
            elif language == Language.CHINESE:
                text = text.replace(customer_name, f"{customer_name}先生/女士")
            elif language == Language.GERMAN:
                text = text.replace(customer_name, f"Herr/Frau {customer_name}")
            elif language == Language.FRENCH:
                text = text.replace(customer_name, f"M./Mme {customer_name}")

        # Remove emoji for formal contexts
        if not adjustments.get("emoji_allowed", True):
            text = re.sub(
                r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF]",
                "",
                text,
            )

        return text

    def get_time_greeting(self, language: Language, hour: int) -> str:
        """Get time-appropriate greeting."""
        greetings = {
            Language.ENGLISH: {
                "morning": "Good morning",
                "afternoon": "Good afternoon",
                "evening": "Good evening",
            },
            Language.SPANISH: {
                "morning": "Buenos días",
                "afternoon": "Buenas tardes",
                "evening": "Buenas noches",
            },
            Language.FRENCH: {
                "morning": "Bonjour",
                "afternoon": "Bonjour",
                "evening": "Bonsoir",
            },
            Language.GERMAN: {
                "morning": "Guten Morgen",
                "afternoon": "Guten Tag",
                "evening": "Guten Abend",
            },
            Language.JAPANESE: {
                "morning": "おはようございます",
                "afternoon": "こんにちは",
                "evening": "こんばんは",
            },
            Language.CHINESE: {
                "morning": "早上好",
                "afternoon": "下午好",
                "evening": "晚上好",
            },
        }

        if hour < 12:
            period = "morning"
        elif hour < 17:
            period = "afternoon"
        else:
            period = "evening"

        lang_greetings = greetings.get(language, greetings[Language.ENGLISH])
        return lang_greetings.get(period, "Hello")


class MultilingualBot:
    """Multilingual customer support bot."""

    def __init__(self, company_name: str = "TechWorld"):
        self.company_name = company_name
        self.language_detector = LanguageDetector()
        self.translator = TranslationService()
        self.knowledge_base = KnowledgeBase()
        self.cultural_adapter = CulturalAdapter()

        self.conversations: dict[str, Conversation] = {}
        self.customers: dict[str, CustomerProfile] = {}

        # Metrics
        self.metrics = {
            "total_conversations": 0,
            "messages_by_language": defaultdict(int),
            "language_switches": 0,
            "translations_performed": 0,
            "escalations": 0,
        }

        # Intent patterns by language
        self.intent_patterns = self._build_intent_patterns()

    def _build_intent_patterns(self) -> dict:
        """Build intent detection patterns for each language."""
        return {
            "shipping": {
                "en": ["shipping", "delivery", "track", "when will", "ship"],
                "es": ["envío", "entrega", "rastrear", "cuándo llegará"],
                "fr": ["livraison", "expédition", "suivre", "quand"],
                "de": ["versand", "lieferung", "verfolgen", "wann"],
                "ja": ["配送", "発送", "届く", "追跡"],
                "zh": ["配送", "发货", "快递", "跟踪"],
            },
            "returns": {
                "en": ["return", "refund", "exchange", "money back"],
                "es": ["devolución", "reembolso", "cambio", "devolver"],
                "fr": ["retour", "remboursement", "échanger", "rendre"],
                "de": ["rückgabe", "erstattung", "umtausch", "zurück"],
                "ja": ["返品", "返金", "交換", "払い戻し"],
                "zh": ["退货", "退款", "换货", "退回"],
            },
            "products": {
                "en": ["monitor", "keyboard", "cable", "product"],
                "es": ["monitor", "teclado", "cable", "producto"],
                "fr": ["moniteur", "clavier", "câble", "produit"],
                "de": ["monitor", "tastatur", "kabel", "produkt"],
                "ja": ["モニター", "キーボード", "ケーブル", "製品"],
                "zh": ["显示器", "键盘", "线缆", "产品"],
            },
        }

    def detect_intent(self, text: str, language: Language) -> Optional[str]:
        """Detect intent from message."""
        text_lower = text.lower()

        for intent, lang_patterns in self.intent_patterns.items():
            patterns = lang_patterns.get(language.value, lang_patterns.get("en", []))
            for pattern in patterns:
                if pattern.lower() in text_lower:
                    return intent

        return None

    async def start_conversation(self, customer: CustomerProfile) -> Conversation:
        """Start a new multilingual conversation."""
        conv = Conversation(
            id=f"conv_{int(time.time())}_{customer.id}", customer=customer
        )

        self.conversations[conv.id] = conv
        self.customers[customer.id] = customer
        self.metrics["total_conversations"] += 1

        # Send greeting in customer's preferred language
        greeting = self.knowledge_base.get("greeting", customer.effective_language)

        # Add time-appropriate greeting
        hour = datetime.now().hour
        time_greeting = self.cultural_adapter.get_time_greeting(
            customer.effective_language, hour
        )

        if greeting:
            full_greeting = f"{time_greeting}! {greeting}"
        else:
            full_greeting = f"{time_greeting}! Welcome to {self.company_name}."

        # Adapt for culture
        full_greeting = self.cultural_adapter.adapt_response(
            full_greeting, customer.effective_language, customer.name
        )

        conv.messages.append(
            {
                "sender": "bot",
                "content": full_greeting,
                "language": customer.effective_language.value,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return conv

    async def handle_message(self, conversation_id: str, message: str) -> dict:
        """Handle incoming customer message."""
        conv = self.conversations.get(conversation_id)
        if not conv:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Detect language
        detected_lang, confidence = self.language_detector.detect(message)
        conv.detected_languages.append(detected_lang)
        self.metrics["messages_by_language"][detected_lang.value] += 1

        # Check for language switch
        if (
            conv.customer.detected_language
            and detected_lang != conv.customer.detected_language
        ):
            self.metrics["language_switches"] += 1

        conv.customer.detected_language = detected_lang

        # Record message
        conv.messages.append(
            {
                "sender": "customer",
                "content": message,
                "language": detected_lang.value,
                "language_confidence": confidence,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Detect intent
        intent = self.detect_intent(message, detected_lang)

        # Generate response in detected language
        response_text = await self._generate_response(
            conv, message, detected_lang, intent
        )

        # Adapt for culture
        response_text = self.cultural_adapter.adapt_response(
            response_text, detected_lang, conv.customer.name
        )

        # Record response
        conv.messages.append(
            {
                "sender": "bot",
                "content": response_text,
                "language": detected_lang.value,
                "intent_detected": intent,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return {
            "response": response_text,
            "detected_language": detected_lang.value,
            "language_name": detected_lang.display_name,
            "confidence": confidence,
            "intent": intent,
        }

    async def _generate_response(
        self,
        conv: Conversation,
        message: str,
        language: Language,
        intent: Optional[str],
    ) -> str:
        """Generate response in appropriate language."""

        # Map intent to knowledge base key
        kb_mappings = {
            "shipping": "shipping_info",
            "returns": "return_policy",
            "products": None,  # Will need sub-detection
        }

        if intent:
            kb_key = kb_mappings.get(intent)

            # Product sub-detection
            if intent == "products":
                message_lower = message.lower()
                if any(
                    w in message_lower
                    for w in ["monitor", "screen", "display", "モニター", "显示器"]
                ):
                    kb_key = "product_monitors"
                elif any(
                    w in message_lower
                    for w in ["keyboard", "teclado", "キーボード", "键盘"]
                ):
                    kb_key = "product_keyboards"
                elif any(
                    w in message_lower for w in ["cable", "câble", "ケーブル", "线缆"]
                ):
                    kb_key = "product_cables"

            if kb_key:
                response = self.knowledge_base.get(kb_key, language)
                if response:
                    return response

        # Check for goodbye/closing
        goodbye_patterns = {
            "en": ["bye", "goodbye", "thanks", "that's all"],
            "es": ["adiós", "gracias", "eso es todo"],
            "fr": ["au revoir", "merci", "c'est tout"],
            "de": ["tschüss", "danke", "das wäre alles"],
            "ja": ["さようなら", "ありがとう", "以上です"],
            "zh": ["再见", "谢谢", "就这些"],
        }

        message_lower = message.lower()
        lang_goodbye = goodbye_patterns.get(language.value, goodbye_patterns["en"])
        if any(pattern in message_lower for pattern in lang_goodbye):
            return self.knowledge_base.get("goodbye", language)

        # Default response - ask for clarification
        clarification_responses = {
            "en": f"I'd be happy to help! Could you please tell me more about what you're looking for? I can assist with shipping, returns, and product information.",
            "es": "¡Estaré encantado de ayudarle! ¿Podría decirme más sobre lo que busca? Puedo ayudarle con envíos, devoluciones e información de productos.",
            "fr": "Je serai ravi de vous aider! Pourriez-vous m'en dire plus sur ce que vous recherchez? Je peux vous aider concernant les livraisons, les retours et les informations sur les produits.",
            "de": "Ich helfe Ihnen gerne! Könnten Sie mir bitte mehr darüber erzählen, wonach Sie suchen? Ich kann Ihnen bei Versand, Rückgaben und Produktinformationen helfen.",
            "ja": "喜んでお手伝いいたします！何をお探しですか？配送、返品、製品情報についてご案内できます。",
            "zh": "我很乐意为您服务！请告诉我您需要什么帮助？我可以协助您处理配送、退货和产品咨询。",
        }

        return clarification_responses.get(
            language.value, clarification_responses["en"]
        )

    def get_conversation_summary(self, conversation_id: str) -> dict:
        """Get conversation summary with language analysis."""
        conv = self.conversations.get(conversation_id)
        if not conv:
            return {}

        language_counts = defaultdict(int)
        for msg in conv.messages:
            language_counts[msg.get("language", "unknown")] += 1

        return {
            "conversation_id": conv.id,
            "customer": conv.customer.name,
            "preferred_language": conv.customer.preferred_language.display_name,
            "primary_language_used": conv.primary_language.display_name,
            "message_count": len(conv.messages),
            "language_distribution": dict(language_counts),
            "started_at": conv.started_at.isoformat(),
            "duration_minutes": (datetime.now() - conv.started_at).seconds / 60,
        }

    def get_metrics(self) -> dict:
        """Get bot metrics."""
        return {
            **self.metrics,
            "languages_used": list(self.metrics["messages_by_language"].keys()),
            "translations_count": self.translator.translations_count,
            "supported_languages": [l.display_name for l in Language],
        }


class MultilingualConsole:
    """Console interface for multilingual demo."""

    def __init__(self, bot: MultilingualBot):
        self.bot = bot
        self.current_conv: Optional[Conversation] = None

    def print_header(self):
        """Print header in multiple languages."""
        print("\n" + "=" * 60)
        print(f"  🌍 {self.bot.company_name} Multilingual Support")
        print("=" * 60)
        print("  Supported: English, Español, Français, Deutsch, 日本語, 中文")
        print("  Type in any language - we'll respond in your language!")
        print("  Commands: /lang /summary /metrics /quit")
        print("-" * 60)

    async def run(self, customer: CustomerProfile):
        """Run multilingual console."""
        self.print_header()

        # Start conversation
        self.current_conv = await self.bot.start_conversation(customer)

        # Display initial greeting
        initial_msg = self.current_conv.messages[0]
        print(f"\n  🤖 [{initial_msg['language'].upper()}] {initial_msg['content']}")

        while True:
            try:
                user_input = input(f"\n  You: ").strip()

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    if await self._handle_command(user_input):
                        break
                    continue

                # Process message
                result = await self.bot.handle_message(self.current_conv.id, user_input)

                # Display response with language indicator
                lang_flag = {
                    "en": "🇺🇸",
                    "es": "🇪🇸",
                    "fr": "🇫🇷",
                    "de": "🇩🇪",
                    "ja": "🇯🇵",
                    "zh": "🇨🇳",
                }.get(result["detected_language"], "🌐")

                print(
                    f"\n  {lang_flag} Detected: {result['language_name']} ({result['confidence']:.0%})"
                )
                if result.get("intent"):
                    print(f"  💡 Intent: {result['intent']}")
                print(f"\n  🤖 {result['response']}")

            except KeyboardInterrupt:
                print("\n\n  Session ended.")
                break
            except Exception as e:
                print(f"\n  ❌ Error: {e}")

    async def _handle_command(self, command: str) -> bool:
        """Handle slash commands."""
        cmd = command.lower().strip()

        if cmd == "/quit":
            goodbye = self.bot.knowledge_base.get(
                "goodbye", self.current_conv.customer.effective_language
            )
            print(f"\n  🤖 {goodbye}")
            return True

        if cmd == "/lang":
            print("\n  🌍 Supported Languages:")
            for lang in Language:
                print(f"     {lang.native_greeting} - {lang.display_name}")
            return False

        if cmd == "/summary":
            summary = self.bot.get_conversation_summary(self.current_conv.id)
            print("\n  📊 Conversation Summary:")
            print(f"     Customer: {summary['customer']}")
            print(f"     Primary Language: {summary['primary_language_used']}")
            print(f"     Messages: {summary['message_count']}")
            print(f"     Duration: {summary['duration_minutes']:.1f} minutes")
            print(f"     Languages Used: {summary['language_distribution']}")
            return False

        if cmd == "/metrics":
            metrics = self.bot.get_metrics()
            print("\n  📈 Bot Metrics:")
            print(f"     Total Conversations: {metrics['total_conversations']}")
            print(f"     Messages by Language: {dict(metrics['messages_by_language'])}")
            print(f"     Language Switches: {metrics['language_switches']}")
            print(f"     Translations: {metrics['translations_count']}")
            return False

        print(f"  Unknown command: {command}")
        return False


async def demo():
    """Run interactive multilingual demo."""
    bot = MultilingualBot(company_name="TechWorld")
    console = MultilingualConsole(bot)

    customer = CustomerProfile(
        id="demo_customer",
        name="Demo User",
        email="demo@example.com",
        preferred_language=Language.ENGLISH,
    )

    await console.run(customer)


async def automated_demo():
    """Run automated demo showing multilingual capabilities."""
    print("\n" + "=" * 60)
    print("  Multilingual Support - Automated Demo")
    print("=" * 60)

    bot = MultilingualBot(company_name="TechWorld")

    # Test messages in different languages
    test_messages = [
        ("Hi, what are your shipping options?", "en", "English"),
        ("¿Cuánto cuesta el envío?", "es", "Spanish"),
        ("Je voudrais retourner un produit", "fr", "French"),
        ("Haben Sie mechanische Tastaturen?", "de", "German"),
        ("モニターについて教えてください", "ja", "Japanese"),
        ("我想查询订单状态", "zh", "Chinese"),
    ]

    customer = CustomerProfile(
        id="test_customer", name="Test User", email="test@example.com"
    )

    conv = await bot.start_conversation(customer)
    print(f"\n  📝 Initial greeting: {conv.messages[0]['content'][:60]}...")

    print("\n--- Testing Language Detection & Response ---\n")

    for message, expected_lang, lang_name in test_messages:
        print(f"  📨 [{lang_name}] Customer: {message}")

        result = await bot.handle_message(conv.id, message)

        detected = "✅" if result["detected_language"] == expected_lang else "❌"
        print(
            f"     {detected} Detected: {result['language_name']} ({result['confidence']:.0%})"
        )
        print(f"     🤖 Response: {result['response'][:70]}...")
        print()

    # Summary
    print("--- Conversation Summary ---\n")
    summary = bot.get_conversation_summary(conv.id)
    print(f"  Messages: {summary['message_count']}")
    print(f"  Languages: {summary['language_distribution']}")

    print("\n--- Bot Metrics ---\n")
    metrics = bot.get_metrics()
    print(f"  Total Conversations: {metrics['total_conversations']}")
    print(f"  Language Switches: {metrics['language_switches']}")
    print(f"  Messages by Language: {dict(metrics['messages_by_language'])}")


if __name__ == "__main__":
    import sys

    if "--auto" in sys.argv:
        asyncio.run(automated_demo())
    else:
        asyncio.run(demo())
