import { test, expect } from '@playwright/test';

test('debug keyboard', async ({ page }) => {
  await page.goto('http://localhost:5176');
  await page.waitForLoadState('networkidle');
  
  // Take a screenshot to see the initial state
  await page.screenshot({ path: 'debug-initial.png' });
  
  // Try pressing Meta+K
  await page.keyboard.press('Meta+K');
  await page.waitForTimeout(1000);
  
  // Check what's on the page
  const html = await page.content();
  console.log('HTML contains CommandPalette:', html.includes('Командная палитра') || html.includes('Введите команду'));
  
  // Try Control+K
  await page.keyboard.press('Control+K');
  await page.waitForTimeout(1000);
  
  const html2 = await page.content();
  console.log('After Control+K, HTML contains palette:', html2.includes('Командная палитра') || html2.includes('Введите команду'));
  
  // Try clicking something else first
  await page.click('body');
  await page.waitForTimeout(500);
  await page.keyboard.press('Meta+K');
  await page.waitForTimeout(1000);
  
  const html3 = await page.content();
  console.log('After click+Meta+K, HTML contains palette:', html3.includes('Командная палитра') || html3.includes('Введите команду'));
  
  await page.screenshot({ path: 'debug-final.png' });
});