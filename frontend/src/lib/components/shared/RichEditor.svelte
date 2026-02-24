<!--
  RichEditor.svelte - Reusable Notion-like rich text editor built on Tiptap.

  Provides a WYSIWYG editor with Markdown storage, supporting headings, lists,
  task lists, tables, code blocks with syntax highlighting, images, and links.
  Two display modes: 'full' (toolbar + bubble menu) and 'compact' (bubble menu
  only). All Tiptap imports are dynamic to ensure SSR safety in SvelteKit.

  Props:
    value       - Editor content as Markdown (synced via onchange)
    placeholder - Placeholder text shown when the editor is empty
    readonly    - If true, the editor is not editable
    minHeight   - CSS min-height for the editor container (default '200px')
    mode        - Display mode: 'full' (toolbar) or 'compact' (bubble only)
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
		placeholder?: string;
		readonly?: boolean;
		minHeight?: string;
		mode?: 'full' | 'compact';
		onchange?: (markdown: string) => void;
	}

	let {
		value = '',
		placeholder = 'Start writing...',
		readonly = false,
		minHeight = '200px',
		mode = 'full',
		onchange
	}: Props = $props();

	// -------------------------------------------------------------------
	// Internal state
	// -------------------------------------------------------------------

	let editorElement: HTMLDivElement;
	let editor: import('@tiptap/core').Editor | undefined = $state(undefined);
	let internalUpdate = false;

	/** Typed accessor for the tiptap-markdown storage (added at runtime). */
	function getMarkdown(e: import('@tiptap/core').Editor): string {
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		return (e.storage as any).markdown.getMarkdown();
	}

	// -------------------------------------------------------------------
	// Lifecycle - initialise Tiptap in the browser only
	// -------------------------------------------------------------------

	onMount(() => {
		// Dynamic imports keep Tiptap out of the SSR bundle.
		Promise.all([
			import('@tiptap/core'),
			import('@tiptap/starter-kit'),
			import('@tiptap/extension-placeholder'),
			import('@tiptap/extension-link'),
			import('@tiptap/extension-image'),
			import('@tiptap/extension-task-list'),
			import('@tiptap/extension-task-item'),
			import('@tiptap/extension-table'),
			import('@tiptap/extension-table-row'),
			import('@tiptap/extension-table-cell'),
			import('@tiptap/extension-table-header'),
			import('@tiptap/extension-code-block-lowlight'),
			import('@tiptap/extension-typography'),
			import('tiptap-markdown'),
			import('lowlight')
		]).then(
			([
				tiptapCore,
				starterKitMod,
				placeholderMod,
				linkMod,
				imageMod,
				taskListMod,
				taskItemMod,
				tableMod,
				tableRowMod,
				tableCellMod,
				tableHeaderMod,
				codeBlockLowlightMod,
				typographyMod,
				markdownMod,
				lowlightMod
			]) => {
				const { Editor } = tiptapCore;
				const { StarterKit } = starterKitMod;
				const { Placeholder } = placeholderMod;
				const { Link } = linkMod;
				const { Image } = imageMod;
				const { TaskList } = taskListMod;
				const { TaskItem } = taskItemMod;
				const { Table } = tableMod;
				const { TableRow } = tableRowMod;
				const { TableCell } = tableCellMod;
				const { TableHeader } = tableHeaderMod;
				const { CodeBlockLowlight } = codeBlockLowlightMod;
				const { Typography } = typographyMod;
				const { Markdown } = markdownMod;
				const lowlight = lowlightMod.createLowlight(lowlightMod.common);

				editor = new Editor({
					element: editorElement,
					editable: !readonly,
					content: value,
					extensions: [
						StarterKit.configure({
							codeBlock: false,
							link: false
						}),
						Placeholder.configure({
							placeholder
						}),
						Link.configure({
							openOnClick: false,
							autolink: true,
							linkOnPaste: true
						}),
						Image,
						TaskList,
						TaskItem.configure({
							nested: true
						}),
						Table.configure({
							resizable: false
						}),
						TableRow,
						TableCell,
						TableHeader,
						CodeBlockLowlight.configure({
							lowlight
						}),
						Typography,
						Markdown.configure({
							html: false,
							transformCopiedText: true,
							transformPastedText: true
						})
					],
					onUpdate: ({ editor: e }) => {
						internalUpdate = true;
						onchange?.(getMarkdown(e));
						internalUpdate = false;
					}
				});
			}
		);

		return () => {
			editor?.destroy();
		};
	});

	// -------------------------------------------------------------------
	// Sync external value changes into the editor
	// -------------------------------------------------------------------

	$effect(() => {
		if (editor && !internalUpdate) {
			const currentMarkdown = getMarkdown(editor);
			if (value !== currentMarkdown) {
				editor.commands.setContent(value);
			}
		}
	});

	// -------------------------------------------------------------------
	// Sync readonly changes into the editor
	// -------------------------------------------------------------------

	$effect(() => {
		if (editor) {
			editor.setEditable(!readonly);
		}
	});

	// -------------------------------------------------------------------
	// Toolbar actions
	// -------------------------------------------------------------------

	function toggleBold() {
		editor?.chain().focus().toggleBold().run();
	}
	function toggleItalic() {
		editor?.chain().focus().toggleItalic().run();
	}
	function toggleStrike() {
		editor?.chain().focus().toggleStrike().run();
	}
	function toggleCode() {
		editor?.chain().focus().toggleCode().run();
	}
	function toggleH1() {
		editor?.chain().focus().toggleHeading({ level: 1 }).run();
	}
	function toggleH2() {
		editor?.chain().focus().toggleHeading({ level: 2 }).run();
	}
	function toggleH3() {
		editor?.chain().focus().toggleHeading({ level: 3 }).run();
	}
	function toggleBulletList() {
		editor?.chain().focus().toggleBulletList().run();
	}
	function toggleOrderedList() {
		editor?.chain().focus().toggleOrderedList().run();
	}
	function toggleTaskList() {
		editor?.chain().focus().toggleTaskList().run();
	}
	function toggleBlockquote() {
		editor?.chain().focus().toggleBlockquote().run();
	}
	function toggleCodeBlock() {
		editor?.chain().focus().toggleCodeBlock().run();
	}
	function insertHorizontalRule() {
		editor?.chain().focus().setHorizontalRule().run();
	}
	function insertTable() {
		editor
			?.chain()
			.focus()
			.insertTable({ rows: 3, cols: 3, withHeaderRow: true })
			.run();
	}

	// -------------------------------------------------------------------
	// Toolbar button definitions
	// -------------------------------------------------------------------

	type ToolbarItem = {
		label: string;
		action: () => void;
		isActive?: () => boolean;
		icon: string;
	};

	const toolbarItems: ToolbarItem[] = [
		{ label: 'Bold', action: toggleBold, isActive: () => !!editor?.isActive('bold'), icon: 'B' },
		{
			label: 'Italic',
			action: toggleItalic,
			isActive: () => !!editor?.isActive('italic'),
			icon: 'I'
		},
		{
			label: 'Strikethrough',
			action: toggleStrike,
			isActive: () => !!editor?.isActive('strike'),
			icon: 'S'
		},
		{ label: 'Code', action: toggleCode, isActive: () => !!editor?.isActive('code'), icon: '<>' },
		{
			label: 'Heading 1',
			action: toggleH1,
			isActive: () => !!editor?.isActive('heading', { level: 1 }),
			icon: 'H1'
		},
		{
			label: 'Heading 2',
			action: toggleH2,
			isActive: () => !!editor?.isActive('heading', { level: 2 }),
			icon: 'H2'
		},
		{
			label: 'Heading 3',
			action: toggleH3,
			isActive: () => !!editor?.isActive('heading', { level: 3 }),
			icon: 'H3'
		},
		{
			label: 'Bullet List',
			action: toggleBulletList,
			isActive: () => !!editor?.isActive('bulletList'),
			icon: '\u2022'
		},
		{
			label: 'Ordered List',
			action: toggleOrderedList,
			isActive: () => !!editor?.isActive('orderedList'),
			icon: '1.'
		},
		{
			label: 'Task List',
			action: toggleTaskList,
			isActive: () => !!editor?.isActive('taskList'),
			icon: '\u2610'
		},
		{
			label: 'Blockquote',
			action: toggleBlockquote,
			isActive: () => !!editor?.isActive('blockquote'),
			icon: '\u275D'
		},
		{
			label: 'Code Block',
			action: toggleCodeBlock,
			isActive: () => !!editor?.isActive('codeBlock'),
			icon: '{}'
		},
		{ label: 'Horizontal Rule', action: insertHorizontalRule, icon: '\u2014' },
		{ label: 'Table', action: insertTable, icon: '\u229E' }
	];
</script>

<div
	class="rich-editor flex flex-col rounded-md border border-border"
	style="min-height: {minHeight}"
>
	{#if mode === 'full' && !readonly && editor}
		<div
			class="flex flex-wrap items-center gap-0.5 border-b border-border bg-surface-secondary px-2 py-1"
		>
			{#each toolbarItems as item}
				<button
					type="button"
					class="rounded px-2 py-1 text-xs font-medium transition-colors hover:bg-surface-hover {item.isActive?.()
						? 'bg-surface-hover text-accent'
						: 'text-text-secondary'}"
					onclick={item.action}
					title={item.label}
				>
					{item.icon}
				</button>
			{/each}
		</div>
	{/if}

	<div
		bind:this={editorElement}
		class="rich-editor-content prose prose-sm max-w-none flex-1 px-4 py-3 text-text-primary"
		class:readonly
	></div>
</div>

<style>
	/* ProseMirror core styling */
	.rich-editor-content :global(.ProseMirror) {
		outline: none;
		min-height: inherit;
	}

	.rich-editor-content :global(.ProseMirror) :global(p.is-editor-empty:first-child::before) {
		content: attr(data-placeholder);
		float: left;
		color: var(--color-text-secondary);
		pointer-events: none;
		height: 0;
	}

	/* Readonly styling */
	.rich-editor-content.readonly {
		background-color: var(--color-surface-secondary);
	}

	/* Task list styling */
	.rich-editor-content :global(ul[data-type='taskList']) {
		list-style: none;
		padding-left: 0;
	}

	.rich-editor-content :global(ul[data-type='taskList'] li) {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
	}

	.rich-editor-content :global(ul[data-type='taskList'] li label) {
		flex-shrink: 0;
		margin-top: 0.25rem;
	}

	.rich-editor-content :global(ul[data-type='taskList'] li div) {
		flex: 1;
	}

	/* Table styling */
	.rich-editor-content :global(table) {
		border-collapse: collapse;
		width: 100%;
		margin: 1rem 0;
	}

	.rich-editor-content :global(th),
	.rich-editor-content :global(td) {
		border: 1px solid var(--color-border);
		padding: 0.5rem;
		text-align: left;
	}

	.rich-editor-content :global(th) {
		background-color: var(--color-surface-secondary);
		font-weight: 600;
	}

	/* Code block styling */
	.rich-editor-content :global(pre) {
		background-color: var(--color-surface-secondary);
		border: 1px solid var(--color-border);
		border-radius: 0.375rem;
		padding: 0.75rem 1rem;
		overflow-x: auto;
		font-family: var(--font-mono);
	}

	.rich-editor-content :global(pre code) {
		background: none;
		padding: 0;
		font-size: 0.875rem;
		color: inherit;
	}

	/* Inline code styling */
	.rich-editor-content :global(:not(pre) > code) {
		background-color: var(--color-surface-secondary);
		border-radius: 0.25rem;
		padding: 0.125rem 0.375rem;
		font-size: 0.875em;
		font-family: var(--font-mono);
	}

	/* Blockquote styling */
	.rich-editor-content :global(blockquote) {
		border-left: 3px solid var(--color-border);
		padding-left: 1rem;
		color: var(--color-text-secondary);
	}

	/* Horizontal rule styling */
	.rich-editor-content :global(hr) {
		border: none;
		border-top: 1px solid var(--color-border);
		margin: 1.5rem 0;
	}

	/* Image styling */
	.rich-editor-content :global(img) {
		max-width: 100%;
		height: auto;
		border-radius: 0.375rem;
	}

	/* Link styling */
	.rich-editor-content :global(a) {
		color: var(--color-accent);
		text-decoration: underline;
		text-underline-offset: 2px;
	}

	.rich-editor-content :global(a:hover) {
		color: var(--color-accent-hover);
	}
</style>
