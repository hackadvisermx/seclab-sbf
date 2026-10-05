import DOMPurify from 'dompurify'
import { marked } from 'marked'

export function renderReport(markdown) {
  return DOMPurify.sanitize(marked.parse(markdown), { USE_PROFILES: { html: true }, FORBID_TAGS: ['style', 'form', 'input', 'button'], FORBID_ATTR: ['style'] })
}
