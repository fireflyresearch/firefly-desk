<!--
  FileUploadArea.svelte - Preview strip showing attached files before sending.

  Displays a horizontal scrollable strip of file preview cards with
  file type icons, truncated filenames, file sizes, and remove buttons.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { FileText, Image, X } from 'lucide-svelte';

	interface FileUploadAreaProps {
		files: File[];
		onRemove: (index: number) => void;
	}

	let { files, onRemove }: FileUploadAreaProps = $props();

	function formatSize(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	function isImage(file: File): boolean {
		return file.type.startsWith('image/');
	}

	function truncateName(name: string, maxLen: number = 24): string {
		if (name.length <= maxLen) return name;
		const ext = name.lastIndexOf('.');
		if (ext > 0 && name.length - ext <= 6) {
			const extStr = name.slice(ext);
			const base = name.slice(0, maxLen - extStr.length - 3);
			return `${base}...${extStr}`;
		}
		return name.slice(0, maxLen - 3) + '...';
	}
</script>

{#if files.length > 0}
	<div class="flex gap-2 overflow-x-auto px-4 pb-2">
		{#each files as file, index (index)}
			<div
				class="flex shrink-0 items-center gap-2 rounded-lg border border-border bg-surface-secondary px-3 py-2"
			>
				{#if isImage(file)}
					<Image size={16} class="shrink-0 text-text-secondary" />
				{:else}
					<FileText size={16} class="shrink-0 text-text-secondary" />
				{/if}
				<div class="flex flex-col">
					<span class="text-xs font-medium text-text-primary">{truncateName(file.name)}</span>
					<span class="text-xs text-text-secondary">{formatSize(file.size)}</span>
				</div>
				<button
					type="button"
					onclick={() => onRemove(index)}
					class="ml-1 shrink-0 rounded p-0.5 text-text-secondary transition-colors hover:bg-surface hover:text-text-primary"
					aria-label="Remove {file.name}"
				>
					<X size={14} />
				</button>
			</div>
		{/each}
	</div>
{/if}
