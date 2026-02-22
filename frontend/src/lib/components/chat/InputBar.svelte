<!--
  InputBar.svelte - Message input area at the bottom of the chat.

  Features auto-expanding textarea (up to 6 lines), Enter to send,
  Shift+Enter for newline, and a send button inside a prominent container.

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
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSend();
		}
	}

	function handleInput() {
		adjustHeight();
	}
</script>

<div class="px-4 pb-4 pt-0">
	<div class="mx-auto max-w-3xl rounded-2xl border border-border bg-surface p-1 shadow-lg">
		<div class="flex items-end gap-2">
			<textarea
				bind:this={textareaEl}
				bind:value={text}
				oninput={handleInput}
				onkeydown={handleKeydown}
				{disabled}
				rows={1}
				placeholder="Type a message..."
				class="min-h-[40px] flex-1 resize-none bg-transparent px-3 py-2.5 text-sm text-text-primary placeholder-text-secondary outline-none disabled:cursor-not-allowed disabled:opacity-50"
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
