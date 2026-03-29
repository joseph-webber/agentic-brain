# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""WooCommerce chatbot toolkit for storefront AI conversations and widget embeds."""

from .ai_features import (
    ChatbotAIFeatures,
    ConversationSummary,
    LanguageDetection,
    SentimentAnalysis,
    TranslationResult,
    UrgencyAssessment,
)
from .analytics_dashboard import (
    ChatbotAnalyticsDashboard,
    CommonQuestionInsight,
    ConversationMetrics,
    ConversionTracking,
    CustomerSatisfactionScore,
    PeakHourInsight,
)
from .cart_assistant import CartAssistant, CartLine, CartRecoveryPlan, CartSummary

# WordPress-specific chat features (content discovery + admin assistant + plugin templates)
from .chatbot.wp_admin_bot import WPAdminAPI, WPAdminBot, WPAdminBotConfig
from .chatbot.wp_content_bot import WPContentBot, WPContentBotConfig
from .chatbot.wp_hooks import WordPressHookConfig, generate_wp_hooks_plugin
from .chatbot.wp_widget import WordPressChatWidgetConfig, generate_wp_widget_plugin
from .integration import ChatbotIntegrator
from .intents import (
    CommerceContext,
    CommerceEntities,
    CommerceIntent,
    CommerceIntentDetector,
    CommerceUserType,
    IntentMatch,
)
from .live_handoff import (
    CallbackRequest,
    HandoffRequest,
    LiveHandoffAssistant,
    QueueStatus,
)
from .multi_channel import (
    BaseChannelAdapter,
    ChannelCapabilities,
    ChannelMessage,
    FacebookMessengerAdapter,
    InstagramDMAdapter,
    SMSAdapter,
    UnifiedInbox,
    UnifiedInboxItem,
    WhatsAppAdapter,
)
from .order_support import (
    EtaEstimate,
    ModificationRequest,
    OrderStatusSummary,
    OrderSupport,
    ReturnRequest,
    ShippingUpdate,
)
from .personalization import (
    BrowsingProfile,
    ChatbotPersonalization,
    DynamicPricingSuggestion,
    PersonalizedProductRecommendation,
    PersonaProfile,
    PurchaseHistoryInsights,
)
from .product_advisor import (
    ProductAdvisor,
    ProductComparison,
    RecommendationReason,
)
from .responses import (
    ResponseTemplates,
    format_currency,
    format_order_status,
    format_product_card,
)
from .training import (
    ChatbotTrainingPipeline,
    ContinuousLearningReport,
    FAQEntry,
    FineTuneExample,
    IntentModelArtifact,
)
from .widgets import (
    ChatWidgetConfig,
    render_chat_widget_html,
    render_woocommerce_block,
    render_wordpress_shortcode,
)
from .woo_chatbot import ChatbotReply, WooCommerceChatbot

__all__ = [
    "BaseChannelAdapter",
    "BrowsingProfile",
    "ChannelCapabilities",
    "ChannelMessage",
    "ChatWidgetConfig",
    "ChatbotAIFeatures",
    "ChatbotAnalyticsDashboard",
    "ChatbotPersonalization",
    "ChatbotReply",
    "ChatbotTrainingPipeline",
    "CommerceContext",
    "CommerceEntities",
    "CommerceIntent",
    "CommerceIntentDetector",
    "CommerceUserType",
    "CommonQuestionInsight",
    "ContinuousLearningReport",
    "ConversationMetrics",
    "ConversationSummary",
    "ConversionTracking",
    "CustomerSatisfactionScore",
    "DynamicPricingSuggestion",
    "FAQEntry",
    "FacebookMessengerAdapter",
    "FineTuneExample",
    "InstagramDMAdapter",
    "IntentMatch",
    "IntentModelArtifact",
    "LanguageDetection",
    "PeakHourInsight",
    "PersonaProfile",
    "PersonalizedProductRecommendation",
    "PurchaseHistoryInsights",
    "ResponseTemplates",
    "SMSAdapter",
    "SentimentAnalysis",
    "TranslationResult",
    "UnifiedInbox",
    "UnifiedInboxItem",
    "UrgencyAssessment",
    "WhatsAppAdapter",
    "WooCommerceChatbot",
    "format_currency",
    "format_order_status",
    "format_product_card",
    "render_chat_widget_html",
    "render_woocommerce_block",
    "render_wordpress_shortcode",
    # WordPress chat
    "WPContentBot",
    "WPContentBotConfig",
    "WPAdminAPI",
    "WPAdminBot",
    "WPAdminBotConfig",
    "WordPressChatWidgetConfig",
    "generate_wp_widget_plugin",
    "WordPressHookConfig",
    "generate_wp_hooks_plugin",
    # WooCommerce cart / product / order helpers
    "CartAssistant",
    "CartLine",
    "CartSummary",
    "CartRecoveryPlan",
    "ProductAdvisor",
    "ProductComparison",
    "RecommendationReason",
    "OrderSupport",
    "OrderStatusSummary",
    "ShippingUpdate",
    "ReturnRequest",
    "ModificationRequest",
    "EtaEstimate",
    "LiveHandoffAssistant",
    "HandoffRequest",
    "QueueStatus",
    "CallbackRequest",
    "ChatbotIntegrator",
]
