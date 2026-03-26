/**
 * Block Registration Entry Point
 */
import { registerBlockType } from '@wordpress/blocks';

// Chat Widget
import './../blocks/chat-widget/style.css';
import EditChatWidget from './../blocks/chat-widget/edit';
import saveChatWidget from './../blocks/chat-widget/save';
import metadataChatWidget from './../blocks/chat-widget/block.json';

registerBlockType(metadataChatWidget.name, {
	edit: EditChatWidget,
	save: saveChatWidget,
});

// Product Search
import './../blocks/product-search/style.css';
import EditProductSearch from './../blocks/product-search/edit';
import saveProductSearch from './../blocks/product-search/save';
import metadataProductSearch from './../blocks/product-search/block.json';

registerBlockType(metadataProductSearch.name, {
	edit: EditProductSearch,
	save: saveProductSearch,
});

// FAQ Bot
import './../blocks/faq-bot/style.css';
import EditFaqBot from './../blocks/faq-bot/edit';
import saveFaqBot from './../blocks/faq-bot/save';
import metadataFaqBot from './../blocks/faq-bot/block.json';

registerBlockType(metadataFaqBot.name, {
	edit: EditFaqBot,
	save: saveFaqBot,
});