<!--
  ChartWidget.svelte - Renders Chart.js charts in the chat.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Chart, registerables } from 'chart.js';

	Chart.register(...registerables);

	interface ChartDataset {
		label: string;
		data: number[];
		backgroundColor?: string | string[];
		borderColor?: string | string[];
		borderWidth?: number;
	}

	interface ChartWidgetProps {
		chartType?: string;
		title?: string;
		labels?: string[];
		datasets?: ChartDataset[];
		options?: Record<string, unknown>;
	}

	let {
		chartType = 'bar',
		title,
		labels = [],
		datasets = [],
		options = {}
	}: ChartWidgetProps = $props();

	let canvas: HTMLCanvasElement;
	let chart: Chart | null = null;

	// Default color palette -- warm industrial theme
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

	function applyDefaultColors(ds: ChartDataset[], type: string): ChartDataset[] {
		return ds.map((dataset, i) => {
			const color = PALETTE[i % PALETTE.length];
			const copy = { ...dataset };

			if (type === 'pie' || type === 'doughnut' || type === 'polarArea') {
				// Each segment gets its own color
				if (!copy.backgroundColor) {
					copy.backgroundColor = copy.data.map((_, j) => PALETTE[j % PALETTE.length]);
				}
				if (!copy.borderColor) {
					copy.borderColor = 'transparent';
				}
			} else {
				if (!copy.backgroundColor) {
					copy.backgroundColor = color + '80'; // 50% opacity for fills
				}
				if (!copy.borderColor) {
					copy.borderColor = color;
				}
				if (copy.borderWidth === undefined) {
					copy.borderWidth = 2;
				}
			}
			return copy;
		});
	}

	function deepMerge(target: Record<string, unknown>, source: Record<string, unknown>): Record<string, unknown> {
		const result: Record<string, unknown> = { ...target };
		for (const key of Object.keys(source)) {
			const sourceVal = source[key];
			if (sourceVal && typeof sourceVal === 'object' && !Array.isArray(sourceVal)) {
				result[key] = deepMerge(
					(result[key] as Record<string, unknown>) || {},
					sourceVal as Record<string, unknown>
				);
			} else {
				result[key] = sourceVal;
			}
		}
		return result;
	}

	/** Read a CSS custom property from :root and return it as a color string. */
	function cssVar(name: string, fallback: string): string {
		if (typeof document === 'undefined') return fallback;
		const val = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
		return val || fallback;
	}

	$effect(() => {
		if (!canvas) return;

		// Destroy previous chart
		if (chart) {
			chart.destroy();
			chart = null;
		}

		const resolvedType = chartType as
			| 'bar'
			| 'line'
			| 'pie'
			| 'doughnut'
			| 'radar'
			| 'polarArea';
		const coloredDatasets = applyDefaultColors(datasets, resolvedType);

		// Resolve theme colors from CSS custom properties
		const textSecondary = cssVar('--color-text-secondary', 'rgba(255,255,255,0.5)');
		const textMuted = cssVar('--color-text-secondary', 'rgba(255,255,255,0.7)');
		const gridColor = cssVar('--color-border', 'rgba(255,255,255,0.06)');

		// Theme-aware defaults using CSS custom properties
		const defaultOptions: Record<string, unknown> = {
			responsive: true,
			maintainAspectRatio: true,
			plugins: {
				legend: {
					labels: {
						color: textMuted,
						font: {
							family: "'Plus Jakarta Sans Variable', system-ui, sans-serif",
							size: 12
						}
					}
				},
				title: {
					display: false // we show title in the card header
				}
			},
			scales: {}
		};

		// Add scale colors for non-radial charts
		if (!['pie', 'doughnut', 'polarArea', 'radar'].includes(resolvedType)) {
			(defaultOptions as Record<string, unknown>).scales = {
				x: {
					ticks: { color: textSecondary, font: { size: 11 } },
					grid: { color: gridColor }
				},
				y: {
					ticks: { color: textSecondary, font: { size: 11 } },
					grid: { color: gridColor }
				}
			};
		}

		if (resolvedType === 'radar') {
			(defaultOptions as Record<string, unknown>).scales = {
				r: {
					ticks: { color: textSecondary, backdropColor: 'transparent' },
					grid: { color: gridColor },
					pointLabels: { color: textMuted }
				}
			};
		}

		// Deep merge user options over defaults
		const mergedOptions = deepMerge(defaultOptions, options);

		chart = new Chart(canvas, {
			type: resolvedType,
			data: {
				labels,
				datasets: coloredDatasets
			},
			options: mergedOptions as import('chart.js').ChartOptions
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
		<canvas bind:this={canvas}></canvas>
	</div>
</div>
