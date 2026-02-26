<!--
  Auth layout -- bypasses the main AppShell so login/callback pages
  render without the top bar or side panel.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	let { children } = $props();
</script>

{@render children()}
