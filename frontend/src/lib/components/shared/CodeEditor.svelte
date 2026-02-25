<!--
  CodeEditor.svelte - Reusable CodeMirror 6 code editor wrapper.

  Provides a drop-in code editor with syntax highlighting for Python,
  Jinja2, and JSON. Built on CodeMirror 6 with the One Dark theme.
  All CodeMirror imports are dynamic to ensure SSR safety in SvelteKit.

  Props:
    value       - Editor content (two-way bindable via onchange)
    language    - Syntax mode: 'python' | 'jinja2' | 'json'
    placeholder - Placeholder text shown when the editor is empty
    readonly    - If true, the editor is not editable
    minHeight   - CSS min-height for the editor container (default '200px')
    onchange    - Callback fired when the editor content changes

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { onMount } from 'svelte';

	// -------------------------------------------------------------------
	// Props
	// -------------------------------------------------------------------

	interface Props {
		value?: string;
		language?: 'python' | 'jinja2' | 'json';
		placeholder?: string;
		readonly?: boolean;
		minHeight?: string;
		onchange?: (value: string) => void;
	}

	let {
		value = '',
		language = 'python',
		placeholder = '',
		readonly = false,
		minHeight = '200px',
		onchange
	}: Props = $props();

	// -------------------------------------------------------------------
	// Internal state
	// -------------------------------------------------------------------

	let container: HTMLDivElement;
	let view: import('@codemirror/view').EditorView | undefined;
	let internalUpdate = false;

	// -------------------------------------------------------------------
	// Lifecycle - initialise CodeMirror in the browser only
	// -------------------------------------------------------------------

	onMount(() => {
		// Dynamic imports keep CodeMirror out of the SSR bundle.
		Promise.all([
			import('codemirror'),
			import('@codemirror/view'),
			import('@codemirror/state'),
			import('@codemirror/commands'),
			import('@codemirror/theme-one-dark'),
			import('@codemirror/lang-python'),
			import('@codemirror/lang-html'),
			import('@codemirror/lang-javascript')
		]).then(
			([cm, cmView, cmState, cmCommands, cmTheme, cmPython, cmHtml, cmJs]) => {
				const langExtension =
					language === 'json'
						? cmJs.javascript()
						: language === 'jinja2'
							? cmHtml.html()
							: cmPython.python();

				const extensions = [
					cm.basicSetup,
					cmTheme.oneDark,
					langExtension,
					cmView.EditorView.lineWrapping,
					cmView.keymap.of([cmCommands.indentWithTab]),
					cmView.EditorView.updateListener.of((update) => {
						if (update.docChanged) {
							internalUpdate = true;
							onchange?.(update.state.doc.toString());
							internalUpdate = false;
						}
					})
				];

				if (placeholder) {
					extensions.push(cmView.placeholder(placeholder));
				}

				if (readonly) {
					extensions.push(cmState.EditorState.readOnly.of(true));
					extensions.push(cmView.EditorView.editable.of(false));
				}

				view = new cmView.EditorView({
					doc: value,
					extensions,
					parent: container
				});
			}
		);

		return () => {
			view?.destroy();
		};
	});

	// -------------------------------------------------------------------
	// Sync external value changes into the editor
	// -------------------------------------------------------------------

	$effect(() => {
		if (view && !internalUpdate && value !== view.state.doc.toString()) {
			view.dispatch({
				changes: { from: 0, to: view.state.doc.length, insert: value }
			});
		}
	});
</script>

<div
	bind:this={container}
	class="min-w-0 overflow-hidden rounded-md border border-border [&_.cm-editor]:!outline-none [&_.cm-editor]:max-w-full [&_.cm-scroller]:!overflow-auto"
	style="min-height: {minHeight}"
></div>
