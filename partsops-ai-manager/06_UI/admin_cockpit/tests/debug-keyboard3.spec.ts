import { test, expect } from '@playwright/test';

test('debug keyboard in browser 2', async ({ page }) => {
  await page.goto('http://localhost:5176');
  await page.waitForLoadState('networkidle');
  
  // Try using Playwright's keyboard API
  await page.keyboard.press('Meta+K');
  await page.waitForTimeout(1000);
  
  // Check if palette opened
  const html = await page.content();
  const paletteVisible = html.includes('Введите команду') || html.includes('Командная палитра');
  console.log('After Meta+K, palette visible:', paletteVisible);
  
  // Try Control+K
  await page.keyboard.press('Control+K');
  await page.waitForTimeout(1000);
  
  const html2 = await page.content();
  const paletteVisible2 = html2.includes('Введите команду') || html2.includes('Командная палитра');
  console.log('After Control+K, palette visible:', paletteVisible2);
  
  // Try directly setting state via React DevTools approach
  const stateCheck = await page.evaluate(() => {
    // Try to find React fiber and force update
    const root = document.getElementById('root');
    if (!root) return 'no root';
    
    // Look for the palette component
    const allInputs = document.querySelectorAll('input[placeholder*="команду"]');
    return {
      inputCount: allInputs.length,
      inputsVisible: Array.from(allInputs).map(el => ({
        visible: el.offsetParent !== null,
        placeholder: el.placeholder
      }))
    };
  });
  console.log('State check:', stateCheck);
  
  await page.screenshot({ path: 'debug-palette2.png', fullPage: true });
});