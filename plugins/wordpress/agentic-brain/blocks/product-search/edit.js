/**
 * React & WordPress dependencies
 */
import { __ } from '@wordpress/i18n';
import { useBlockProps, InspectorControls } from '@wordpress/block-editor';
import { PanelBody, TextControl, ToggleControl, SelectControl } from '@wordpress/components';

export default function Edit({ attributes, setAttributes }) {
	const { placeholder, enableVoice, displayMode, limit } = attributes;
	
	const blockProps = useBlockProps();

	return (
		<div {...blockProps}>
			<InspectorControls>
				<PanelBody title={__('Search Settings', 'agentic-brain')}>
					<TextControl
						label={__('Placeholder Text', 'agentic-brain')}
						value={placeholder}
						onChange={(val) => setAttributes({ placeholder: val })}
					/>
					<ToggleControl
						label={__('Enable Voice Search', 'agentic-brain')}
						checked={enableVoice}
						onChange={(val) => setAttributes({ enableVoice: val })}
					/>
					<SelectControl
						label={__('Results Display Mode', 'agentic-brain')}
						value={displayMode}
						options={[
							{ label: 'Grid', value: 'grid' },
							{ label: 'List', value: 'list' },
						]}
						onChange={(val) => setAttributes({ displayMode: val })}
					/>
					<TextControl
						label={__('Product Limit', 'agentic-brain')}
						type="number"
						value={limit}
						onChange={(val) => setAttributes({ limit: parseInt(val) })}
					/>
				</PanelBody>
			</InspectorControls>

			<div className="agentic-brain-search-preview">
				<div className="search-bar">
					<span className="search-icon dashicons dashicons-search"></span>
					<input 
						type="text" 
						placeholder={placeholder} 
						disabled
					/>
					{enableVoice && (
						<span className="voice-icon dashicons dashicons-microphone"></span>
					)}
				</div>
				<div className={`search-results-preview mode-${displayMode}`}>
					<div className="preview-item"></div>
					<div className="preview-item"></div>
					<div className="preview-item"></div>
				</div>
			</div>
		</div>
	);
}