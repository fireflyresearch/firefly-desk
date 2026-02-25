<!--
  InputBar.svelte - Message input area at the bottom of the chat.

  Features auto-expanding textarea (up to 8 lines), Enter to send,
  Shift+Enter for newline, file attachment via Paperclip button,
  slash command autocomplete, and a send button.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Paperclip, Send, Terminal, Activity, Database, Settings, FileText, HelpCircle, BookOpen, Server } from 'lucide-svelte';
	import FileUploadArea from './FileUploadArea.svelte';
	import ModelStatus from './ModelStatus.svelte';
	import { uploadFile, type UploadedFile } from '$lib/services/files.js';

	interface SlashCommand {
		command: string;
		label: string;
		description: string;
		icon: typeof Terminal;
	}

	const SLASH_COMMANDS: SlashCommand[] = [
		{ command: '/help', label: 'Help', description: 'Show available slash commands', icon: HelpCircle },
		{ command: '/status', label: 'Status', description: 'LLM provider, model, and fallback info', icon: Activity },
		{ command: '/context', label: 'Context', description: 'Show retrieved entities, knowledge, processes', icon: Database },
		{ command: '/memory', label: 'Memory', description: 'Conversation memory and token counts', icon: Database },
		{ command: '/config', label: 'Config', description: 'Agent configuration and user info', icon: Settings },
		{ command: '/prompt', label: 'Prompt', description: 'Preview system prompt context sections', icon: FileText },
	];

	interface InputBarProps {
		onSend: (message: string, files?: UploadedFile[]) => void;
		disabled?: boolean;
		pendingFiles?: File[];
		conversationId?: string | null;
	}

	let { onSend, disabled = false, pendingFiles = $bindable([]), conversationId = null }: InputBarProps = $props();

	let text = $state('');
	let textareaEl: HTMLTextAreaElement | undefined = $state();
	let fileInputEl: HTMLInputElement | undefined = $state();
	let uploading = $state(false);
	let showSlashMenu = $state(false);
	let slashFilter = $state('');
	let selectedSlashIndex = $state(0);

	// Mention autocomplete state
	let showMentionMenu = $state(false);
	let mentionType = $state<'knowledge' | 'system' | null>(null);
	let mentionFilter = $state('');
	let mentionTriggerPos = $state(0);
	let mentionItems = $state<Array<{id: string, name: string, type: string}>>([]);
	let selectedMentionIdx = $state(0);
	let mentionDebounceTimer: ReturnType<typeof setTimeout> | undefined;

	let canSend = $derived((text.trim().length > 0 || pendingFiles.length > 0) && !disabled && !uploading);

	let filteredCommands = $derived(
		SLASH_COMMANDS.filter((cmd) =>
			cmd.command.startsWith('/' + slashFilter) || cmd.label.toLowerCase().includes(slashFilter.toLowerCase())
		)
	);

	function adjustHeight() {
		if (!textareaEl) return;
		textareaEl.style.height = 'auto';
		const maxHeight = 24 * 8;
		textareaEl.style.height = `${Math.min(textareaEl.scrollHeight, maxHeight)}px`;
	}

	async function handleSend() {
		const trimmed = text.trim();
		if ((!trimmed && pendingFiles.length === 0) || disabled || uploading) return;

		showSlashMenu = false;
		showMentionMenu = false;

		// Upload pending files first
		let uploadedFiles: UploadedFile[] = [];
		if (pendingFiles.length > 0) {
			uploading = true;
			try {
				const convId = conversationId ?? crypto.randomUUID();
				uploadedFiles = await Promise.all(
					pendingFiles.map((f) => uploadFile(f, convId))
				);
			} catch {
				uploading = false;
				return;
			}
			uploading = false;
		}

		onSend(trimmed || '(attached files)', uploadedFiles.length > 0 ? uploadedFiles : undefined);
		text = '';
		pendingFiles = [];
		if (textareaEl) {
			textareaEl.style.height = 'auto';
		}
	}

	function selectSlashCommand(cmd: SlashCommand) {
		// If the command takes an argument (context, prompt), add a space
		const needsArg = cmd.command === '/context' || cmd.command === '/prompt';
		text = needsArg ? cmd.command + ' ' : cmd.command;
		showSlashMenu = false;
		textareaEl?.focus();
		if (!needsArg) {
			handleSend();
		}
	}

	async function fetchMentionItems() {
		try {
			if (mentionType === 'knowledge') {
				const { apiJson } = await import('$lib/services/api.js');
				const docs = await apiJson<Array<{id: string, title: string, document_type: string}>>('/knowledge/documents');
				mentionItems = docs
					.filter(d => d.title.toLowerCase().includes(mentionFilter.toLowerCase()))
					.slice(0, 8)
					.map(d => ({ id: d.id, name: d.title, type: d.document_type }));
			} else if (mentionType === 'system') {
				const { apiJson } = await import('$lib/services/api.js');
				const systems = await apiJson<Array<{id: string, name: string, status: string}>>('/catalog/systems');
				mentionItems = systems
					.filter(s => s.name.toLowerCase().includes(mentionFilter.toLowerCase()))
					.slice(0, 8)
					.map(s => ({ id: s.id, name: s.name, type: s.status }));
			}
		} catch {
			mentionItems = [];
		}
	}

	function selectMention(item: { id: string; name: string; type: string }) {
		const prefix = mentionType === 'knowledge' ? '@' : '#';
		const token = `${prefix}[${item.name}](${item.id})`;
		// Replace the trigger char + filter text with the token
		const before = text.slice(0, mentionTriggerPos);
		const cursorPos = textareaEl?.selectionStart ?? text.length;
		const after = text.slice(cursorPos);
		text = before + token + ' ' + after;
		showMentionMenu = false;
		mentionItems = [];
		textareaEl?.focus();
	}

	function handleKeydown(e: KeyboardEvent) {
		// Mention menu keyboard navigation
		if (showMentionMenu && mentionItems.length > 0) {
			if (e.key === 'ArrowDown') {
				e.preventDefault();
				selectedMentionIdx = (selectedMentionIdx + 1) % mentionItems.length;
				return;
			}
			if (e.key === 'ArrowUp') {
				e.preventDefault();
				selectedMentionIdx = (selectedMentionIdx - 1 + mentionItems.length) % mentionItems.length;
				return;
			}
			if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
				e.preventDefault();
				selectMention(mentionItems[selectedMentionIdx]);
				return;
			}
			if (e.key === 'Escape') {
				e.preventDefault();
				showMentionMenu = false;
				return;
			}
		}

		if (showSlashMenu && filteredCommands.length > 0) {
			if (e.key === 'ArrowDown') {
				e.preventDefault();
				selectedSlashIndex = (selectedSlashIndex + 1) % filteredCommands.length;
				return;
			}
			if (e.key === 'ArrowUp') {
				e.preventDefault();
				selectedSlashIndex = (selectedSlashIndex - 1 + filteredCommands.length) % filteredCommands.length;
				return;
			}
			if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
				e.preventDefault();
				selectSlashCommand(filteredCommands[selectedSlashIndex]);
				return;
			}
			if (e.key === 'Escape') {
				e.preventDefault();
				showSlashMenu = false;
				return;
			}
		}

		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSend();
		}
	}

	function handleInput() {
		adjustHeight();

		// Detect slash command typing
		const val = text;
		if (val.startsWith('/') && !val.includes(' ')) {
			showSlashMenu = true;
			slashFilter = val.slice(1);
			selectedSlashIndex = 0;
		} else {
			showSlashMenu = false;
		}

		// Detect @ or # mention
		if (!showSlashMenu) {
			const cursorPos = textareaEl?.selectionStart ?? val.length;
			const textBeforeCursor = val.slice(0, cursorPos);

			// Find the last @ or # that starts a mention
			const atIdx = textBeforeCursor.lastIndexOf('@');
			const hashIdx = textBeforeCursor.lastIndexOf('#');

			const triggerIdx = Math.max(atIdx, hashIdx);
			const triggerChar = triggerIdx === atIdx ? '@' : '#';

			if (triggerIdx >= 0) {
				const textAfterTrigger = textBeforeCursor.slice(triggerIdx + 1);
				// Only show menu if no space in the filter text (still typing the mention)
				if (!textAfterTrigger.includes(' ') && textAfterTrigger.length <= 50) {
					mentionType = triggerChar === '@' ? 'knowledge' : 'system';
					mentionFilter = textAfterTrigger;
					mentionTriggerPos = triggerIdx;
					selectedMentionIdx = 0;
					showMentionMenu = true;
					// Debounce the API fetch
					clearTimeout(mentionDebounceTimer);
					mentionDebounceTimer = setTimeout(() => fetchMentionItems(), 200);
				} else {
					showMentionMenu = false;
				}
			} else {
				showMentionMenu = false;
			}
		}
	}

	function openFilePicker() {
		fileInputEl?.click();
	}

	function handleFileChange(e: Event) {
		const input = e.target as HTMLInputElement;
		if (input.files) {
			pendingFiles = [...pendingFiles, ...Array.from(input.files)];
			input.value = '';
		}
	}

	function handlePaste(e: ClipboardEvent) {
		const clipboardFiles = e.clipboardData?.files;
		if (clipboardFiles && clipboardFiles.length > 0) {
			e.preventDefault();
			pendingFiles = [...pendingFiles, ...Array.from(clipboardFiles)];
		}
	}

	function removeFile(index: number) {
		pendingFiles = pendingFiles.filter((_, i) => i !== index);
	}
</script>

<div class="px-4 pb-4 pt-0">
	<div class="relative mx-auto max-w-3xl">
		{#if pendingFiles.length > 0}
			<FileUploadArea files={pendingFiles} onRemove={removeFile} />
		{/if}

		<!-- Slash command popover -->
		{#if showSlashMenu && filteredCommands.length > 0}
			<div class="absolute bottom-full left-0 right-0 z-50 mb-2 overflow-hidden rounded-xl border border-border bg-surface shadow-xl">
				<div class="px-3 py-2 text-xs font-medium uppercase tracking-wider text-text-secondary">
					Slash Commands
				</div>
				{#each filteredCommands as cmd, i (cmd.command)}
					{@const Icon = cmd.icon}
					<button
						type="button"
						onclick={() => selectSlashCommand(cmd)}
						class="flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors {i === selectedSlashIndex ? 'bg-accent/10 text-accent' : 'text-text-primary hover:bg-surface-secondary'}"
					>
						<span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md {i === selectedSlashIndex ? 'bg-accent/20' : 'bg-surface-secondary'}">
							<Icon size={14} />
						</span>
						<span class="flex flex-col">
							<span class="text-sm font-medium">{cmd.command}</span>
							<span class="text-xs text-text-secondary">{cmd.description}</span>
						</span>
					</button>
				{/each}
				<div class="border-t border-border/50 px-3 py-1.5 text-[10px] text-text-secondary">
					<kbd class="rounded bg-surface-secondary px-1 py-0.5 font-mono">↑↓</kbd> navigate
					<kbd class="ml-2 rounded bg-surface-secondary px-1 py-0.5 font-mono">Tab</kbd> select
					<kbd class="ml-2 rounded bg-surface-secondary px-1 py-0.5 font-mono">Esc</kbd> dismiss
				</div>
			</div>
		{/if}

		<!-- Mention autocomplete popover -->
		{#if showMentionMenu && mentionItems.length > 0}
			<div class="absolute bottom-full left-0 right-0 z-50 mb-2 overflow-hidden rounded-xl border border-border bg-surface shadow-xl">
				<div class="px-3 py-2 text-xs font-medium uppercase tracking-wider text-text-secondary">
					{#if mentionType === 'knowledge'}
						<BookOpen size={12} class="mr-1 inline" />
						Knowledge Documents
					{:else}
						<Server size={12} class="mr-1 inline" />
						Catalog Systems
					{/if}
				</div>
				{#each mentionItems as item, i (item.id)}
					<button
						type="button"
						onclick={() => selectMention(item)}
						class="flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors {i === selectedMentionIdx ? 'bg-accent/10 text-accent' : 'text-text-primary hover:bg-surface-secondary'}"
					>
						<span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md {i === selectedMentionIdx ? 'bg-accent/20' : 'bg-surface-secondary'}">
							{#if mentionType === 'knowledge'}
								<BookOpen size={14} />
							{:else}
								<Server size={14} />
							{/if}
						</span>
						<span class="flex flex-col">
							<span class="text-sm font-medium">{item.name}</span>
							<span class="text-xs text-text-secondary">{item.type}</span>
						</span>
					</button>
				{/each}
				<div class="border-t border-border/50 px-3 py-1.5 text-[10px] text-text-secondary">
					<kbd class="rounded bg-surface-secondary px-1 py-0.5 font-mono">↑↓</kbd> navigate
					<kbd class="ml-2 rounded bg-surface-secondary px-1 py-0.5 font-mono">Tab</kbd> select
					<kbd class="ml-2 rounded bg-surface-secondary px-1 py-0.5 font-mono">Esc</kbd> dismiss
				</div>
			</div>
		{/if}

		<div class="rounded-2xl border border-border/60 bg-surface p-1 shadow-sm transition-all duration-200 focus-within:border-transparent focus-within:ring-0 focus-within:shadow-md">
			<div class="flex items-end gap-1">
				<button
					type="button"
					onclick={openFilePicker}
					disabled={disabled || uploading}
					class="mb-1.5 ml-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-surface-secondary hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
					aria-label="Attach file"
				>
					<Paperclip size={16} />
				</button>

				<input
					bind:this={fileInputEl}
					type="file"
					multiple
					onchange={handleFileChange}
					class="hidden"
					aria-hidden="true"
				/>

				<textarea
					bind:this={textareaEl}
					bind:value={text}
					oninput={handleInput}
					onkeydown={handleKeydown}
					onpaste={handlePaste}
					disabled={disabled || uploading}
					rows={2}
					placeholder={uploading ? 'Uploading files...' : 'Ask Ember anything...'}
					class="min-h-[72px] flex-1 resize-none bg-transparent px-2 py-3 text-sm leading-relaxed text-text-primary placeholder-text-secondary outline-none disabled:cursor-not-allowed disabled:opacity-50"
				></textarea>

				<button
					type="button"
					onclick={handleSend}
					disabled={!canSend}
					class="mb-1.5 mr-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-white transition-all hover:scale-105 hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
					aria-label="Send message"
				>
					<Send size={16} />
				</button>
			</div>
		</div>

		<!-- Footer: model indicator + hint -->
		<div class="flex items-center justify-between px-2 pt-1.5">
			<ModelStatus compact />
			<span class="text-[10px] text-text-secondary">
				<kbd class="rounded bg-surface-secondary/50 px-1 py-0.5 font-mono text-[9px]">Shift+Enter</kbd> for new line
			</span>
		</div>
	</div>
</div>
