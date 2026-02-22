<!--
  EmberAvatar.svelte - Warm ember/firefly glow avatar for the Ember assistant.

  Renders a small SVG firefly icon with a warm amber-orange glow effect.
  Used in MessageBubble for assistant messages and ChatEmptyState greeting.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	interface EmberAvatarProps {
		/** Width and height in pixels. */
		size?: number;
	}

	let { size = 24 }: EmberAvatarProps = $props();
</script>

<svg
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	xmlns="http://www.w3.org/2000/svg"
	aria-label="Ember"
	role="img"
>
	<defs>
		<!-- Outer ambient glow -->
		<radialGradient id="ember-glow-outer" cx="50%" cy="50%" r="50%">
			<stop offset="0%" stop-color="#f59e0b" stop-opacity="0.35" />
			<stop offset="100%" stop-color="#f59e0b" stop-opacity="0" />
		</radialGradient>
		<!-- Inner core glow -->
		<radialGradient id="ember-glow-inner" cx="50%" cy="45%" r="40%">
			<stop offset="0%" stop-color="#fbbf24" stop-opacity="0.9" />
			<stop offset="60%" stop-color="#f59e0b" stop-opacity="0.6" />
			<stop offset="100%" stop-color="#d97706" stop-opacity="0" />
		</radialGradient>
	</defs>

	<!-- Ambient glow circle -->
	<circle cx="12" cy="12" r="11" fill="url(#ember-glow-outer)" />

	<!-- Body: stylized firefly shape -->
	<ellipse cx="12" cy="13" rx="3.2" ry="4.5" fill="#d97706" opacity="0.85" />

	<!-- Inner ember core -->
	<ellipse cx="12" cy="11.5" rx="2" ry="2.8" fill="url(#ember-glow-inner)" />

	<!-- Bright center spark -->
	<circle cx="12" cy="10.5" r="1.1" fill="#fde68a" opacity="0.95" />

	<!-- Wings -->
	<path
		d="M8.8 10.5 C7 8.5, 5.5 9.5, 5.5 11 C5.5 12.5, 7.5 13, 8.8 12"
		fill="#fbbf24"
		opacity="0.4"
	/>
	<path
		d="M15.2 10.5 C17 8.5, 18.5 9.5, 18.5 11 C18.5 12.5, 16.5 13, 15.2 12"
		fill="#fbbf24"
		opacity="0.4"
	/>

	<!-- Antennae -->
	<line x1="10.5" y1="8.5" x2="9" y2="5.5" stroke="#d97706" stroke-width="0.6" stroke-linecap="round" />
	<line x1="13.5" y1="8.5" x2="15" y2="5.5" stroke="#d97706" stroke-width="0.6" stroke-linecap="round" />
	<circle cx="9" cy="5.5" r="0.6" fill="#fbbf24" />
	<circle cx="15" cy="5.5" r="0.6" fill="#fbbf24" />
</svg>
