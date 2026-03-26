/**
 * React & WordPress dependencies
 */
import { __ } from '@wordpress/i18n';
import { useBlockProps, InspectorControls } from '@wordpress/block-editor';
import { PanelBody, SelectControl, ColorPalette } from '@wordpress/components';

/**
 * Edit component
 */
export default function Edit({ attributes, setAttributes }) {
	const { position, primaryColor } = attributes;

	const blockProps = useBlockProps({
		className: `agentic-brain-chat-widget position-${position}`,
		style: { '--chat-primary-color': primaryColor }
	});

	return (
		<div {...blockProps}>
			<InspectorControls>
				<PanelBody title={__('Widget Settings', 'agentic-brain')}>
					<SelectControl
						label={__('Position', 'agentic-brain')}
						value={position}
						options={[
							{ label: 'Bottom Right', value: 'bottom-right' },
							{ label: 'Bottom Left', value: 'bottom-left' },
						]}
						onChange={(value) => setAttributes({ position: value })}
					/>
					<p>{__('Primary Color', 'agentic-brain')}</p>
					<ColorPalette
						colors={[
							{ name: 'Blue', color: '#0073aa' },
							{ name: 'Red', color: '#d63638' },
							{ name: 'Green', color: '#008a20' },
							{ name: 'Black', color: '#000000' },
						]}
						value={primaryColor}
						onChange={(color) => setAttributes({ primaryColor: color })}
					/>
				</PanelBody>
			</InspectorControls>

			<div className="chat-widget-preview">
				<div className="chat-header" style={{ backgroundColor: primaryColor }}>
					<span>{__('AI Assistant', 'agentic-brain')}</span>
				</div>
				<div className="chat-body">
					<p>{__('Hello! How can I help you today?', 'agentic-brain')}</p>
				</div>
				<div className="chat-input">
					<input type="text" placeholder={__('Type a message...', 'agentic-brain')} disabled />
				</div>
			</div>
		</div>
	);
}