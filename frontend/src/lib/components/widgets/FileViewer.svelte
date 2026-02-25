<!--
  FileViewer.svelte - Widget button that opens FileViewerModal on click.

  Registered as the "file_viewer" widget type. Receives file_id, file_name,
  and content_type from the backend widget payload and renders a preview
  button that launches the full-screen file viewer modal.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Eye } from 'lucide-svelte';
	import FileViewerModal from '$lib/components/chat/FileViewerModal.svelte';

	interface FileViewerProps {
		file_id: string;
		file_name: string;
		content_type: string;
	}

	let { file_id, file_name, content_type }: FileViewerProps = $props();

	let showModal = $state(false);
</script>

<button
	type="button"
	class="inline-flex items-center gap-2 rounded-xl border border-border bg-surface-elevated px-4 py-2.5 text-sm font-medium text-text-primary shadow-sm transition-all hover:shadow-md hover:bg-surface-secondary"
	onclick={() => { showModal = true; }}
>
	<Eye size={16} class="text-accent" />
	<span class="truncate max-w-xs">{file_name}</span>
</button>

{#if showModal}
	<FileViewerModal
		fileId={file_id}
		fileName={file_name}
		contentType={content_type}
		onClose={() => { showModal = false; }}
	/>
{/if}
