<!--
  FolderCreateModal.svelte - Modal for creating folders with name and icon.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Folder,
		Star,
		Heart,
		Briefcase,
		Code,
		BookOpen,
		Lightbulb,
		Zap,
		Globe,
		Shield,
		Coffee,
		Flame,
		Music,
		Camera,
		Palette,
		Rocket,
		Target,
		Award,
		Gift,
		MessageCircle,
		Bell,
		Hash,
		Bookmark,
		Archive,
		X
	} from 'lucide-svelte';

	// -----------------------------------------------------------------------
	// Icon options
	// -----------------------------------------------------------------------

	const ICON_OPTIONS: { name: string; component: typeof Folder }[] = [
		{ name: 'folder', component: Folder },
		{ name: 'star', component: Star },
		{ name: 'heart', component: Heart },
		{ name: 'briefcase', component: Briefcase },
		{ name: 'code', component: Code },
		{ name: 'book', component: BookOpen },
		{ name: 'lightbulb', component: Lightbulb },
		{ name: 'zap', component: Zap },
		{ name: 'globe', component: Globe },
		{ name: 'shield', component: Shield },
		{ name: 'coffee', component: Coffee },
		{ name: 'flame', component: Flame },
		{ name: 'music', component: Music },
		{ name: 'camera', component: Camera },
		{ name: 'palette', component: Palette },
		{ name: 'rocket', component: Rocket },
		{ name: 'target', component: Target },
		{ name: 'award', component: Award },
		{ name: 'gift', component: Gift },
		{ name: 'message', component: MessageCircle },
		{ name: 'bell', component: Bell },
		{ name: 'hash', component: Hash },
		{ name: 'bookmark', component: Bookmark },
		{ name: 'archive', component: Archive }
	];

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface FolderCreateModalProps {
		open: boolean;
		onClose: () => void;
		onCreate: (name: string, icon: string) => void;
	}

	let { open, onClose, onCreate }: FolderCreateModalProps = $props();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let folderName = $state('');
	let selectedIcon = $state('folder');

	// Reset state when modal opens
	$effect(() => {
		if (open) {
			folderName = '';
			selectedIcon = 'folder';
		}
	});

	let canSubmit = $derived(folderName.trim().length > 0);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	function handleSubmit() {
		if (!canSubmit) return;
		onCreate(folderName.trim(), selectedIcon);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			onClose();
		} else if (e.key === 'Enter' && canSubmit) {
			e.preventDefault();
			handleSubmit();
		}
	}
</script>

{#if open}
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
		onkeydown={handleKeydown}
	>
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<div class="fixed inset-0" onclick={onClose}></div>

		<div class="relative z-10 w-full max-w-md rounded-xl border border-border bg-surface p-6 shadow-xl">
			<!-- Header -->
			<div class="mb-4 flex items-center justify-between">
				<h2 class="text-base font-semibold text-text-primary">Create Folder</h2>
				<button
					type="button"
					onclick={onClose}
					class="rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
				>
					<X size={16} />
				</button>
			</div>

			<form
				onsubmit={(e) => { e.preventDefault(); handleSubmit(); }}
				class="flex flex-col gap-4"
			>
				<!-- Folder name input -->
				<div class="flex flex-col gap-1">
					<label for="folder-name" class="text-sm font-medium text-text-primary">
						Name <span class="text-danger">*</span>
					</label>
					<!-- svelte-ignore a11y_autofocus -->
					<input
						id="folder-name"
						type="text"
						bind:value={folderName}
						autofocus
						placeholder="e.g. Work Projects"
						class="rounded-md border border-border bg-surface-secondary px-3 py-1.5 text-sm text-text-primary placeholder:text-text-secondary/60 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
					/>
				</div>

				<!-- Icon picker -->
				<div class="flex flex-col gap-1">
					<span class="text-sm font-medium text-text-primary">Icon</span>
					<div class="grid grid-cols-6 gap-1.5">
						{#each ICON_OPTIONS as opt}
							<button
								type="button"
								onclick={() => (selectedIcon = opt.name)}
								class="flex flex-col items-center gap-0.5 rounded-md p-2 transition-colors
									{selectedIcon === opt.name
									? 'bg-accent/10 ring-2 ring-accent'
									: 'bg-surface-secondary hover:bg-surface-hover'}"
							>
								<opt.component size={18} class={selectedIcon === opt.name ? 'text-accent' : 'text-text-secondary'} />
								<span class="text-[9px] text-text-secondary">{opt.name}</span>
							</button>
						{/each}
					</div>
				</div>

				<!-- Action buttons -->
				<div class="flex items-center justify-end gap-2 pt-2">
					<button
						type="button"
						onclick={onClose}
						class="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover"
					>
						Cancel
					</button>
					<button
						type="submit"
						disabled={!canSubmit}
						class="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
					>
						Create
					</button>
				</div>
			</form>
		</div>
	</div>
{/if}
