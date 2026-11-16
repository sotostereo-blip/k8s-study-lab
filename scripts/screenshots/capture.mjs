// Screenshots and the lab GIF in docs/images/ (README). Needs Google Chrome, ffmpeg and Docker.
//
//   1. start a backend on a THROWAWAY database (never your real data/progress.db):
//        cd backend && DB_PATH=/tmp/shots.db uvicorn app.main:app --port 8000
//   2. cd frontend && npm run dev
//   3. python scripts/screenshots/seed.py          # realistic KCNA/CKA progress in that database
//   4. cd scripts/screenshots && npm i playwright-core && node capture.mjs /tmp/shots
//   5. ffmpeg -f concat -safe 0 -i /tmp/shots/frames.txt \
//        -vf "fps=8,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" \
//        /tmp/shots/lab.gif
//   6. copy the .png files and lab.gif to docs/images/
import { chromium } from 'playwright-core'
import fs from 'node:fs'

const OUT = process.argv[2] || '/tmp/shots'
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const T0 = Date.now()
const mark = (name) => { const t = (Date.now() - T0) / 1000; console.log(`${name} at ${t.toFixed(1)}s`); return t }
const browser = await chromium.launch({
  executablePath: CHROME, headless: true,
})
const ctx = await browser.newContext({
  viewport: { width: 1280, height: 800 }, colorScheme: 'dark',
})
// frames for the GIF: a screenshot every ~200 ms while `recording` is on
let recording = false, frameNo = 0
fs.mkdirSync(`${OUT}/frames`, { recursive: true })
const frames = []
async function recorder() {
  while (recording) {
    const t = Date.now()
    const f = `${OUT}/frames/f${String(frameNo++).padStart(4, '0')}.jpg`
    await page.screenshot({ path: f, type: 'jpeg', quality: 85 }).catch(() => {})
    frames.push({ f, t })
    const wait = 200 - (Date.now() - t); if (wait > 0) await new Promise((r) => setTimeout(r, wait))
  }
}
const page = await ctx.newPage()
const shot = async (name) => { await page.waitForTimeout(600); await page.screenshot({ path: `${OUT}/${name}.png` }); mark(name) }
const tab = (label) => page.locator('nav button', { hasText: new RegExp(`^${label}$`) }).click()
const cert = (id) => page.selectOption('select.cert-select', id)

await page.goto('http://localhost:5173/')
await page.waitForSelector('select.cert-select')
await cert('kcna')
await tab('Plan'); await page.waitForTimeout(800); await shot('plan')
await tab('Dashboard'); await page.waitForTimeout(800); await shot('dashboard')

await tab('Practice')
await page.waitForSelector('.card li button .key', { timeout: 10000 })
await page.locator('.card li button').nth(1).click({ position: { x: 12, y: 12 } })
await page.getByRole('button', { name: 'Check answer' }).click()
await page.waitForTimeout(500)
const term = page.locator('.card .term').first()
if (await term.count()) await term.click()
await shot('practice')

await tab('My path'); await page.waitForTimeout(800); await shot('path')

await cert('interview')
await page.waitForTimeout(800)
await tab('Practice')
await page.waitForTimeout(1200); await shot('interview')

// lab: open a CKA task, wait for the cluster, solve it in the browser terminal, check
await cert('cka')
await tab('Labs')
await page.locator('.lab-card', { hasText: 'Create a Deployment' }).first().click()
mark('lab-open')
await page.waitForSelector('.lab-terminal iframe', { timeout: 300000 })
await page.waitForTimeout(4000)
mark('lab-ready')
recording = true
const rec = recorder()
const term2 = page.frameLocator('.lab-terminal iframe').locator('.xterm-screen, canvas, body').first()
await term2.click()
for (const cmd of [
  'kubectl create namespace shop',
  'kubectl -n shop create deployment web --image=nginx:1.27-alpine --replicas=3',
  'kubectl -n shop rollout status deployment web',
]) {
  await page.keyboard.type(cmd, { delay: 35 })
  await page.keyboard.press('Enter')
  await page.waitForTimeout(cmd.includes('rollout') ? 9000 : 1500)
}
await page.getByRole('button', { name: 'Check my work' }).click()
await page.waitForSelector('.feedback.ok', { timeout: 60000 })
await page.waitForTimeout(2500)
await page.screenshot({ path: `${OUT}/lab.png` })
recording = false
await rec
mark('lab-done')
await page.getByRole('button', { name: 'Stop lab' }).click()
await page.waitForTimeout(1000)
await ctx.close()
await browser.close()
// ffmpeg concat list with each frame's real duration
const lines = frames.map((x, i) => `file '${x.f}'\nduration ${(((frames[i + 1]?.t ?? x.t + 2000) - x.t) / 1000).toFixed(3)}`)
fs.writeFileSync(`${OUT}/frames.txt`, lines.join('\n') + `\nfile '${frames.at(-1).f}'\n`)
