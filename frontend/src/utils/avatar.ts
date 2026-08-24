/**
 * Avatar URL helpers.
 *
 * Uploaded avatars are served from an internal route (`/api/files/avatars/...`).
 * Showing that path in the "online URL" input leaks the server storage layout,
 * so the UI must never prefill internal paths into the URL field.
 */

/** True when the avatar is an internally uploaded file (not an external URL). */
export function isUploadedAvatar(url?: string | null): boolean {
  if (!url) return false
  return !/^https?:\/\//i.test(url.trim())
}

/** True when the string is a valid external image URL (http/https or empty). */
export function isExternalImageUrl(url: string): boolean {
  const v = url.trim()
  if (!v) return true
  return /^https?:\/\//i.test(v)
}

/** Value to prefill the "online URL" field: never expose internal paths. */
export function avatarUrlInputValue(url?: string | null): string {
  return isUploadedAvatar(url) ? '' : (url || '')
}
