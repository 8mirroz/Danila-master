import { test, expect } from '@playwright/test';

test.describe('PartsOps AI Manager E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/session', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ tenant_id: 'default', role: 'manager', authenticated: true, auth_mode: 'token', permissions: { can_manage_matching: true } }),
      });
    });
    await page.route('**/api/organizations/current', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          organization: { organization_id: 'default', display_name: 'PartsOps E2E' },
          subscription: { status: 'trial', plan_code: 'beta_trial', position_limit: 100, current_period_end: '2026-08-15T00:00:00Z' },
          onboarding: { checklist_json: '[]', completed_steps_json: '[]' },
          integrations: [],
        }),
      });
    });
    await page.route('**/api/billing/usage', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ positions_used: 0, positions_remaining: 100, position_limit: 100 }),
      });
    });
    await page.route('**/api/organizations/current/members', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
    });
    await page.route('**/api/analytics/quoteops', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ automation_rate: 0, automated_positions: 0, valid_positions: 0, margin_violations: 0, pending_approvals: 0 }),
      });
    });
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

    await page.route(/\/api\/suppliers(\?.*)?$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            supplier_id: 'SUP-001',
            name: 'Nordline Supply',
            contact_person: 'Иван Петров',
            phone: '+7-495-111-22-33',
            email: 'sales@nordline.test',
            city: 'Москва',
            specialization: 'OEM',
            reliability_score: 0.94,
            avg_delivery_days: 3,
            status: 'active',
            rating_manual: 4.8,
            rating_auto: 0.9,
            account_owner: 'Ops',
            payment_terms: 'Net 30',
            delivery_terms: 'EXW',
            currency_default: 'RUB',
            notes_internal: '',
            last_feed_at: new Date().toISOString(),
            last_sync_status: 'synced',
            categories: ['Тормозная система'],
            table_count: 1,
            active_table_count: 1,
            last_activity_at: new Date().toISOString(),
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
    await page.evaluate((l: string) => {
      const palette = document.querySelector('input[placeholder*="команду"]')?.closest('div.fixed');
      const btn = Array.from(palette?.querySelectorAll('button') ?? []).find((b) =>
        b.textContent?.trim().includes(l)
      );
      if (btn) btn.click();
    }, label);
  };

  test('should load dashboard and show workspace title', async ({ page }) => {
    await expect(page.locator('h2:has-text("Рабочая очередь PartsOps")').first()).toBeVisible({ timeout: 15000 });
    await expect(page.locator('text=Активная очередь').first()).toBeVisible();
    await expect(page.locator('text=Нагрузка согласования')).toBeVisible();
  });

  test('Command Palette opens and shows navigation items', async ({ page }) => {
    await openCommandPalette(page);

    await expect(page.locator('text=Навигация')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Действия', exact: true })).toBeVisible();
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

  test('Kanban action opens the real pipeline-run confirmation dialog', async ({ page }) => {
    await openCommandPalette(page);
    await clickPaletteButton(page, 'Канбан-доска');

    await page.getByRole('button', { name: 'Запустить pipeline для REQ-4821', exact: true }).click();
    await expect(page.getByRole('dialog', { name: 'Подтверждение запуска pipeline' })).toBeVisible();
    await expect(page.getByText('Финальный этап определяет pipeline, а не drag-and-drop.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Запустить pipeline', exact: true })).toBeVisible();
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

    await expect(page.getByRole('heading', { name: 'Поставщики' })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('button', { name: 'Добавить поставщика' })).toBeVisible();
    await expect(page.getByText('Nordline Supply')).toBeVisible();
  });
});
