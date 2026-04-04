const { chromium } = require('playwright');

(async () => {
  console.log('🚀 Launching Chromium browser...');
  
  const browser = await chromium.launch({
    headless: false,
    slowMo: 100
  });
  
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
  });
  
  // Anti-bot measures
  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
  });
  
  const page = await context.newPage();
  
  console.log('📍 Going to AusPost Ready to Ship...');
  await page.goto('https://auspost.com.au/mypost-business/shipping-and-tracking/orders/ready', {
    waitUntil: 'networkidle',
    timeout: 30000
  });
  
  console.log('📄 Page title:', await page.title());
  console.log('🔗 Current URL:', page.url());
  
  // Check page content
  const bodyText = await page.textContent('body');
  console.log('📝 Page preview:', bodyText.substring(0, 800));
  
  // Check for private browsing error
  if (bodyText.includes('private browsing') || bodyText.includes('Private browsing')) {
    console.log('❌ BLOCKED: Private browsing error detected');
  } else if (bodyText.includes('Sign in') || bodyText.includes('Log in')) {
    console.log('🔐 NEED LOGIN: Sign in required');
  } else if (bodyText.includes('Ready to ship') || bodyText.includes('ready')) {
    console.log('✅ SUCCESS: Ready to ship page loaded!');
  }
  
  console.log('\n🖥️ Browser window is open - check it!');
  
  // Wait for user to see
  await page.waitForTimeout(30000);
  
  await browser.close();
  console.log('Browser closed');
})();
