const { registry } = require(process.argv[2]);
const executable = registry.findExecutable("chromium-headless-shell")?.executablePath();
if (!executable) {
  throw new Error("locked Playwright registry has no Chromium headless shell executable");
}
process.stdout.write(`${executable}\n`);
