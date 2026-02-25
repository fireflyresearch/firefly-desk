<!--
  MessageBubble.svelte - Displays a single chat message (user or assistant).

  User messages: right-aligned bubble with accent background and user avatar.
  Assistant messages: full-width left-aligned with Ember avatar and markdown rendering.
  Timestamps appear on hover for both message types.
  Supports staggered entry animation for history messages via index/messageCount props.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { fly } from 'svelte/transition';
	import { FileText, Download } from 'lucide-svelte';
	import type { Message, MessageFile } from '$lib/stores/chat.js';
	import { currentUser } from '$lib/stores/user.js';
	import MarkdownContent from './MarkdownContent.svelte';
	import ToolSummary from './ToolSummary.svelte';
	import TokenUsage from './TokenUsage.svelte';
	import EmberAvatar from './EmberAvatar.svelte';
	import ImageLightbox from './ImageLightbox.svelte';
	import FileViewerModal from './FileViewerModal.svelte';
	import MessageActions from './MessageActions.svelte';
	import { agentSettings } from '$lib/stores/agent.js';

	interface MessageBubbleProps {
		message: Message;
		/** Position index of this message in the list (used for staggered animation). */
		index?: number;
		/** Total number of messages being rendered (used to detect batch loads). */
		messageCount?: number;
	}

	let { message, index = 0, messageCount = 1 }: MessageBubbleProps = $props();

	// Stagger delay: when multiple messages load at once (conversation switch),
	// each message gets a small incremental delay for a cascading entrance.
	// Cap at 30ms per message, max 600ms total delay to keep it snappy.
	// For single new messages (messageCount <= 2 or index near end), no delay.
	let staggerDelay = $derived(
		messageCount > 2 ? Math.min(index * 30, 600) : 0
	);

	let formattedTime = $derived(
		message.timestamp.toLocaleTimeString(undefined, {
			hour: '2-digit',
			minute: '2-digit'
		})
	);

	let isUser = $derived(message.role === 'user');

	let userInitials = $derived(
		($currentUser?.displayName ?? 'U')
			.split(' ')
			.map((part) => part[0])
			.join('')
			.toUpperCase()
			.slice(0, 2)
	);

	function isImage(file: MessageFile): boolean {
		return file.content_type.startsWith('image/');
	}

	function formatSize(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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

	// Safety-net: strip any remaining raw widget directives that were not
	// cleaned by the backend content_replace event (e.g. race condition or
	// historical messages loaded from persistence).
	const WIDGET_PATTERN = /:::widget\{[^}]+\}[\s\S]*?:::/g;
	let cleanContent = $derived((message.content ?? '').replace(WIDGET_PATTERN, '').trim());

	let lightboxSrc = $state('');
	let lightboxAlt = $state('');
	let viewerFile: { id: string; filename: string; content_type: string } | null = $state(null);

	function openLightbox(src: string, alt: string) {
		lightboxSrc = src;
		lightboxAlt = alt;
	}
</script>

{#if isUser}
	<!-- User message: right-aligned bubble -->
	<div class="group flex w-full justify-end px-4 py-1" transition:fly={{ y: 10, duration: 200, delay: staggerDelay }}>
		<div class="flex items-start gap-2">
			<div class="flex max-w-[75%] flex-col items-end">
				<div
					class="rounded-2xl rounded-br-sm bg-accent/90 backdrop-blur-sm px-4 py-2.5 text-sm leading-relaxed text-white shadow-sm whitespace-pre-wrap break-words"
				>
					{message.content}
				</div>
			{#if message.files?.length}
				<div class="mt-1.5 flex flex-wrap justify-end gap-1.5">
					{#each message.files as file (file.id)}
						{#if isImage(file)}
							<div
								class="group/file flex items-center gap-2 rounded-lg border border-border bg-surface px-2.5 py-1.5 transition-colors hover:bg-surface-secondary"
							>
								<button type="button" class="block shrink-0" onclick={() => { viewerFile = { id: file.id, filename: file.filename, content_type: file.content_type }; }}>
									<img
										src="/api/files/{file.id}/download"
										alt={file.filename}
										class="h-20 w-auto max-w-48 rounded-lg object-cover cursor-pointer hover:shadow-md transition-shadow"
									/>
								</button>
								<div class="flex flex-col">
									<span class="text-xs font-medium text-text-primary">{truncateName(file.filename)}</span>
									<span class="text-xs text-text-secondary">{formatSize(file.file_size)}</span>
								</div>
								<a
									href="/api/files/{file.id}/download"
									target="_blank"
									rel="noopener noreferrer"
									class="shrink-0"
								>
									<Download size={14} class="text-text-secondary opacity-0 transition-opacity group-hover/file:opacity-100" />
								</a>
							</div>
						{:else}
							<button
								type="button"
								class="group/file flex items-center gap-2 rounded-lg border border-border bg-surface px-2.5 py-1.5 transition-colors hover:bg-surface-secondary"
								onclick={() => { viewerFile = { id: file.id, filename: file.filename, content_type: file.content_type }; }}
							>
								<FileText size={16} class="shrink-0 text-text-secondary" />
								<div class="flex flex-col text-left">
									<span class="text-xs font-medium text-text-primary">{truncateName(file.filename)}</span>
									<span class="text-xs text-text-secondary">{formatSize(file.file_size)}</span>
								</div>
								<Download size={14} class="shrink-0 text-text-secondary opacity-0 transition-opacity group-hover/file:opacity-100" />
							</button>
						{/if}
					{/each}
				</div>
			{/if}
			<span
				class="mt-1 px-1 text-xs text-text-secondary opacity-0 transition-opacity group-hover:opacity-100"
			>
				{formattedTime}
			</span>
			</div>
			<!-- User avatar -->
			<div class="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full overflow-hidden">
				{#if $currentUser?.pictureUrl}
					<img
						src={$currentUser.pictureUrl}
						alt={$currentUser.displayName}
						class="h-7 w-7 rounded-full object-cover"
					/>
				{:else}
					<div class="flex h-7 w-7 items-center justify-center rounded-full bg-accent text-[10px] font-medium text-white select-none">
						{userInitials}
					</div>
				{/if}
			</div>
		</div>
	</div>
{:else}
	<!-- Assistant message: full-width left-aligned, no bubble background -->
	<div class="group flex w-full justify-start px-4 py-1" transition:fly={{ y: 10, duration: 200, delay: staggerDelay }}>
		<div class="flex gap-3">
			<!-- Agent avatar (custom or default Ember) -->
			<div class="mt-0.5 flex shrink-0 flex-col items-center">
				<div class="flex h-7 w-7 items-center justify-center overflow-hidden rounded-full">
					{#if $agentSettings.avatar_url}
						<img
							src={$agentSettings.avatar_url}
							alt={$agentSettings.display_name || 'Assistant'}
							class="h-7 w-7 rounded-full object-cover"
						/>
					{:else}
						<EmberAvatar size={20} />
					{/if}
				</div>
				<span class="mt-0.5 text-center text-[9px] font-medium text-text-secondary">
					{$agentSettings.display_name || 'Ember'}
				</span>
			</div>
			<!-- Message content -->
			<div class="flex flex-col items-start">
				<div class="rounded-2xl rounded-bl-sm bg-surface-secondary/50 px-4 py-2.5 text-sm leading-relaxed">
					<MarkdownContent content={cleanContent} />
				</div>
				{#if !message.isStreaming && message.toolExecutions?.length}
					<ToolSummary tools={message.toolExecutions} />
				{/if}
				{#if !message.isStreaming && message.usage}
					<TokenUsage usage={message.usage} />
				{/if}
				{#if !message.isStreaming && $currentUser?.devMode && message.toolCount !== undefined}
					<span class="mt-0.5 rounded bg-surface-secondary px-1.5 py-0.5 font-mono text-[10px] text-text-secondary" title="Number of tools available to the agent">
						{message.toolCount} tools
					</span>
				{/if}
				<div class="mt-1 flex items-center gap-2">
					<span
						class="px-1 text-xs text-text-secondary opacity-0 transition-opacity group-hover:opacity-100"
					>
						{formattedTime}
					</span>
					{#if !message.isStreaming}
						<MessageActions messageId={message.id} content={message.content} />
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}

{#if lightboxSrc}
	<ImageLightbox src={lightboxSrc} alt={lightboxAlt} onclose={() => { lightboxSrc = ''; }} />
{/if}

{#if viewerFile}
	<FileViewerModal
		fileId={viewerFile.id}
		fileName={viewerFile.filename}
		contentType={viewerFile.content_type}
		onClose={() => { viewerFile = null; }}
	/>
{/if}
