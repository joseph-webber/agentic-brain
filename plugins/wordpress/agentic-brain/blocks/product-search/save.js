import { useBlockProps } from '@wordpress/block-editor';

export default function save({ attributes }) {
	const { placeholder, enableVoice, displayMode } = attributes;

	return (
		<div {...useBlockProps.save()}>
			<form role="search" method="get" className="agentic-brain-product-search" action="/">
				<div className="search-wrapper">
					<label className="screen-reader-text" htmlFor="agentic-brain-search-field">
						{placeholder}
					</label>
					<input 
						type="search" 
						id="agentic-brain-search-field"
						className="search-field" 
						placeholder={placeholder} 
						name="s" 
					/>
					<input type="hidden" name="post_type" value="product" />
					
					{enableVoice && (
						<button type="button" className="voice-search-trigger" aria-label="Search by voice">
							<span className="dashicons dashicons-microphone"></span>
						</button>
					)}
					
					<button type="submit" className="search-submit">
						<span className="dashicons dashicons-search"></span>
						<span className="screen-reader-text">Search</span>
					</button>
				</div>
				<div 
					className="agentic-brain-search-results" 
					data-display-mode={displayMode}
					aria-live="polite"
				></div>
			</form>
		</div>
	);
}