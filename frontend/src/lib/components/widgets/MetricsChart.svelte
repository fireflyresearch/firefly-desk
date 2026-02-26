<!--
  MetricsChart.svelte - Time-series metrics display using Chart.js.

  Renders line, bar, or area charts for OpenTelemetry-style metric data
  with time-series formatting on the x-axis. Uses the same PALETTE as
  ChartWidget for visual consistency.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Chart, registerables } from 'chart.js';

	Chart.register(...registerables);

	interface MetricSample {
		timestamp: string | number;
		value: number;
	}

	interface MetricSeries {
		name: string;
		values: MetricSample[];
		unit?: string;
	}

	interface MetricsChartProps {
		title?: string;
		metrics?: MetricSeries[];
		chartType?: 'line' | 'bar' | 'area';
	}

	let {
		title,
		metrics = [],
		chartType = 'line'
	}: MetricsChartProps = $props();

	let canvas = $state<HTMLCanvasElement>();
	let chart: Chart | null = null;

	// Shared palette from ChartWidget
	const PALETTE = [
		'#f59e0b', // ember
		'#3b82f6', // accent/blue
		'#22c55e', // success/green
		'#ef4444', // danger/red
		'#8b5cf6', // violet
		'#6b7280', // gray
		'#f97316', // orange
		'#14b8a6' // teal
	];

	/** Read a CSS custom property from :root. */
	function cssVar(name: string, fallback: string): string {
		if (typeof document === 'undefined') return fallback;
		const val = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
		return val || fallback;
	}

	/** Format a timestamp for x-axis display. */
	function formatTimestamp(ts: string | number): string {
		const d = new Date(ts);
		if (isNaN(d.getTime())) return String(ts);
		// Show hours:minutes if within a day range, otherwise date
		return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
	}

	$effect(() => {
		if (!canvas) return;

		if (chart) {
			chart.destroy();
			chart = null;
		}

		if (metrics.length === 0) return;

		// Build a unified set of labels from all metric timestamps
		const allTimestamps = new Set<string>();
		for (const metric of metrics) {
			for (const sample of metric.values) {
				allTimestamps.add(String(sample.timestamp));
			}
		}
		const sortedTimestamps = Array.from(allTimestamps).sort((a, b) => {
			const da = new Date(a).getTime();
			const db = new Date(b).getTime();
			if (!isNaN(da) && !isNaN(db)) return da - db;
			return a.localeCompare(b);
		});
		const labels = sortedTimestamps.map(formatTimestamp);

		// Build datasets
		const isArea = chartType === 'area';
		const resolvedType = isArea ? 'line' : chartType;

		const datasets = metrics.map((metric, i) => {
			const color = PALETTE[i % PALETTE.length];
			// Map values by timestamp for alignment
			const valueMap = new Map<string, number>();
			for (const sample of metric.values) {
				valueMap.set(String(sample.timestamp), sample.value);
			}
			const data = sortedTimestamps.map((ts) => valueMap.get(ts) ?? NaN);

			return {
				label: metric.unit ? `${metric.name} (${metric.unit})` : metric.name,
				data,
				borderColor: color,
				backgroundColor: isArea ? color + '30' : color + '80',
				borderWidth: 2,
				fill: isArea,
				tension: 0.3,
				pointRadius: 3,
				pointHoverRadius: 5,
				spanGaps: true
			};
		});

		// Theme colors
		const textSecondary = cssVar('--color-text-secondary', 'rgba(255,255,255,0.5)');
		const gridColor = cssVar('--color-border', 'rgba(255,255,255,0.06)');

		chart = new Chart(canvas, {
			type: resolvedType,
			data: { labels, datasets },
			options: {
				responsive: true,
				maintainAspectRatio: true,
				interaction: {
					mode: 'index',
					intersect: false
				},
				plugins: {
					legend: {
						labels: {
							color: textSecondary,
							font: {
								family: "'Plus Jakarta Sans Variable', system-ui, sans-serif",
								size: 12
							}
						}
					},
					title: {
						display: false
					},
					tooltip: {
						mode: 'index',
						intersect: false
					}
				},
				scales: {
					x: {
						ticks: {
							color: textSecondary,
							font: { size: 10 },
							maxRotation: 45,
							autoSkip: true,
							maxTicksLimit: 12
						},
						grid: { color: gridColor }
					},
					y: {
						ticks: {
							color: textSecondary,
							font: { size: 11 }
						},
						grid: { color: gridColor }
					}
				}
			}
		});

		return () => {
			if (chart) {
				chart.destroy();
				chart = null;
			}
		};
	});
</script>

<div class="rounded-xl border border-border bg-surface-elevated shadow-sm overflow-hidden">
	{#if title}
		<div class="border-b border-border px-4 py-3">
			<h3 class="text-sm font-semibold text-text-primary">{title}</h3>
		</div>
	{/if}
	<div class="p-4">
		{#if metrics.length > 0}
			<canvas bind:this={canvas}></canvas>
		{:else}
			<div class="flex items-center justify-center py-8">
				<span class="text-xs text-text-secondary">No metrics to display</span>
			</div>
		{/if}
	</div>
</div>
