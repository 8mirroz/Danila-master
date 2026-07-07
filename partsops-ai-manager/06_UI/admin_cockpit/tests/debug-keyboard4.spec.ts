import { test, expect } from '@playwright/test';

test('debug keyboard with console logs', async ({ page }) => {
  // Capture console logs
  page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
  page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));
  
  await page.goto('http://localhost:5176');
  await page.waitForLoadState('networkidle');
  
  // Check if the App component has the isCommandPaletteOpen state
  const initialState = await page.evaluate(() => {
    // Try to access the React component state through the root
    return document.body.innerHTML.length;
  });
  console.log('Initial body length:', initialState);
  
  // Try Meta+K
  await page.keyboard.press('Meta+K');
  await page.waitForTimeout(1000);
  
  const afterMeta = await page.evaluate(() => {
    const inputs = document.querySelectorAll('input');
    return Array.from(inputs).map(input => ({
      placeholder: input.placeholder,
      type: input.type,
      visible: input.offsetParent !== null
    }));
  });
  console.log('After Meta+K inputs:', afterMeta);
  
  // Try to manually set the state via window
  const manualOpen = await page.evaluate(() => {
    // Try to find the React component and trigger it
    const root = document.getElementById('root');
    if (!root) return 'no root';
    
    // Look for any component with isCommandPaletteOpen
    // In React 18, we can try to find the fiber
    return 'checking fiber...';
  });
  console.log('Manual open:', manualOpen);
  
  // Try dispatching event directly on window with all over and document
  await page.evaluate(() => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }));
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }));
  });
  await page.waitForTimeout(1000);
  
  const afterDispatch = await page.evaluate(() => {
    const inputs = document.querySelectorAll('input[placeholder*="команду"]');
    return {
      count: inputs.length,
      html: document.body.innerHTML.includes('Введите команду')
    };
  });
  console.log('After direct dispatch:', afterDispatch);
  
  await page.screenshot({ path: 'debug-palette3.png', fullPage: true });
});