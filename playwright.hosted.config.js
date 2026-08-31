const { defineConfig, devices } = require('@playwright/test');

const port = process.env.VULNORAIQ_HOSTED_TEST_PORT || '8797';

module.exports = defineConfig({
  testDir: './tests/webui',
  testMatch: /hosted.*\.spec\.js/,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: `python scripts/webui_test_server.py --host 127.0.0.1 --port ${port} --skip-production-checks`,
    url: `http://127.0.0.1:${port}/healthz`,
    reuseExistingServer: !process.env.CI,
    timeout: 45_000,
    env: {
      ...process.env,
      VULNORAIQ_ALLOW_TEST_FIXTURE_TARGETS: 'true',
      VULNORAIQ_TARGET_CONFIG: 'targets.test.yaml',
      VULNORAIQ_AUTH_ENABLED: 'false',
      VULNORAIQ_WEB_OUTPUT_ROOT: 'reports/output/webui-hosted-playwright',
      VULNORAIQ_JOB_STORE_PATH: 'reports/output/webui-hosted-playwright/jobs.db',
    },
  },
});
