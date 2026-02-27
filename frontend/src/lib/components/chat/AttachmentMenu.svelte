<!--
  AttachmentMenu.svelte - Plus button dropdown for file attachments.

  Shows a dropdown with "Upload File" and "Paste from clipboard" options.
  Reuses existing file upload infrastructure.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Plus, Upload, Clipboard } from 'lucide-svelte';

	interface AttachmentMenuProps {
		disabled?: boolean;
		onFileSelect: (files: File[]) => void;
	}

	let { disabled = false, onFileSelect }: AttachmentMenuProps = $props();

	let open = $state(false);
	let fileInputEl: HTMLInputElement | undefined = $state();

	function toggle() {
		if (disabled) return;
		open = !open;
	}

	function close() {
		open = false;
	}

	function handleUploadClick() {
		fileInputEl?.click();
		close();
	}

	function handleFileChange(e: Event) {
		const input = e.target as HTMLInputElement;
		if (input.files && input.files.length > 0) {
			onFileSelect(Array.from(input.files));
			input.value = '';
		}
	}

	async function handlePasteClick() {
		close();
		try {
			const clipboardItems = await navigator.clipboard.read();
			const files: File[] = [];
			for (const item of clipboardItems) {
				for (const type of item.types) {
					if (type.startsWith('image/') || type === 'application/pdf') {
						const blob = await item.getType(type);
						const ext = type.split('/')[1] || 'bin';
						files.push(new File([blob], `clipboard.${ext}`, { type }));
					}
				}
			}
			if (files.length > 0) {
				onFileSelect(files);
			}
		} catch {
			console.warn('[AttachmentMenu] Clipboard read unavailable');
		}
	}
</script>

<div class="relative">
	<button
		type="button"
		onclick={toggle}
		disabled={disabled}
		class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-text-secondary transition-all hover:bg-surface-secondary hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-40
			{open ? 'rotate-45 bg-surface-secondary text-text-primary' : ''}"
		aria-label="Attach file"
	>
		<Plus size={18} />
	</button>

	<input
		bind:this={fileInputEl}
		type="file"
		multiple
		onchange={handleFileChange}
		class="hidden"
		aria-hidden="true"
	/>

	{#if open}
		<!-- Backdrop -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="fixed inset-0 z-40" onclick={close} onkeydown={(e) => { if (e.key === 'Escape') close(); }}></div>

		<!-- Menu -->
		<div class="absolute bottom-full left-0 z-50 mb-2 w-48 overflow-hidden rounded-xl border border-border bg-surface shadow-xl">
			<button
				type="button"
				onclick={handleUploadClick}
				class="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-text-primary transition-colors hover:bg-surface-hover"
			>
				<Upload size={14} class="text-text-secondary" />
				Upload File
			</button>
			<button
				type="button"
				onclick={handlePasteClick}
				class="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-text-primary transition-colors hover:bg-surface-hover"
			>
				<Clipboard size={14} class="text-text-secondary" />
				Paste from Clipboard
			</button>
		</div>
	{/if}
</div>
