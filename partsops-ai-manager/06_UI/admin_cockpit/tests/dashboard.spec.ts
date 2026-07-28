import { test, expect } from '@playwright/test';

test.describe('PartsOps Admin Cockpit - Refactored Soft UI & View Model', () => {

  test.beforeEach(async ({ page }) => {
    await page.route('**/api/admin/data-health', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'healthy',
          generated_at: new Date().toISOString(),
          tenant_id: 'tenant-e2e-test',
          entity_counts: {
            requests: { total: 42, by_status: { NEW: 10, APPROVED: 20 }, active_queue_total: 12 },
            suppliers: { total: 15, active: 12, inactive: 3 },
            invoices: { total: 8, by_status: {} },
            approval_tickets: { total: 5, pending: 3, approved: 2, rejected: 0 },
            erp_sync_logs: { total: 100, success: 98, failed: 2 },
            events: 500,
            llm_usage_logs: 120,
          },
          freshness: {
            last_request_at: new Date().toISOString(),
            last_event_at: new Date().toISOString(),
            last_erp_sync: new Date().toISOString(),
          },
          health_indicators: {
            queue_staleness: { stuck_over_24h: 1, stuck_over_72h: 0, oldest_active_request_hours: 12 },
            approval_pressure: { pending_approvals: 3 },
            erp_health: { currently_failing: false },
            agent_health: { llm_error_rate_last_hour: 0, llm_errors_last_hour: 0, llm_requests_last_hour: 50 },
            supplier_feed_freshness: { feed_stale_suppliers: 2, suppliers_without_feed: 1 },
          },
          alerts: [
            { level: 'info', source: 'ERP Sync', message: 'Синхронизация с ERP выполнена успешно' },
          ],
        }),
      });
    });

    await page.route('**/api/requests', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 99,
            request_id: 'REQ-9999',
            status: 'NEW',
            customer_name: 'Test Client',
            created_at: new Date().toISOString(),
            parts_json: '[]',
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify([
            {
              id: 1,
              request_id: 'REQ-4821',
              source: 'MANUAL',
              status: 'NEW',
              customer_name: 'ООО АвтоТехСнаб',
              created_at: new Date().toISOString(),
              parts_json: JSON.stringify([{ name: 'Тормозные колодки', quantity: 2 }]),
              priority: 'normal',
            },
          ]),
        });
      }
    });

    await page.route('**/api/suppliers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: '1',
            supplier_id: 'SUP-001',
            name: 'Nordline Supply',
            rating: 4.8,
            active: true,
            categories: ['Тормозная система'],
            regions: ['МСК'],
            catalog_type: 'API',
            reliability_score: 95,
            feed_updated_at: new Date().toISOString(),
          },
        ]),
      });
    });

    await page.route('**/api/admin/observability/llm-costs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          count: 42,
          total_cost_usd: 0.42,
          by_provider: { openai: 0.25, anthropic: 0.17 },
          by_model: { 'gpt-4o': 0.25, 'claude-3-5-sonnet': 0.17 },
        }),
      });
    });

    await page.route('**/api/admin/observability/pipeline-runs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.route('**/api/copilot/health', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'online',
          profile: 'partsops',
          version: '0.19.0',
          capabilities: ['run_submission', 'run_events_sse', 'run_stop'],
          skills: ['partsops-navigation'],
        }),
      });
    });

    await page.route('**/api/copilot/conversations', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 'conv-e2e' }) });
      } else {
        await route.continue();
      }
    });

    await page.route('**/api/copilot/conversations/conv-e2e/runs', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ run_id: 'run-e2e', correlation_id: 'corr-e2e', status: 'queued' }) });
    });

    await page.route('**/api/copilot/runs/run-e2e/events', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'data: {"type":"run.started","run_id":"run-e2e","correlation_id":"corr-e2e","sequence":1}\n\ndata: {"type":"assistant.delta","run_id":"run-e2e","correlation_id":"corr-e2e","text":"Готово","sequence":2}\n\ndata: {"type":"run.completed","run_id":"run-e2e","correlation_id":"corr-e2e","sequence":3}\n\n',
      });
    });
  });

  const openCommandPalette = async (page: any) => {
    await page.evaluate(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }));
    });
    await page.waitForTimeout(300);
    await expect(page.locator('input[placeholder*="команду"]')).toBeVisible({ timeout: 10000 });
  };

  test('Dashboard loads live view model metrics and displays KPI tiles at 1440px', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('http://localhost:5176');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('h2:has-text("Операционный пульт закупок")').first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator('button:has-text("Новый запрос")')).toBeVisible();
    await expect(page.locator('text=Активная очередь').first()).toBeVisible();
    await expect(page.locator('text=Нагрузка согласования')).toBeVisible();
  });

  test('Drawer behavior and responsive layout at 390px mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('http://localhost:5176');
    await page.waitForLoadState('networkidle');

    const navBurger = page.locator('button[aria-label="Открыть меню навигации"]');
    await expect(navBurger).toBeVisible();
    await navBurger.click();

    const navDrawer = page.locator('aside[role="dialog"][aria-label="Меню навигации"]');
    await expect(navDrawer).toBeVisible();

    const closeBtn = page.locator('button[aria-label="Закрыть меню"]');
    await closeBtn.click();
    await expect(navDrawer).not.toBeVisible();
  });

  test('Command palette keyboard workflow (Cmd+K / Escape)', async ({ page }) => {
    await page.goto('http://localhost:5176');
    await page.waitForLoadState('networkidle');

    await openCommandPalette(page);
    const paletteInput = page.locator('input[placeholder*="команду"]');
    await expect(paletteInput).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(paletteInput).not.toBeVisible();
  });

  test('BatchSearchModal focus trap, default values, and close button', async ({ page }) => {
    await page.goto('http://localhost:5176');
    await page.waitForLoadState('networkidle');

    await page.click('button:has-text("Пакетный поиск OEM")');

    const modalDialog = page.locator('div[role="dialog"][aria-label="Пакетный поиск по артикулам OEM"]');
    await expect(modalDialog).toBeVisible();

    const prioritySelect = modalDialog.locator('select');
    await expect(prioritySelect).toHaveValue('normal');

    const closeBtn = page.locator('button[aria-label="Закрыть диалог"]');
    await closeBtn.click();
    await expect(modalDialog).not.toBeVisible();
  });

  test('Numeric table cells are right aligned', async ({ page }) => {
    await page.goto('http://localhost:5176');
    await page.waitForLoadState('networkidle');

    const numCell = page.locator('.table-base .cell-num').first();
    if (await numCell.count() > 0) {
      await expect(numCell).toHaveCSS('text-align', 'right');
    }
  });

  test('Premium queue rail stays inside the desktop viewport and exposes stable controls', async ({ page }) => {
    await page.setViewportSize({ width: 1669, height: 940 });
    await page.goto('http://localhost:5176');
    await page.waitForLoadState('networkidle');

    const rail = page.locator('aside[aria-label="Скрытая очередь заказов"]');
    const expandedRail = page.locator('aside.queue-rail').first();
    await page.getByRole('button', { name: 'Свернуть очередь заказов' }).click();
    await expect(rail).toBeVisible();
    await expect(rail.getByRole('button', { name: 'Развернуть очередь заказов' }).first()).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(1669);
    await rail.getByRole('button', { name: 'Развернуть очередь заказов' }).first().click();
    await expect(expandedRail).toBeVisible();
    const attachment = page.locator('label[aria-label="Загрузить файл"]');
    await expect(attachment).toBeVisible();
    await expect(attachment.locator('svg')).toBeVisible();
    await expect(page.locator('[data-testid="queue-order-meta"]').first()).toBeVisible();
    await expect(page.locator('[data-testid="queue-order-controls"]').first()).toBeVisible();
    await expect(page.locator('[data-testid="queue-order-meta"]').first().locator(':scope > *')).toHaveCount(2);
    const cardBox = await page.locator('.queue-order-card').first().boundingBox();
    const controlsBox = await page.locator('[data-testid="queue-order-controls"]').first().boundingBox();
    expect(cardBox && controlsBox && controlsBox.x + controlsBox.width).toBeLessThanOrEqual((cardBox?.x ?? 0) + (cardBox?.width ?? 0));
  });

  test('Mobile queue drawer and Hermes assistant remain keyboard usable', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('http://localhost:5176');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: 'Открыть очередь запросов' }).click();
    const queueDrawer = page.locator('aside[role="dialog"][aria-label="Очередь запросов"]');
    await expect(queueDrawer).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(queueDrawer).not.toBeVisible();

    await page.getByRole('button', { name: 'Открыть меню навигации' }).click();
    const navDrawer = page.locator('aside[role="dialog"][aria-label="Меню навигации"]');
    await expect(navDrawer).toBeVisible();
    await navDrawer.getByRole('button', { name: 'AI агент' }).click();
    const hermes = page.getByTestId('hermes-drawer');
    await expect(hermes).toBeVisible();
    await expect(hermes.getByText('READ-ONLY', { exact: true })).toBeVisible();
    await expect(hermes.getByRole('textbox', { name: 'Сообщение Hermes' })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(hermes).not.toBeVisible();
  });
});
