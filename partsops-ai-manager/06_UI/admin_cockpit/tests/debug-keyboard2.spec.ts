import { test, expect } from '@playwright/test';

test('debug keyboard in browser', async ({ page }) => {
  await page.goto('http://localhost:5176');
  await page.waitForLoadState('networkidle');
  
  // Check if the keydown listener is on window
  const hasListener = await page.evaluate(() => {
    // Try to trigger the handler directly
    const event = new KeyboardEvent('keydown', { key: 'k', metaKey: true });
    window.dispatchEvent(event);
    // Check if palette opened
    return document.body.innerHTML.includes('Введите команду') || document.body.innerHTML.includes('Командная палитра');
  });
  console.log('Direct dispatch result:', hasListener);
  
  // Check if the handler is attached
  const handlerInfo = await page.evaluate(() => {
    // Look at what's in the window for debugging
    return {
      hasGlobalEventListeners: true,
      innerHTMLSnippet: document.body.innerHTML.substring(0, 500)
    };
  });
  console.log('Handler info:', handlerInfo);
  
  await page.screenshot({ path: 'debug-palette.png', fullPage: true });
});