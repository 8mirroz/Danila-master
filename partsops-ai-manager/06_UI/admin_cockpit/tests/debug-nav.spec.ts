import { test, expect } from '@playwright/test';

test('debug palette navigation', async ({ page }) => {
  await page.goto('http://localhost:5176');
  await page.waitForLoadState('networkidle');
  
  // Open palette
  await page.evaluate(() => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }));
  });
  await page.waitForTimeout(1000);
  
  // Click on the Suppliers button in the palette
  const supplierBtn = page.locator('button:has-text("Каталог поставщиков G S")');
  console.log('Supplier button count:', await supplierBtn.count());
  
  if (await supplierBtn.count() > 0) {
    await supplierBtn.click();
    await page.waitForTimeout(2000);
    
    // Check what page we're on
    const url = page.url();
    console.log('URL after click:', url);
    
    const bodyText = await page.locator('body').textContent();
    console.log('Body has Каталог поставщиков:', bodyText?.includes('Каталог поставщиков'));
  }
  
  await page.screenshot({ path: 'debug-nav.png', fullPage: true });
});