/**
 * React & WordPress dependencies
 */
import { __ } from '@wordpress/i18n';
import { useBlockProps, InspectorControls, RichText } from '@wordpress/block-editor';
import { PanelBody, TextControl, SelectControl, ToggleControl } from '@wordpress/components';

export default function Edit({ attributes, setAttributes }) {
	const { title, initialQuestion, productSource, showAvatar } = attributes;
	
	const blockProps = useBlockProps({
		className: 'agentic-brain-faq-bot'
	});

	return (
		<div {...blockProps}>
			<InspectorControls>
				<PanelBody title={__('Bot Settings', 'agentic-brain')}>
					<TextControl
						label={__('Initial Question', 'agentic-brain')}
						value={initialQuestion}
						onChange={(val) => setAttributes({ initialQuestion: val })}
					/>
					<SelectControl
						label={__('Training Source', 'agentic-brain')}
						value={productSource}
						options={[
							{ label: 'All Products', value: 'all' },
							{ label: 'Current Category', value: 'category' },
							{ label: 'Current Product Only', value: 'current' },
						]}
						onChange={(val) => setAttributes({ productSource: val })}
					/>
					<ToggleControl
						label={__('Show Avatar', 'agentic-brain')}
						checked={showAvatar}
						onChange={(val) => setAttributes({ showAvatar: val })}
					/>
				</PanelBody>
			</InspectorControls>

			<div className="faq-bot-header">
				{showAvatar && <span className="bot-avatar dashicons dashicons-admin-users"></span>}
				<RichText
					tagName="h3"
					value={title}
					onChange={(val) => setAttributes({ title: val })}
					placeholder={__('FAQ Title...', 'agentic-brain')}
				/>
			</div>
			
			<div className="faq-bot-body">
				<div className="bot-message">
					<p>{initialQuestion}</p>
				</div>
				<div className="user-input-mock">
					<span>{__('Type your question here...', 'agentic-brain')}</span>
				</div>
			</div>
		</div>
	);
}