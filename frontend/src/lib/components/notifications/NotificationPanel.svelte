<!--
  NotificationPanel.svelte - Dropdown panel showing recent job & workflow activity.

  Renders a list of notifications with status icons, progress bars, and
  dismiss actions.  Opens as an absolutely-positioned dropdown anchored
  below the trigger (typically a Bell icon in the TopBar).

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Bell, X, CheckCircle, AlertCircle, Loader2, Clock, Activity } from 'lucide-svelte';
	import {
		fetchNotifications,
		dismissNotification,
		type AppNotification
	} from '$lib/services/notifications.js';

	interface NotificationPanelProps {
		open?: boolean;
		onclose?: () => void;
	}

	let { open = false, onclose }: NotificationPanelProps = $props();

	let notifications = $state<AppNotification[]>([]);
	let loading = $state(false);

	// Load notifications when panel opens
	$effect(() => {
		if (open) {
			loadNotifications();
		}
	});

	async function loadNotifications() {
		loading = true;
		try {
			notifications = await fetchNotifications();
		} catch (e) {
			console.error('Failed to load notifications', e);
		} finally {
			loading = false;
		}
	}

	async function handleDismiss(event: MouseEvent, id: string) {
		event.stopPropagation();
		try {
			await dismissNotification(id);
			notifications = notifications.filter((n) => n.id !== id);
		} catch (e) {
			console.error('Failed to dismiss notification', e);
		}
	}

	async function clearAll() {
		try {
			await Promise.all(notifications.map((n) => dismissNotification(n.id)));
			notifications = [];
		} catch (e) {
			console.error('Failed to clear notifications', e);
		}
	}

	/**
	 * Format a timestamp string into a human-readable relative time.
	 */
	function relativeTime(iso: string | null): string {
		if (!iso) return '';
		const now = Date.now();
		const then = new Date(iso).getTime();
		const diffSec = Math.floor((now - then) / 1000);

		if (diffSec < 60) return 'just now';
		const diffMin = Math.floor(diffSec / 60);
		if (diffMin < 60) return `${diffMin}m ago`;
		const diffHr = Math.floor(diffMin / 60);
		if (diffHr < 24) return `${diffHr}h ago`;
		const diffDay = Math.floor(diffHr / 24);
		return `${diffDay}d ago`;
	}

	/** Map status to a human-readable label. */
	function statusLabel(status: AppNotification['status']): string {
		const labels: Record<AppNotification['status'], string> = {
			pending: 'Pending',
			running: 'Running',
			completed: 'Completed',
			failed: 'Failed'
		};
		return labels[status];
	}
</script>

{#if open}
	<!-- Backdrop for click-outside dismiss -->
	<button
		type="button"
		class="fixed inset-0 z-40"
		onclick={onclose}
		aria-label="Close notifications"
		tabindex="-1"
	></button>

	<div
		class="absolute right-0 top-full z-50 mt-1 w-96 rounded-lg border border-border bg-surface shadow-lg"
		role="region"
		aria-label="Notifications"
	>
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-border px-4 py-3">
			<h3 class="text-sm font-semibold text-text-primary">Notifications</h3>
			{#if notifications.length > 0}
				<button
					type="button"
					onclick={clearAll}
					class="text-xs text-text-secondary transition-colors hover:text-text-primary"
				>
					Clear all
				</button>
			{/if}
		</div>

		<!-- Body -->
		<div class="max-h-96 overflow-y-auto">
			{#if loading}
				<!-- Loading state -->
				<div class="flex items-center justify-center py-12">
					<Loader2 size={20} class="animate-spin text-text-secondary" />
				</div>
			{:else if notifications.length === 0}
				<!-- Empty state -->
				<div class="flex flex-col items-center justify-center py-12 text-text-secondary">
					<Bell size={24} class="mb-2 opacity-40" />
					<p class="text-sm">No recent activity</p>
				</div>
			{:else}
				<!-- Notification list -->
				<ul class="divide-y divide-border">
					{#each notifications as notification (notification.id)}
						<li class="group flex items-start gap-3 px-4 py-3 transition-colors hover:bg-surface-secondary">
							<!-- Status icon -->
							<div class="mt-0.5 shrink-0">
								{#if notification.status === 'pending'}
									<Clock size={16} class="text-text-secondary" />
								{:else if notification.status === 'running'}
									<Loader2 size={16} class="animate-spin text-amber-500" />
								{:else if notification.status === 'completed'}
									<CheckCircle size={16} class="text-green-500" />
								{:else if notification.status === 'failed'}
									<AlertCircle size={16} class="text-red-500" />
								{/if}
							</div>

							<!-- Content -->
							<div class="min-w-0 flex-1">
								<div class="flex items-center gap-2">
									<span class="truncate text-sm font-medium text-text-primary">
										{notification.title}
									</span>
									<span
										class="shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium
										{notification.status === 'pending'
											? 'border border-border bg-surface-secondary text-text-secondary'
											: notification.status === 'running'
												? 'border border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400'
												: notification.status === 'completed'
													? 'border border-green-500/30 bg-green-500/10 text-green-600 dark:text-green-400'
													: 'border border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400'}"
									>
										{statusLabel(notification.status)}
									</span>
								</div>

								<!-- Progress bar (only for running status with defined progress) -->
								{#if notification.status === 'running' && notification.progress != null}
									<div class="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-surface-secondary">
										<div
											class="h-full rounded-full bg-amber-500 transition-all duration-300"
											style="width: {notification.progress}%"
										></div>
									</div>
								{/if}

								<!-- Timestamp -->
								<span class="mt-1 block text-xs text-text-secondary">
									{relativeTime(notification.updated_at ?? notification.created_at)}
								</span>
							</div>

							<!-- Dismiss button -->
							<button
								type="button"
								onclick={(e) => handleDismiss(e, notification.id)}
								class="mt-0.5 shrink-0 rounded-md p-0.5 text-text-secondary opacity-0 transition-all hover:bg-surface-hover hover:text-text-primary group-hover:opacity-100"
								aria-label="Dismiss notification"
							>
								<X size={14} />
							</button>
						</li>
					{/each}
				</ul>
			{/if}
		</div>

		<!-- Footer -->
		<div class="border-t border-border px-4 py-2.5 text-center">
			<a
				href="/admin/jobs"
				class="inline-flex items-center gap-1.5 text-sm text-text-secondary transition-colors hover:text-accent"
				onclick={onclose}
			>
				<Activity size={14} />
				View all jobs &rarr;
			</a>
		</div>
	</div>
{/if}
