// One local command starts both processes; reuse an already running RAY API.
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

const root = fileURLToPath(new URL('../', import.meta.url))
const python = fileURLToPath(new URL('../.venv/Scripts/python.exe', import.meta.url))
const unixPython = fileURLToPath(new URL('../.venv/bin/python', import.meta.url))
let backend
let server
try {
  const response = await fetch('http://127.0.0.1:8001/api/v1/dashboard', { signal: AbortSignal.timeout(1500) })
  if (!response.ok || !('budget' in await response.json())) throw new Error('Not a RAY backend')
  console.log('Using the running RAY backend on port 8001.')
} catch {
  const executable = existsSync(python) ? python : existsSync(unixPython) ? unixPython : 'python'
  backend = spawn(executable, ['-m', 'backend.server'], { cwd: root, stdio: 'inherit', windowsHide: true })
  backend.on('error', () => console.error('Backend failed to start. Install backend/requirements.txt in .venv.'))
  backend.on('exit', code => { if (code) console.error(`Backend stopped (${code}). Check Python dependencies or port 8001.`) })
}
try {
  server = await createServer()
  await server.listen()
  server.printUrls()
} catch (error) {
  backend?.kill()
  throw error
}
let closing = false
async function close() {
  if (closing) return
  closing = true
  backend?.kill()
  await server?.close()
  process.exit()
}
process.on('SIGINT', close)
process.on('SIGTERM', close)
