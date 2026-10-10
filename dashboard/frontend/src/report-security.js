import DOMPurify from 'dompurify'
import { marked } from 'marked'

export function renderReport(markdown) {
  return DOMPurify.sanitize(marked.parse(markdown), { USE_PROFILES: { html: true }, FORBID_TAGS: ['style', 'form', 'input', 'button'], FORBID_ATTR: ['style'] })
}

// Only the compiler's local, versioned source links open the artifact viewer.
export function reportArtifactReference(href) {
  if (typeof href !== 'string') return null
  const match = /^\.\/([^?#]+)#sha256=([a-f0-9]{64})$/.exec(href)
  if (!match) return null
  let path
  try { path = decodeURIComponent(match[1]) } catch { return null }
  if (!/^(evidence|recon|fuzzing|screenshots)\//.test(path) || /[\\?#\x00-\x1f]/.test(path) || path.split('/').some(part => !part || part === '.' || part === '..')) return null
  return { path, sha256: match[2] }
}
