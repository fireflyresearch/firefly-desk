<!--
  InputBar.svelte - Message input area at the bottom of the chat.

  Features auto-expanding textarea (up to 6 lines), Enter to send,
  Shift+Enter for newline, file attachment via Paperclip button,
  and a send button inside a prominent container.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Paperclip, Send } from 'lucide-svelte';
	import FileUploadArea from './FileUploadArea.svelte';
	import { uploadFile, type UploadedFile } from '$lib/services/files.js';

	interface InputBarProps {
		onSend: (message: string, files?: UploadedFile[]) => void;
		disabled?: boolean;
		pendingFiles?: File[];
	}

	let { onSend, disabled = false, pendingFiles = $bindable([]) }: InputBarProps = $props();

	let text = $state('');
	let textareaEl: HTMLTextAreaElement | undefined = $state();
	let fileInputEl: HTMLInputElement | undefined = $state();
	let uploading = $state(false);

	let canSend = $derived((text.trim().length > 0 || pendingFiles.length > 0) && !disabled && !uploading);

	function adjustHeight() {
		if (!textareaEl) return;
		textareaEl.style.height = 'auto';
		// Max 6 lines: ~24px per line at text-sm
		const maxHeight = 24 * 6;
		textareaEl.style.height = `${Math.min(textareaEl.scrollHeight, maxHeight)}px`;
	}

	async function handleSend() {
		const trimmed = text.trim();
		if ((!trimmed && pendingFiles.length === 0) || disabled || uploading) return;

		// Upload pending files first
		let uploadedFiles: UploadedFile[] = [];
		if (pendingFiles.length > 0) {
			uploading = true;
			try {
				// We need a conversation ID for uploads -- generate if needed
				const convId = crypto.randomUUID();
				uploadedFiles = await Promise.all(
					pendingFiles.map((f) => uploadFile(f, convId))
				);
			} catch {
				// Upload failed -- allow user to retry
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

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSend();
		}
	}

	function handleInput() {
		adjustHeight();
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

	function removeFile(index: number) {
		pendingFiles = pendingFiles.filter((_, i) => i !== index);
	}
</script>

<div class="px-4 pb-4 pt-0">
	<div class="mx-auto max-w-3xl">
		{#if pendingFiles.length > 0}
			<FileUploadArea files={pendingFiles} onRemove={removeFile} />
		{/if}
		<div class="rounded-2xl border border-border bg-surface p-1 shadow-lg">
			<div class="flex items-end gap-1">
				<button
					type="button"
					onclick={openFilePicker}
					disabled={disabled || uploading}
					class="mb-1 ml-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-surface-secondary hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40"
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
					disabled={disabled || uploading}
					rows={1}
					placeholder={uploading ? 'Uploading files...' : 'Type a message...'}
					class="min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2.5 text-sm text-text-primary placeholder-text-secondary outline-none disabled:cursor-not-allowed disabled:opacity-50"
				></textarea>

				<button
					type="button"
					onclick={handleSend}
					disabled={!canSend}
					class="mb-1 mr-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
					aria-label="Send message"
				>
					<Send size={16} />
				</button>
			</div>
		</div>
	</div>
</div>
