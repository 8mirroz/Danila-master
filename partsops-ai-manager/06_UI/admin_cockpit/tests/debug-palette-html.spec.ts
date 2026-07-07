import { test } from '@playwright/test';

test('debug palette html', async ({ page }) => {
  await page.goto('http://localhost:5176');
  await page.waitForLoadState('networkidle');
  
  // Open palette
  await page.evaluate(() => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }));
  });
  await page.waitForTimeout(1000);
  
  // Get all button texts in the palette
  const buttons = await page.locator('button').allTextContents();
  console.log('All buttons:', buttons);
  
  // Get the palette HTML
  const paletteHtml = await page.locator('div[class*="animate-slide-down"]').innerHTML();
  console.log('Palette HTML:', paletteHtml.substring(0, 5000));
  
  await page.screenshot({ path: 'debug-palette-full.png', fullPage: true });
});