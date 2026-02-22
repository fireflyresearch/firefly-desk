<!--
  DropOverlay.svelte - Visual overlay for file drag-and-drop.

  Displays a full overlay with dashed border and upload icon when
  files are being dragged over the chat area.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Upload } from 'lucide-svelte';
</script>

<div
	class="absolute inset-0 z-50 flex items-center justify-center rounded-xl border-2 border-dashed border-accent bg-accent/10"
>
	<div class="text-center">
		<Upload size={48} class="mx-auto text-accent" />
		<p class="mt-2 text-sm font-medium text-accent">Drop files here</p>
	</div>
</div>
