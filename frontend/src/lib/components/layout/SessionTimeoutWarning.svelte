<script>
  let { onExtend, onLogout } = $props();
</script>

<div class="session-timeout-overlay">
  <div class="session-timeout-modal">
    <h3>Session Expiring</h3>
    <p>Your session will expire in 5 minutes due to inactivity.</p>
    <div class="session-timeout-actions">
      <button class="btn-extend" onclick={onExtend}>Extend Session</button>
      <button class="btn-logout" onclick={onLogout}>Logout</button>
    </div>
  </div>
</div>

<style>
  .session-timeout-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
  }

  .session-timeout-modal {
    background: var(--bg-surface, #fff);
    border-radius: 12px;
    padding: 2rem;
    max-width: 400px;
    text-align: center;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  }

  h3 {
    margin: 0 0 0.5rem;
    font-size: 1.25rem;
  }

  p {
    margin: 0 0 1.5rem;
    color: var(--text-secondary, #6b7280);
  }

  .session-timeout-actions {
    display: flex;
    gap: 1rem;
    justify-content: center;
  }

  .btn-extend {
    padding: 0.5rem 1.5rem;
    border-radius: 8px;
    background: var(--color-primary, #3b82f6);
    color: white;
    border: none;
    cursor: pointer;
    font-weight: 500;
  }

  .btn-extend:hover {
    opacity: 0.9;
  }

  .btn-logout {
    padding: 0.5rem 1.5rem;
    border-radius: 8px;
    background: transparent;
    border: 1px solid var(--border-color, #e5e7eb);
    cursor: pointer;
    color: var(--text-primary, #111);
  }

  .btn-logout:hover {
    background: var(--bg-hover, #f3f4f6);
  }
</style>
