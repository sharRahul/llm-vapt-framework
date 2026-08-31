const { test, expect } = require('@playwright/test');

async function csrfToken(request) {
  const response = await request.get('/api/csrf-token');
  expect(response.ok()).toBeTruthy();
  const data = await response.json();
  expect(data.csrf_token).toBeTruthy();
  return data.csrf_token;
}

test('hosted server serves the console and creates an authorised fixture scan job', async ({ page, request }) => {
  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expect(page).toHaveTitle(/VulnorAIQ/i);
  await expect(page.locator('#root')).toBeAttached();

  const token = await csrfToken(request);
  const response = await request.post('/api/scans', {
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': token,
    },
    data: {
      target: process.env.VULNORAIQ_HOSTED_TEST_TARGET || 'demo',
      profile: 'baseline',
      authorised: true,
    },
  });

  expect(response.status()).toBe(202);
  const job = await response.json();
  expect(job.id).toBeTruthy();
  expect(job.target).toBe(process.env.VULNORAIQ_HOSTED_TEST_TARGET || 'demo');
  expect(job.profile).toBe('baseline');
  expect(['queued', 'running', 'completed']).toContain(job.status);
});

test('console navigation is compact at every viewport and legacy Agent Lab opens Projects', async ({ page }) => {
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 820, height: 1180 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto('/', { waitUntil: 'networkidle' });
    for (const view of ['Overview', 'Workspace', 'Targets', 'Agents', 'Projects']) {
      await page.getByRole('button', { name: view }).click();
      await expect(page).toHaveURL(new RegExp(`#/${view.toLowerCase()}`));
      const widths = await page.locator('body').evaluate((body) => ({ scroll: body.scrollWidth, client: body.clientWidth }));
      expect(widths.scroll).toBeLessThanOrEqual(widths.client);
    }
  }

  await page.goto('/agent-lab', { waitUntil: 'networkidle' });
  await expect(page).toHaveURL(/#\/projects$/);
  await expect(page.getByRole('heading', { name: 'Projects', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Import ZIP archive' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Refresh mapped folders' })).toBeVisible();
});
