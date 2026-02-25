<!--
  InputBar.svelte - Message input area at the bottom of the chat.

  Features auto-expanding textarea (up to 8 lines), Enter to send,
  Shift+Enter for newline, file attachment via Paperclip button,
  slash command autocomplete, and a send button.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Paperclip, Send, Terminal, Activity, Database, Settings, FileText, HelpCircle } from 'lucide-svelte';
	import FileUploadArea from './FileUploadArea.svelte';
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

	function handleKeydown(e: KeyboardEvent) {
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

		<div class="rounded-2xl border border-border/60 bg-surface p-1 shadow-sm transition-colors">
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
					class="min-h-[56px] flex-1 resize-none bg-transparent px-2 py-3 text-sm leading-relaxed text-text-primary placeholder-text-secondary outline-none disabled:cursor-not-allowed disabled:opacity-50"
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
	</div>
</div>
