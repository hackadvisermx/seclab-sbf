import { createServer } from 'node:net'
import { spawn } from 'node:child_process'
import { mkdtemp, mkdir, writeFile, chmod, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { randomBytes } from 'node:crypto'

const credentialsDir = fileURLToPath(new URL('./.playwright-fixture/', import.meta.url))
const name = `seclab-playwright-${process.pid}-${randomBytes(4).toString('hex')}`
const image = process.env.PLAYWRIGHT_LAB_IMAGE || 'seclab-sbf:full-phase168'
let root, child, server, ownsCredentials = false, cleaning
const connections = new Set()

function run(command, args) {
  return new Promise(resolve => {
    const process = spawn(command, args, { stdio: 'ignore' })
    process.on('error', () => resolve(1))
    process.on('exit', code => resolve(code ?? 1))
  })
}
function cleanup() {
  if (!cleaning) cleaning = (async () => {
    if (server) server.close()
    for (const { socket, proxy } of connections) { socket.destroy(); proxy.kill() }
    await run('docker', ['rm', '-f', name])
    if (ownsCredentials) await rm(credentialsDir, { recursive: true, force: true })
    if (root) await rm(root, { recursive: true, force: true })
  })()
  return cleaning
}
for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, async () => {
  await cleanup()
  process.exit(0)
})
try {
  await mkdir(credentialsDir, { mode: 0o700 })
  ownsCredentials = true
  root = await mkdtemp(join(tmpdir(), 'seclab-playwright-'))
  const workspace = join(root, 'workspace'), data = join(root, 'data')
  for (const path of [workspace, data]) {
    await mkdir(path)
    await chmod(path, 0o777)
  }
  const password = randomBytes(32).toString('base64url')
  await writeFile(join(credentialsDir, 'user.json'), JSON.stringify({ username: 'tester', password }), { mode: 0o600 })
  await writeFile(join(credentialsDir, 'workspace.json'), JSON.stringify({ workspace, container: name }), { mode: 0o600 })
  const envFile = join(root, 'backend.env')
  await writeFile(envFile, `DASHBOARD_PASSWORD=${password}\nSECLAB_DATA_DIR=/fixture-state\nHOME=/home/tester\nDASHBOARD_ALLOWED_HOSTS=localhost,127.0.0.1\nDASHBOARD_CORS_ORIGINS=http://127.0.0.1:4199\nPYTHONPATH=/usr/local/share/seclab/dashboard/backend\n`, { mode: 0o600 })
  console.log(`Backend de pruebas: ${name}; usuario tester temporal; contraseña aleatoria privada.`)
  server = createServer(socket => {
    const proxy = spawn('docker', ['exec', '-i', name, 'socat', 'STDIO', 'TCP:127.0.0.1:8080'], { stdio: ['pipe', 'pipe', 'ignore'] })
    const connection = { socket, proxy }
    connections.add(connection)
    socket.pipe(proxy.stdin)
    proxy.stdout.pipe(socket)
    proxy.stdin.on('error', () => socket.destroy())
    proxy.on('error', () => socket.destroy())
    proxy.on('exit', () => socket.destroy())
    socket.on('error', () => proxy.kill())
    socket.on('close', () => { proxy.kill(); connections.delete(connection) })
  })
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(4199, '127.0.0.1', resolve) })
  child = spawn('docker', ['run', '--rm', '--name', name, '--read-only', '--no-healthcheck',
    '--network', 'none', '--user', 'tester', '--tmpfs', '/tmp:rw,nosuid,nodev', '--cap-drop', 'ALL',
    '--security-opt', 'no-new-privileges',
    '-v', `${workspace}:/workspace`, '-v', `${data}:/fixture-state`, '--env-file', envFile,
    '--entrypoint', '/opt/nxc/bin/python3', image,
    '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8080'], { stdio: 'inherit' })
  process.exitCode = await new Promise((resolve, reject) => {
    child.on('error', reject)
    child.on('exit', code => resolve(code ?? 1))
  })
} catch (error) {
  console.error(`No se pudo iniciar el fixture: ${error.message}`)
  process.exitCode = 1
} finally {
  await cleanup()
}
