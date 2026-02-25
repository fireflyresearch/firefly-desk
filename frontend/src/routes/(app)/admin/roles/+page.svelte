<!--
  Redirect: /admin/roles → /admin/users
  Roles are managed within the Users & Roles page.
-->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	onMount(() => {
		goto('/admin/users', { replaceState: true });
	});
</script>
