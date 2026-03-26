/**
 * React & WordPress dependencies
 */
import { useBlockProps } from '@wordpress/block-editor';

/**
 * Save component
 */
export default function save({ attributes }) {
	const { position, primaryColor } = attributes;

	const blockProps = useBlockProps.save({
		className: `agentic-brain-chat-widget position-${position}`,
		style: { '--chat-primary-color': primaryColor },
		'data-position': position,
		'data-primary-color': primaryColor,
	});

	return (
		<div {...blockProps}>
			<div className="agentic-brain-chat-container">
				{/* The chat widget will be initialized here by the frontend script */}
				<button 
					className="chat-launcher" 
					style={{ backgroundColor: primaryColor }}
					aria-label="Open Chat"
				>
					<span className="dashicons dashicons-format-chat"></span>
				</button>
			</div>
		</div>
	);
}