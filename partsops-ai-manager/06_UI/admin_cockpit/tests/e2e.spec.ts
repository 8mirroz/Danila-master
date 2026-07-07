import { test, expect } from '@playwright/test';

test.describe('PartsOps AI Manager E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5176');
    await page.waitForLoadState('networkidle');
  });

  // Helper to open command palette
  const openCommandPalette = async (page: any) => {
    await page.evaluate(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }));
    });
    await page.waitForTimeout(500);
    await expect(page.locator('input[placeholder*="команду"]')).toBeVisible({ timeout: 10000 });
  };

  // Helper to click palette button using JS to avoid backdrop interception
  const clickPaletteButton = async (page: any, label: string) => {
    await page.evaluate((l) => {
      const btn = Array.from(document.querySelectorAll('button')).find(b => 
        b.textContent?.includes(l)
      );
      if (btn) btn.click();
    }, label);
  };

  test('should load dashboard and show overview metrics', async ({ page }) => {
    await expect(page.locator('text=Операционная панель PartsOps')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('text=Уверенность системы')).toBeVisible();
    await expect(page.locator('text=Нагрузка согласования')).toBeVisible();
  });

  test('Command Palette opens and shows navigation items', async ({ page }) => {
    await openCommandPalette(page);

    // Check categories exist
    await expect(page.locator('text=Навигация')).toBeVisible();
    await expect(page.locator('text=Действия')).toBeVisible();
    await expect(page.locator('text=Помощь')).toBeVisible();

    // Check some navigation items
    await expect(page.locator('button:has-text("Панель управления")').first()).toBeVisible();
    await expect(page.locator('button:has-text("Канбан-доска")').first()).toBeVisible();
    await expect(page.locator('button:has-text("Каталог поставщиков")').first()).toBeVisible();

    // Close with Escape
    await page.keyboard.press('Escape');
    await expect(page.locator('input[placeholder*="команду"]')).not.toBeVisible({ timeout: 5000 });
  });

  test('Command Palette navigation works - go to Suppliers', async ({ page }) => {
    await openCommandPalette(page);

    // Click on the Suppliers navigation item using JS
    await clickPaletteButton(page, 'Каталог поставщиков');

    // Should navigate to suppliers page
    await expect(page.locator('text=Каталог поставщиков').first()).toBeVisible({ timeout: 10000 });
  });

  test('Create new request via Order Import page', async ({ page }) => {
    await openCommandPalette(page);
    
    // Click on Orders import
    await clickPaletteButton(page, 'Импорт заказов');

    await expect(page.locator('text=Центр импорта и создания заказов')).toBeVisible({ timeout: 10000 });

    // Fill in a text request
    const textarea = page.locator('textarea').first();
    await textarea.fill(JSON.stringify({
      source: 'UI_UPLOAD',
      text: 'Brake pads for BMW X5',
      customer_name: 'Test Client E2E'
    }));

    // Submit - click import button
    await page.click('button:has-text("Импорт")');

    // Should show success message
    await expect(page.locator('text=Successfully added order')).toBeVisible({ timeout: 15000 });
  });

  test('File upload via Dropzone', async ({ page }) => {
    await openCommandPalette(page);
    await clickPaletteButton(page, 'Импорт заказов');

    await expect(page.locator('text=Перетащите файл запроса на закупку')).toBeVisible({ timeout: 10000 });

    // Create a test CSV file
    const csvContent = `name,quantity,oem,price
Brake Pads,2,BMW-12345,45.00
Oil Filter,1,BMW-67890,12.50`;

    // Use file input directly
    await page.evaluate((content) => {
      const file = new File([content], 'test-order.csv', { type: 'text/csv' });
      const dt = new DataTransfer();
      dt.items.add(file);
      const input = document.querySelector('input[type="file"]') as HTMLInputElement;
      if (input) input.files = dt.files;
    }, csvContent);

    // Should upload and import
    await expect(page.locator('text=Successfully imported order')).toBeVisible({ timeout: 20000 });
  });

  test('Kanban board loads and shows requests', async ({ page }) => {
    await openCommandPalette(page);
    await clickPaletteButton(page, 'Канбан-доска');

    await expect(page.locator('text=Интерактивный рабочий процесс')).toBeVisible({ timeout: 10000 });

    // Should have column headers for workflow states
    await expect(page.locator('[class*="kanban"], [class*="column"]').first()).toBeVisible({ timeout: 10000 });
  });

  test('Right panel shows request queue', async ({ page }) => {
    // Right panel should be visible by default
    await expect(page.locator('text=REQ-').first()).toBeVisible({ timeout: 15000 });
  });

  test('Audit view loads with completed orders', async ({ page }) => {
    await openCommandPalette(page);
    await clickPaletteButton(page, 'Аудит и логи');

    await expect(page.locator('text=Детальный аудит не загружен')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=выберите завершенный заказ')).toBeVisible();
  });

  test('Suppliers page loads', async ({ page }) => {
    await openCommandPalette(page);
    await clickPaletteButton(page, 'Каталог поставщиков');

    await expect(page.locator('text=Каталог поставщиков').first()).toBeVisible({ timeout: 10000 });
  });
});