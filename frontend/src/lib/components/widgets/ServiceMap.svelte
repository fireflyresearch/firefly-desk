<!--
  ServiceMap.svelte - Service dependency visualization as a node-link diagram.

  Renders services as nodes in a circular layout with connection arrows
  showing dependencies, request rates, and error rates. Pure SVG
  implementation with no external libraries.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	interface ServiceNode {
		id: string;
		name: string;
		status?: string;
	}

	interface ServiceConnection {
		source: string;
		target: string;
		requestRate?: number | string;
		errorRate?: number | string;
	}

	interface ServiceMapProps {
		services: ServiceNode[];
		connections: ServiceConnection[];
		title?: string;
	}

	let { services, connections, title }: ServiceMapProps = $props();

	// Unique ID per instance to prevent SVG marker ID collisions when
	// multiple ServiceMap widgets are rendered on the same page.
	const instanceId = Math.random().toString(36).slice(2, 10);

	// -----------------------------------------------------------------
	// Layout: circular placement
	// -----------------------------------------------------------------

	const SVG_WIDTH = 600;
	const SVG_HEIGHT = 400;
	const CENTER_X = SVG_WIDTH / 2;
	const CENTER_Y = SVG_HEIGHT / 2;
	const RADIUS_X = 220;
	const RADIUS_Y = 140;
	const NODE_RADIUS = 28;

	interface PositionedNode extends ServiceNode {
		x: number;
		y: number;
	}

	let positionedNodes = $derived.by<PositionedNode[]>(() => {
		const count = services.length;
		if (count === 0) return [];
		if (count === 1) {
			return [{ ...services[0], x: CENTER_X, y: CENTER_Y }];
		}
		return services.map((svc, i) => {
			const angle = (2 * Math.PI * i) / count - Math.PI / 2;
			return {
				...svc,
				x: CENTER_X + RADIUS_X * Math.cos(angle),
				y: CENTER_Y + RADIUS_Y * Math.sin(angle)
			};
		});
	});

	// Build a lookup for node positions
	let nodeMap = $derived(
		new Map(positionedNodes.map((n) => [n.id, n]))
	);

	// -----------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------

	function statusColor(status?: string): string {
		if (!status) return 'var(--color-accent, #3b82f6)';
		const s = status.toLowerCase();
		if (s === 'healthy' || s === 'ok' || s === 'success') return 'var(--color-success, #22c55e)';
		if (s === 'error' || s === 'unhealthy' || s === 'critical') return 'var(--color-danger, #ef4444)';
		if (s === 'warning' || s === 'degraded') return 'var(--color-warning, #f59e0b)';
		return 'var(--color-accent, #3b82f6)';
	}

	/** Compute edge path with an offset to avoid overlapping the node circles. */
	function edgePath(conn: ServiceConnection): string {
		const src = nodeMap.get(conn.source);
		const tgt = nodeMap.get(conn.target);
		if (!src || !tgt) return '';
		const dx = tgt.x - src.x;
		const dy = tgt.y - src.y;
		const dist = Math.sqrt(dx * dx + dy * dy) || 1;
		const ux = dx / dist;
		const uy = dy / dist;
		// Offset start/end to circle border
		const x1 = src.x + ux * (NODE_RADIUS + 2);
		const y1 = src.y + uy * (NODE_RADIUS + 2);
		const x2 = tgt.x - ux * (NODE_RADIUS + 6);
		const y2 = tgt.y - uy * (NODE_RADIUS + 6);
		return `M ${x1} ${y1} L ${x2} ${y2}`;
	}

	/** Midpoint for edge labels. */
	function edgeMidpoint(conn: ServiceConnection): { x: number; y: number } {
		const src = nodeMap.get(conn.source);
		const tgt = nodeMap.get(conn.target);
		if (!src || !tgt) return { x: 0, y: 0 };
		return { x: (src.x + tgt.x) / 2, y: (src.y + tgt.y) / 2 };
	}

	function edgeLabel(conn: ServiceConnection): string {
		const parts: string[] = [];
		if (conn.requestRate !== undefined) parts.push(`${conn.requestRate} req/s`);
		if (conn.errorRate !== undefined) parts.push(`${conn.errorRate}% err`);
		return parts.join(' | ');
	}

	function hasErrorRate(conn: ServiceConnection): boolean {
		if (conn.errorRate === undefined) return false;
		const rate = typeof conn.errorRate === 'string' ? parseFloat(conn.errorRate) : conn.errorRate;
		return rate > 0;
	}
</script>

<div class="rounded-xl border border-border bg-surface-elevated shadow-sm overflow-hidden">
	{#if title}
		<div class="border-b border-border px-4 py-3">
			<h3 class="text-sm font-semibold text-text-primary">{title}</h3>
		</div>
	{/if}

	<div class="p-4">
		{#if services.length > 0}
			<svg
				viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}"
				class="w-full h-auto"
				xmlns="http://www.w3.org/2000/svg"
			>
				<!-- Arrowhead marker -->
				<defs>
					<marker
						id="arrowhead-{instanceId}"
						markerWidth="8"
						markerHeight="6"
						refX="7"
						refY="3"
						orient="auto"
					>
						<polygon
							points="0 0, 8 3, 0 6"
							class="fill-text-secondary"
						/>
					</marker>
					<marker
						id="arrowhead-error-{instanceId}"
						markerWidth="8"
						markerHeight="6"
						refX="7"
						refY="3"
						orient="auto"
					>
						<polygon
							points="0 0, 8 3, 0 6"
							class="fill-danger"
						/>
					</marker>
				</defs>

				<!-- Connections -->
				{#each connections as conn}
					{@const path = edgePath(conn)}
					{@const mid = edgeMidpoint(conn)}
					{@const label = edgeLabel(conn)}
					{@const isError = hasErrorRate(conn)}
					{#if path}
						<path
							d={path}
							fill="none"
							stroke-width="1.5"
							class={isError ? 'stroke-danger/60' : 'stroke-text-secondary/40'}
							marker-end={isError ? `url(#arrowhead-error-${instanceId})` : `url(#arrowhead-${instanceId})`}
						/>
						{#if label}
							<text
								x={mid.x}
								y={mid.y - 6}
								text-anchor="middle"
								class="fill-text-secondary"
								font-size="9"
								font-family="'Plus Jakarta Sans Variable', system-ui, sans-serif"
							>
								{label}
							</text>
						{/if}
					{/if}
				{/each}

				<!-- Service nodes -->
				{#each positionedNodes as node}
					<!-- Node circle -->
					<circle
						cx={node.x}
						cy={node.y}
						r={NODE_RADIUS}
						fill={statusColor(node.status) + '18'}
						stroke={statusColor(node.status)}
						stroke-width="2"
					/>
					<!-- Node label -->
					<text
						x={node.x}
						y={node.y + 1}
						text-anchor="middle"
						dominant-baseline="middle"
						class="fill-text-primary"
						font-size="10"
						font-weight="600"
						font-family="'Plus Jakarta Sans Variable', system-ui, sans-serif"
					>
						{node.name.length > 12 ? node.name.substring(0, 11) + '\u2026' : node.name}
					</text>
					<!-- Status indicator dot -->
					{#if node.status}
						<circle
							cx={node.x + NODE_RADIUS * 0.6}
							cy={node.y - NODE_RADIUS * 0.6}
							r="4"
							fill={statusColor(node.status)}
							stroke="var(--color-surface-elevated, #1a1a1a)"
							stroke-width="1.5"
						/>
					{/if}
				{/each}
			</svg>
		{:else}
			<div class="flex items-center justify-center py-8">
				<span class="text-xs text-text-secondary">No services to display</span>
			</div>
		{/if}
	</div>
</div>
