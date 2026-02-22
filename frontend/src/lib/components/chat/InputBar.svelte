<!--
  InputBar.svelte - Message input area at the bottom of the chat.

  Features auto-expanding textarea (up to 6 lines), Cmd/Ctrl+Enter to send,
  and a send button with the Lucide Send icon.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Send } from 'lucide-svelte';

	interface InputBarProps {
		onSend: (message: string) => void;
		disabled?: boolean;
	}

	let { onSend, disabled = false }: InputBarProps = $props();

	let text = $state('');
	let textareaEl: HTMLTextAreaElement | undefined = $state();

	let canSend = $derived(text.trim().length > 0 && !disabled);

	function adjustHeight() {
		if (!textareaEl) return;
		textareaEl.style.height = 'auto';
		// Max 6 lines: ~24px per line at text-sm
		const maxHeight = 24 * 6;
		textareaEl.style.height = `${Math.min(textareaEl.scrollHeight, maxHeight)}px`;
	}

	function handleSend() {
		const trimmed = text.trim();
		if (!trimmed || disabled) return;
		onSend(trimmed);
		text = '';
		if (textareaEl) {
			textareaEl.style.height = 'auto';
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
			e.preventDefault();
			handleSend();
		}
	}

	function handleInput() {
		adjustHeight();
	}
</script>

<div class="flex items-end gap-2 border-t border-border bg-surface px-4 py-3">
	<textarea
		bind:this={textareaEl}
		bind:value={text}
		oninput={handleInput}
		onkeydown={handleKeydown}
		{disabled}
		rows={1}
		placeholder="Type a message..."
		class="min-h-[40px] flex-1 resize-none rounded-lg border border-border bg-surface-secondary px-3 py-2.5 text-sm text-text-primary placeholder-text-secondary outline-none transition-colors focus:border-accent disabled:cursor-not-allowed disabled:opacity-50"
	></textarea>

	<button
		type="button"
		onclick={handleSend}
		disabled={!canSend}
		class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
		aria-label="Send message"
	>
		<Send size={18} />
	</button>
</div>
