import { test, expect } from "@playwright/test";
import { spawn } from "node:child_process";
import which from "which";
import { join } from "path";

test("gradio cc dev correcty launches and is interactive", async ({ page }) => {
	test.setTimeout(45 * 1000);

	const _process = spawn(which("gradio"), ["cc", "dev"], {
		shell: true,
		stdio: "pipe",
		cwd: join(process.cwd(), "mycomponent"),
		env: {
			...process.env,
			PYTHONUNBUFFERED: "true"
		}
	});

	_process.stdout.setEncoding("utf8");
	_process.stderr.setEncoding("utf8");

	_process.on("exit", () => kill_process(_process));
	_process.on("close", () => kill_process(_process));
	_process.on("disconnect", () => kill_process(_process));

	let port;

	function std_out(data) {
		const _data: string = data.toString();

		const portRegExp = /:(\d+)/;
		const match = portRegExp.exec(_data);

		if (match && match[1]) {
			port = parseInt(match[1], 10);
		}
	}

	_process.stdout.on("data", std_out);

	while (!port) {
		await new Promise((r) => setTimeout(r, 1000));
	}
	await page.goto(`http://localhost:${port}`);
	await page.getByLabel("x").fill("foo");
	await page.getByRole("button", { name: "Submit" }).click();
	await expect(page.getByLabel("output")).toHaveValue("foo");
	kill_process(_process);
});

function kill_process(process) {
	process.kill("SIGKILL");
}