import { test, expect, type Page } from '@playwright/test';

const MOCK_SUPPLIER = {
  supplier_id: 'SUP-001',
  name: 'Nordline Supply',
  contact_person: 'Иван Петров',
  phone: '+7-495-111-22-33',
  email: 'sales@nordline.test',
  city: 'Москва',
  specialization: 'OEM, тормоза',
  reliability_score: 0.94,
  avg_delivery_days: 3,
  status: 'active',
  rating_manual: 4.7,
  rating_auto: 0.91,
  account_owner: 'Ops Team',
  payment_terms: 'Net 30',
  delivery_terms: 'EXW',
  currency_default: 'RUB',
  notes_internal: 'Приоритетный поставщик',
  last_feed_at: new Date().toISOString(),
  last_sync_status: 'synced',
  categories: ['Тормозная система', 'Подвеска'],
  table_count: 2,
  active_table_count: 1,
  last_activity_at: new Date().toISOString(),
};

const MOCK_SUPPLIER_STALE = {
  ...MOCK_SUPPLIER,
  supplier_id: 'SUP-002',
  name: 'Volga Parts',
  status: 'pending',
  reliability_score: 0.72,
  last_sync_status: 'stale',
  active_table_count: 0,
  table_count: 1,
  city: 'Казань',
  categories: ['Фильтры'],
};

async function mockBaseApis(page: Page) {
  // Prevent hanging SSE / EventSource from stalling browser context teardown.
  await page.route('**/api/events/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: 'data: {}\n\n',
    });
  });

  await page.route('**/api/session', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        tenant_id: 'default',
        role: 'manager',
        authenticated: true,
        auth_mode: 'token',
        permissions: { can_manage_matching: true },
      }),
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
          requests: { total: 1, by_status: { NEW: 1 }, active_queue_total: 1 },
          suppliers: { total: 2, active: 1, inactive: 1 },
          invoices: { total: 0, by_status: {} },
          approval_tickets: { total: 0, pending: 0, approved: 0, rejected: 0 },
          erp_sync_logs: { total: 0, success: 0, failed: 0 },
          events: 0,
          llm_usage_logs: 0,
        },
        freshness: {},
        health_indicators: {
          queue_staleness: { stuck_over_24h: 0, stuck_over_72h: 0, oldest_active_request_hours: 1 },
          approval_pressure: { pending_approvals: 0 },
          erp_health: { currently_failing: false },
          agent_health: {
            llm_error_rate_last_hour: 0,
            llm_errors_last_hour: 0,
            llm_requests_last_hour: 0,
          },
          supplier_feed_freshness: { feed_stale_suppliers: 1, suppliers_without_feed: 0 },
        },
        alerts: [],
      }),
    });
  });

  await page.route('**/api/requests', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  await page.route('**/api/admin/observability/llm-costs', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ count: 0, total_cost_usd: 0, by_provider: {}, by_model: {} }),
    });
  });

  await page.route('**/api/admin/observability/pipeline-runs', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });
}

async function mockSuppliersList(page: Page, suppliers = [MOCK_SUPPLIER, MOCK_SUPPLIER_STALE]) {
  // Registered first; more specific routes below override (Playwright checks last-registered first).
  await page.route(/\/api\/suppliers(\?.*)?$/, async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ ...MOCK_SUPPLIER, supplier_id: 'SUP-NEW', name: 'Новый поставщик' }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(suppliers),
    });
  });
}

async function mockSupplierDetail(page: Page) {
  // Single dispatcher — avoids Playwright last-route precedence fights.
  await page.route('**/api/suppliers/SUP-001**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();

    if (path.endsWith('/archive') && method === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...MOCK_SUPPLIER, status: 'archived' }),
      });
      return;
    }

    if (path.includes('/rows')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          rows: [
            {
              row_key: 'R1',
              part_name: 'Колодки передние',
              oem_number: '34116761280',
              brand: 'BMW',
              price: 4200,
              currency: 'RUB',
              stock_qty: 8,
              delivery_days: 2,
              category: 'Тормозная система',
              raw_payload_json: { sku: 'BRK-01' },
            },
          ],
        }),
      });
      return;
    }

    if (path.endsWith('/analytics')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          supplier_id: 'SUP-001',
          summary: {
            table_count: 2,
            active_table_count: 1,
            catalog_item_count: 12,
            avg_price: 4500,
            avg_delivery_days: 3,
            manual_rating: 4.7,
            auto_rating: 0.91,
            stale_table_count: 0,
            avg_price_deviation: 0.04,
          },
          reliability_history: [],
          category_coverage: [{ category: 'Тормозная система', count: 8 }],
          table_health: [
            {
              table_id: 'TBL-1',
              name: 'OEM price list',
              status: 'active',
              is_active: true,
              row_count: 12,
            },
          ],
        }),
      });
      return;
    }

    if (path.includes('/logs')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total: 1,
          logs: [
            {
              event_id: 'EVT-1',
              supplier_id: 'SUP-001',
              table_id: 'TBL-1',
              event_type: 'table_imported',
              actor_id: 'admin',
              payload: { rows: 12 },
              created_at: new Date().toISOString(),
            },
          ],
        }),
      });
      return;
    }

    if (path.includes('/tables')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            table_id: 'TBL-1',
            supplier_id: 'SUP-001',
            name: 'OEM price list',
            source_type: 'excel',
            filename: 'oem.xlsx',
            version: 2,
            status: 'active',
            uploaded_at: new Date().toISOString(),
            uploaded_by: 'admin',
            row_count: 12,
            mapped_columns_json: {},
            validation_summary_json: {
              imported_rows: 12,
              total_rows: 12,
              skipped_rows: 0,
              warnings: [],
            },
            is_active: true,
          },
        ]),
      });
      return;
    }

    // GET/PATCH /api/suppliers/SUP-001
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(MOCK_SUPPLIER),
    });
  });
}

async function openSuppliersCatalog(page: Page) {
  await page.goto('/');
  await page.waitForLoadState('domcontentloaded');
  // App shell ready
  await expect(page.locator('#root')).not.toBeEmpty({ timeout: 15000 });

  const nav = page.getByRole('button', { name: 'Каталог поставщиков' }).first();
  await expect(nav).toBeVisible({ timeout: 15000 });
  await nav.click();

  await expect(page.getByRole('heading', { name: 'Поставщики', exact: true })).toBeVisible({
    timeout: 15000,
  });
}

test.describe('Suppliers catalog redesign', () => {
  test.beforeEach(async ({ page }) => {
    await mockBaseApis(page);
    await mockSuppliersList(page);
    await mockSupplierDetail(page);
  });

  test('loads catalog with KPI, cards and RU labels', async ({ page }) => {
    await openSuppliersCatalog(page);

    await expect(page.getByText('Каталог, фиды, рейтинги и журнал изменений')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Активные' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Ожидают' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Устаревшие фиды' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Добавить поставщика' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Карточки' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Таблица' })).toBeVisible();

    await expect(page.getByText('Nordline Supply')).toBeVisible();
    await expect(page.getByText('Volga Parts')).toBeVisible();
    await expect(page.getByText(/Показано 2 из 2/)).toBeVisible();
  });

  test('KPI filter and clear chips work', async ({ page }) => {
    await openSuppliersCatalog(page);

    await page.getByRole('button', { name: 'Активные' }).click();
    // status filter is server-side in real app; mock ignores query — chip should still appear
    const statusChip = page.getByRole('button', { name: /Статус: Активен/ });
    await expect(statusChip).toBeVisible();
    // chip click clears that filter
    await statusChip.click();
    await expect(page.getByRole('button', { name: /Статус: Активен/ })).toHaveCount(0);
  });

  test('switches to table mode and shows rows', async ({ page }) => {
    await openSuppliersCatalog(page);

    await page.getByRole('button', { name: 'Таблица' }).click();
    await expect(page.getByRole('columnheader', { name: 'Поставщик' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Статус' })).toBeVisible();
    await expect(page.getByText('Nordline Supply')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Открыть' }).first()).toBeVisible();
  });

  test('opens detail workspace with RU tabs', async ({ page }) => {
    await openSuppliersCatalog(page);

    await page.locator('article').filter({ hasText: 'Nordline Supply' }).click();
    await expect(page.getByRole('button', { name: 'Назад к каталогу' })).toBeVisible({ timeout: 15000 });
    await expect(page.locator('h2', { hasText: 'Nordline Supply' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Обзор' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Профиль' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Таблицы' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Аналитика' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Журнал' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Настройки' })).toBeVisible();

    await page.getByRole('button', { name: 'Аналитика' }).click();
    await expect(page.getByText('Сигналы здоровья')).toBeVisible();
    await expect(page.getByText('Покрытие категорий')).toBeVisible();

    await page.getByRole('button', { name: 'Таблицы' }).click();
    await expect(page.getByRole('heading', { name: /Предпросмотр: OEM price list/ })).toBeAttached();
    await expect(page.getByText('Колодки передние')).toBeVisible();
  });

  test('archive confirm modal opens from catalog', async ({ page }) => {
    await openSuppliersCatalog(page);

    await page
      .locator('article')
      .filter({ hasText: 'Nordline Supply' })
      .getByRole('button', { name: 'Архив' })
      .click();
    const dialog = page.getByRole('alertdialog');
    await expect(dialog).toBeVisible({ timeout: 10000 });
    await expect(dialog.getByRole('heading', { name: /Архивировать/ })).toBeVisible();
    await dialog.getByRole('button', { name: 'Отмена' }).click();
    await expect(dialog).toHaveCount(0);
  });

  test('empty state when API returns no suppliers', async ({ page }) => {
    await mockBaseApis(page);
    await page.route(/\/api\/suppliers(\?.*)?$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await openSuppliersCatalog(page);
    await expect(page.getByText('Поставщики пока не добавлены')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Добавить первого' })).toBeVisible();
  });

  test('error state when list fails', async ({ page }) => {
    await mockBaseApis(page);
    await page.route(/\/api\/suppliers(\?.*)?$/, async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'upstream failed' }),
      });
    });

    await openSuppliersCatalog(page);
    await expect(page.getByText('Не удалось загрузить поставщиков')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Повторить' })).toBeVisible();
  });
});
