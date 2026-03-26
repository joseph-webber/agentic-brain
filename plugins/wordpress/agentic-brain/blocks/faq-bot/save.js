import { useBlockProps, RichText } from '@wordpress/block-editor';

export default function save({ attributes }) {
	const { title, initialQuestion, productSource, showAvatar } = attributes;

	return (
		<div {...useBlockProps.save({
			'data-source': productSource,
			'data-initial-question': initialQuestion
		})}>
			<div className="faq-bot-container">
				<div className="faq-header">
					{showAvatar && (
						<div className="bot-avatar" aria-hidden="true">
							<span className="dashicons dashicons-admin-users"></span>
						</div>
					)}
					<RichText.Content tagName="h3" value={title} />
				</div>
				
				<div className="faq-conversation" aria-live="polite">
					<div className="message bot-message">
						<div className="message-content">
							<p>{initialQuestion}</p>
						</div>
					</div>
				</div>
				
				<form className="faq-input-form">
					<label className="screen-reader-text" htmlFor="faq-question-input">
						{initialQuestion}
					</label>
					<input 
						type="text" 
						id="faq-question-input"
						className="faq-input" 
						placeholder="Ask a question..." 
						aria-required="true"
					/>
					<button type="submit" className="faq-submit" aria-label="Send question">
						<span className="dashicons dashicons-arrow-right-alt2"></span>
					</button>
				</form>
			</div>
		</div>
	);
}