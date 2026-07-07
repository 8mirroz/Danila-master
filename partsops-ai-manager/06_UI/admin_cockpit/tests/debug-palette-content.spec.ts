import { test, expect } from '@playwright/test';

test('debug palette content', async ({ page }) => {
  await page.goto('http://localhost:5176');
  await page.waitForLoadState('networkidle');
  
  // Open palette
  await page.evaluate(() => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }));
  });
  await page.waitForTimeout(1000);
  
  // Get all text content in the palette
  const paletteContent = await page.evaluate(() => {
    const overlay = document.querySelector('.fixed.inset-0.z-50');
    if (!overlay) return 'no overlay';
    return overlay.textContent || 'empty';
  });
  console.log('Palette content:', paletteContent);
  
  // Check for specific elements
  const buttons = await page.locator('button').all();
  console.log('Button count:', buttons.length);
  for (const btn of buttons.slice(0, 20)) {
    const text = await btn.textContent();
    if (text && text.trim()) console.log('Button:', text.trim().substring(0, 100));
  }
  
  await page.screenshot({ path: 'debug-palette-full.png', fullPage: true });
});