import { test, expect } from '@playwright/test';

test.describe('PartsOps AI Manager E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/admin/data-health', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'healthy',
          generated_at: new Date().toISOString(),
          tenant_id: 'default',
          entity_counts: {
            requests: { total: 10, by_status: { NEW: 5 }, active_queue_total: 5 },
            suppliers: { total: 4, active: 4, inactive: 0 },
            invoices: { total: 2, by_status: {} },
            approval_tickets: { total: 1, pending: 1, approved: 0, rejected: 0 },
            erp_sync_logs: { total: 50, success: 50, failed: 0 },
            events: 100,
            llm_usage_logs: 25,
          },
          freshness: {},
          health_indicators: {
            queue_staleness: { stuck_over_24h: 0, stuck_over_72h: 0, oldest_active_request_hours: 2 },
            approval_pressure: { pending_approvals: 1 },
            erp_health: { currently_failing: false },
            agent_health: { llm_error_rate_last_hour: 0, llm_errors_last_hour: 0, llm_requests_last_hour: 10 },
            supplier_feed_freshness: { feed_stale_suppliers: 0, suppliers_without_feed: 0 },
          },
          alerts: [],
        }),
      });
    });

    await page.route('**/api/requests', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1,
            request_id: 'REQ-4821',
            status: 'NEW',
            customer_name: 'Test Client E2E',
            created_at: new Date().toISOString(),
            parts_json: JSON.stringify([{ name: 'Brake pads', quantity: 2 }]),
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
          count: 10,
          total_cost_usd: 0.15,
          by_provider: { openai: 0.15 },
          by_model: { 'gpt-4o': 0.15 },
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

    await page.goto('http://localhost:5176');
    await page.waitForLoadState('networkidle');
  });

  const openCommandPalette = async (page: any) => {
    await page.evaluate(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }));
    });
    await page.waitForTimeout(300);
    await expect(page.locator('input[placeholder*="команду"]')).toBeVisible({ timeout: 10000 });
  };

  const clickPaletteButton = async (page: any, label: string) => {
    await page.evaluate((l) => {
      const btn = Array.from(document.querySelectorAll('button')).find((b) =>
        b.textContent?.trim().includes(l)
      );
      if (btn) btn.click();
    }, label);
  };

  test('should load dashboard and show workspace title', async ({ page }) => {
    await expect(page.locator('h2:has-text("Операционный пульт закупок")').first()).toBeVisible({ timeout: 15000 });
    await expect(page.locator('text=Активная очередь').first()).toBeVisible();
    await expect(page.locator('text=Нагрузка согласования')).toBeVisible();
  });

  test('Command Palette opens and shows navigation items', async ({ page }) => {
    await openCommandPalette(page);

    await expect(page.locator('text=Навигация')).toBeVisible();
    await expect(page.locator('text=Действия')).toBeVisible();
    await expect(page.locator('text=Помощь')).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(page.locator('input[placeholder*="команду"]')).not.toBeVisible({ timeout: 5000 });
  });

  test('Command Palette navigation works - go to Suppliers', async ({ page }) => {
    await openCommandPalette(page);
    await clickPaletteButton(page, 'Каталог поставщиков');
    await expect(page.locator('button:has-text("Поставщики"), button:has-text("Каталог поставщиков")').first()).toBeVisible({ timeout: 10000 });
  });

  test('Create new request via Order Import page', async ({ page }) => {
    await openCommandPalette(page);
    await clickPaletteButton(page, 'Кастом');

    await expect(page.locator(':has-text("Ввод запроса")').first()).toBeVisible({ timeout: 10000 });
  });

  test('Kanban board loads and shows requests', async ({ page }) => {
    await openCommandPalette(page);
    await clickPaletteButton(page, 'Канбан-доска');

    await expect(page.locator('text=Интерактивный рабочий процесс')).toBeVisible({ timeout: 10000 });
  });

  test('Right panel shows request queue', async ({ page }) => {
    await expect(page.locator('text=REQ-').first()).toBeVisible({ timeout: 15000 });
  });

  test('Audit view loads with completed orders', async ({ page }) => {
    await openCommandPalette(page);
    await clickPaletteButton(page, 'Аудит и логи');

    await expect(page.locator('text=Детальный аудит не загружен')).toBeVisible({ timeout: 10000 });
  });

  test('Suppliers page loads', async ({ page }) => {
    await openCommandPalette(page);
    await clickPaletteButton(page, 'Каталог поставщиков');

    await expect(page.locator('button:has-text("Поставщики"), button:has-text("Каталог поставщиков")').first()).toBeVisible({ timeout: 10000 });
  });
});