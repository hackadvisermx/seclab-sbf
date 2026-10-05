import { createHash } from 'node:crypto'
import { mkdir, rm, writeFile } from 'node:fs/promises'
import { execFileSync } from 'node:child_process'

const packages = [
  ['npm', '12.2.0', 'ZsJjKpTnlmSXOLLXiU1xDCzC4Wlok4IwZmh/aw2KUuXytU7q6qMv/cUT7MoeSf95Slwuw/lRXYefGzGCspHPNQ=='],
  ['brace-expansion', '5.0.11', 'awigjhi6cLTh90bdw6+QJ9CtmJmyYhEIi70iCbc8Rozn04Fw9FeQIBjv/E22FFGuCGx1bLJyUfB64x/szUSXUg=='],
  ['undici', '6.28.1', 'zWpdTVD54H48CIybL0rWQ3ukpb9d23wM7eH5RtfdmeP70cWHNjtfo7P4vZX+5CoDcO53J4Pu5uXp7lNfjc6DRA=='],
]

for (const [name, version, integrity] of packages) {
  const response = await fetch(`https://registry.npmjs.org/${name}/-/${name}-${version}.tgz`)
  if (!response.ok) throw new Error(`Download failed: ${name}`)
  const data = Buffer.from(await response.arrayBuffer())
  if (createHash('sha512').update(data).digest('base64') !== integrity) {
    throw new Error(`Integrity mismatch: ${name}`)
  }
  const archive = `/tmp/seclab-${name}.tgz`
  await writeFile(archive, data)
  if (name === 'npm') {
    execFileSync('npm', ['install', '--global', archive, '--ignore-scripts', '--no-audit', '--no-fund'], { stdio: 'inherit' })
  } else {
    const destination = `/usr/local/lib/node_modules/npm/node_modules/${name}`
    await rm(destination, { recursive: true, force: true })
    await mkdir(destination, { recursive: true })
    execFileSync('tar', ['-xzf', archive, '--strip-components=1', '--no-same-owner', '-C', destination], { stdio: 'inherit' })
  }
  await rm(archive)
}
await rm('/root/.npm', { recursive: true, force: true })
