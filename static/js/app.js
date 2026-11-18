/* PTracker – app.js
   Minimal JavaScript: only confirmation dialogs. */

/**
 * Confirm before deleting a period.
 * Called inline via onsubmit on each delete form.
 */
function confirmDelete(label) {
  return window.confirm(`Delete period ${label}?\n\nThis cannot be undone.`);
}
