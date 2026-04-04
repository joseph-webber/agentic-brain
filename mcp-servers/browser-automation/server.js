#!/usr/bin/env node
/**
 * 🌐 BROWSER AUTOMATION MCP SERVER + NEO4J LEARNING
 * ==================================================
 * 
 * Playwright-powered browser automation for the Brain.
 * Accessibility-first design for Joseph's use.
 * 
 * Features:
 * - Persistent browser sessions (keeps login state)
 * - Anti-bot detection bypass
 * - Cookie/session management
 * - Screenshot & PDF capture
 * - Form filling with clipboard paste fallback
 * - Touch ID payment support
 * - **NEO4J LEARNING** - Remembers what works per site!
 * 
 * Neo4j Integration:
 * - Stores successful selector patterns per domain
 * - Records anti-bot bypass methods that worked
 * - Learns from failures and alternatives
 * - Builds knowledge graph of site behaviors
 * 
 * Author: Joseph Webber / Brain
 * Created: 2026-03-12
 */

import { chromium } from 'playwright';
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { createInterface } from 'readline';
import neo4j from 'neo4j-driver';

const __dirname = dirname(fileURLToPath(import.meta.url));
const BRAIN_DIR = join(process.env.HOME, 'brain');
const DATA_DIR = join(BRAIN_DIR, 'data', 'browser-automation');
const COOKIES_DIR = join(DATA_DIR, 'cookies');
const SCREENSHOTS_DIR = join(DATA_DIR, 'screenshots');

// Ensure directories exist
[DATA_DIR, COOKIES_DIR, SCREENSHOTS_DIR].forEach(dir => {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
});

// ═══════════════════════════════════════════════════════════════════════════════
// 🧠 NEO4J KNOWLEDGE GRAPH - Learn from every automation
// ═══════════════════════════════════════════════════════════════════════════════

class BrowserKnowledge {
  constructor() {
    this.driver = neo4j.driver(
      process.env.NEO4J_URI || 'bolt://localhost:7687',
      neo4j.auth.basic(
        process.env.NEO4J_USER || 'neo4j',
        process.env.NEO4J_PASSWORD || 'brain2026'
      )
    );
  }

  async recordSuccess(domain, action, method, selector, details = {}) {
    const session = this.driver.session();
    try {
      await session.run(`
        MERGE (site:Website {domain: $domain})
        MERGE (action:AutomationAction {name: $action, domain: $domain})
        MERGE (site)-[:HAS_ACTION]->(action)
        
        MERGE (method:WorkingMethod {
          domain: $domain,
          action: $action,
          method: $method,
          selector: $selector
        })
        ON CREATE SET 
          method.success_count = 1,
          method.created = datetime(),
          method.last_success = datetime(),
          method.details = $details
        ON MATCH SET 
          method.success_count = method.success_count + 1,
          method.last_success = datetime()
        
        MERGE (action)-[:WORKS_WITH]->(method)
      `, { domain, action, method, selector: selector || '', details: JSON.stringify(details) });
      
      console.error(`✅ Neo4j: Recorded success for ${domain}/${action}`);
    } catch (e) {
      console.error(`⚠️ Neo4j error: ${e.message}`);
    } finally {
      await session.close();
    }
  }

  async recordFailure(domain, action, method, selector, error) {
    const session = this.driver.session();
    try {
      await session.run(`
        MERGE (site:Website {domain: $domain})
        MERGE (failure:FailedMethod {
          domain: $domain,
          action: $action,
          method: $method,
          selector: $selector
        })
        ON CREATE SET 
          failure.fail_count = 1,
          failure.created = datetime(),
          failure.last_failure = datetime(),
          failure.last_error = $error
        ON MATCH SET 
          failure.fail_count = failure.fail_count + 1,
          failure.last_failure = datetime(),
          failure.last_error = $error
        
        MERGE (site)-[:HAS_FAILURE]->(failure)
      `, { domain, action, method, selector: selector || '', error });
      
      console.error(`❌ Neo4j: Recorded failure for ${domain}/${action}`);
    } catch (e) {
      console.error(`⚠️ Neo4j error: ${e.message}`);
    } finally {
      await session.close();
    }
  }

  async getBestMethod(domain, action) {
    const session = this.driver.session();
    try {
      const result = await session.run(`
        MATCH (m:WorkingMethod {domain: $domain, action: $action})
        WHERE NOT EXISTS {
          MATCH (f:FailedMethod {domain: $domain, action: $action, method: m.method, selector: m.selector})
          WHERE f.last_failure > m.last_success
        }
        RETURN m.method as method, m.selector as selector, m.success_count as successes, m.details as details
        ORDER BY m.success_count DESC, m.last_success DESC
        LIMIT 1
      `, { domain, action });
      
      if (result.records.length > 0) {
        const record = result.records[0];
        return {
          method: record.get('method'),
          selector: record.get('selector'),
          successes: record.get('successes').toNumber(),
          details: JSON.parse(record.get('details') || '{}')
        };
      }
      return null;
    } catch (e) {
      console.error(`⚠️ Neo4j query error: ${e.message}`);
      return null;
    } finally {
      await session.close();
    }
  }

  async getSiteKnowledge(domain) {
    const session = this.driver.session();
    try {
      const result = await session.run(`
        MATCH (site:Website {domain: $domain})
        OPTIONAL MATCH (site)-[:HAS_ACTION]->(action:AutomationAction)
        OPTIONAL MATCH (action)-[:WORKS_WITH]->(method:WorkingMethod)
        OPTIONAL MATCH (site)-[:HAS_FAILURE]->(failure:FailedMethod)
        OPTIONAL MATCH (site)-[:HAS_ISSUE]->(issue:SiteIssue)
        RETURN 
          site.domain as domain,
          collect(DISTINCT {action: action.name, method: method.method, selector: method.selector, successes: method.success_count}) as working_methods,
          collect(DISTINCT {action: failure.action, method: failure.method, error: failure.last_error}) as failures,
          collect(DISTINCT {issue: issue.issue, workaround: issue.workaround}) as known_issues
      `, { domain });
      
      if (result.records.length > 0) {
        const record = result.records[0];
        return {
          domain: record.get('domain'),
          working_methods: record.get('working_methods').filter(m => m.action),
          failures: record.get('failures').filter(f => f.action),
          known_issues: record.get('known_issues').filter(i => i.issue)
        };
      }
      return null;
    } catch (e) {
      console.error(`⚠️ Neo4j query error: ${e.message}`);
      return null;
    } finally {
      await session.close();
    }
  }

  async learnAntiBot(domain, method, success, details = {}) {
    const session = this.driver.session();
    try {
      await session.run(`
        MERGE (site:Website {domain: $domain})
        MERGE (antibot:AntiBotMethod {domain: $domain, method: $method})
        ON CREATE SET 
          antibot.attempts = 1,
          antibot.successes = CASE WHEN $success THEN 1 ELSE 0 END,
          antibot.created = datetime(),
          antibot.details = $details
        ON MATCH SET 
          antibot.attempts = antibot.attempts + 1,
          antibot.successes = antibot.successes + CASE WHEN $success THEN 1 ELSE 0 END,
          antibot.last_attempt = datetime()
        
        MERGE (site)-[:ANTI_BOT]->(antibot)
      `, { domain, method, success, details: JSON.stringify(details) });
    } catch (e) {
      console.error(`⚠️ Neo4j error: ${e.message}`);
    } finally {
      await session.close();
    }
  }

  async close() {
    await this.driver.close();
  }
}

const knowledge = new BrowserKnowledge();

// ═══════════════════════════════════════════════════════════════════════════════
// 🌐 BROWSER MANAGER - Handles persistent sessions
// ═══════════════════════════════════════════════════════════════════════════════

class BrowserManager {
  constructor() {
    this.browser = null;
    this.contexts = new Map(); // domain -> context
    this.pages = new Map();    // domain -> page
  }

  async launch(options = {}) {
    if (this.browser) return this.browser;
    
    this.browser = await chromium.launch({
      headless: options.headless ?? false,
      slowMo: options.slowMo ?? 100,
      args: [
        '--disable-blink-features=AutomationControlled',
        '--no-sandbox'
      ]
    });
    
    return this.browser;
  }

  async getContext(domain, options = {}) {
    if (this.contexts.has(domain)) {
      return this.contexts.get(domain);
    }

    await this.launch(options);
    
    const cookieFile = join(COOKIES_DIR, `${domain.replace(/\./g, '_')}.json`);
    let storageState = undefined;
    
    if (existsSync(cookieFile)) {
      storageState = cookieFile;
      console.log(`📂 Loading cookies for ${domain}`);
    }

    const context = await this.browser.newContext({
      viewport: { width: 1400, height: 900 },
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
      storageState,
      ...options.contextOptions
    });

    this.contexts.set(domain, context);
    return context;
  }

  async getPage(domain, options = {}) {
    if (this.pages.has(domain)) {
      return this.pages.get(domain);
    }

    const context = await this.getContext(domain, options);
    const page = await context.newPage();
    
    // Anti-bot: remove webdriver flag
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'webdriver', { get: () => false });
    });

    this.pages.set(domain, page);
    return page;
  }

  async saveCookies(domain) {
    const context = this.contexts.get(domain);
    if (!context) return false;

    const cookieFile = join(COOKIES_DIR, `${domain.replace(/\./g, '_')}.json`);
    const state = await context.storageState();
    writeFileSync(cookieFile, JSON.stringify(state, null, 2));
    console.log(`💾 Saved cookies for ${domain}`);
    return true;
  }

  async close() {
    // Save all cookies before closing
    for (const domain of this.contexts.keys()) {
      await this.saveCookies(domain);
    }
    
    if (this.browser) {
      await this.browser.close();
      this.browser = null;
      this.contexts.clear();
      this.pages.clear();
    }
  }
}

const browserManager = new BrowserManager();

// ═══════════════════════════════════════════════════════════════════════════════
// 🛠️ MCP TOOLS
// ═══════════════════════════════════════════════════════════════════════════════

const tools = {
  // Navigate to URL
  async browser_goto({ url, waitUntil = 'networkidle', timeout = 30000 }) {
    const domain = new URL(url).hostname;
    
    // Check Neo4j for site knowledge first
    const siteKnowledge = await knowledge.getSiteKnowledge(domain);
    if (siteKnowledge?.known_issues?.length > 0) {
      console.error(`⚠️ Known issues for ${domain}:`, siteKnowledge.known_issues);
    }
    
    const page = await browserManager.getPage(domain);
    
    try {
      await page.goto(url, { waitUntil, timeout });
      
      const title = await page.title();
      const content = await page.textContent('body').catch(() => '');
      
      // Record success
      await knowledge.recordSuccess(domain, 'navigate', 'playwright_goto', url);
      
      return {
        success: true,
        url: page.url(),
        title,
        content_preview: content.substring(0, 1000),
        site_knowledge: siteKnowledge
      };
    } catch (e) {
      await knowledge.recordFailure(domain, 'navigate', 'playwright_goto', url, e.message);
      throw e;
    }
  },

  // Get page content
  async browser_content({ selector = 'body', format = 'text' }) {
    const pages = Array.from(browserManager.pages.values());
    if (pages.length === 0) {
      return { error: 'No browser page open. Use browser_goto first.' };
    }
    
    const page = pages[pages.length - 1];
    
    if (format === 'html') {
      return { content: await page.innerHTML(selector) };
    } else {
      return { content: await page.textContent(selector) };
    }
  },

  // Click element
  async browser_click({ selector, text, index = 0, domain }) {
    const pages = Array.from(browserManager.pages.values());
    if (pages.length === 0) {
      return { error: 'No browser page open' };
    }
    
    const page = pages[pages.length - 1];
    const currentDomain = new URL(page.url()).hostname;
    
    // Check if we have a better method from Neo4j
    const bestMethod = await knowledge.getBestMethod(currentDomain, 'click');
    if (bestMethod && !selector && !text) {
      console.error(`🧠 Using learned method: ${bestMethod.method} with selector: ${bestMethod.selector}`);
      selector = bestMethod.selector;
    }
    
    let locator;
    if (text) {
      locator = page.getByText(text);
    } else {
      locator = page.locator(selector);
    }
    
    const count = await locator.count();
    if (count === 0) {
      await knowledge.recordFailure(currentDomain, 'click', 'locator', selector || text, 'Element not found');
      return { error: `No element found for: ${selector || text}` };
    }
    
    try {
      await locator.nth(index).click();
      await knowledge.recordSuccess(currentDomain, 'click', 'locator_click', selector || text);
      return { success: true, clicked: selector || text };
    } catch (e) {
      // Try SPACE key as fallback (works on Angular!)
      console.error(`⚠️ Click failed, trying SPACE key...`);
      try {
        await locator.nth(index).focus();
        await page.keyboard.press('Space');
        await knowledge.recordSuccess(currentDomain, 'click', 'space_key', selector || text);
        return { success: true, clicked: selector || text, method: 'space_key_fallback' };
      } catch (e2) {
        await knowledge.recordFailure(currentDomain, 'click', 'space_key', selector || text, e2.message);
        throw e;
      }
    }
  },

  // Fill form field (with clipboard paste fallback)
  async browser_fill({ selector, value, useClipboard = false }) {
    const pages = Array.from(browserManager.pages.values());
    if (pages.length === 0) {
      return { error: 'No browser page open' };
    }
    
    const page = pages[pages.length - 1];
    
    if (useClipboard) {
      // Use clipboard paste for hostile sites
      await page.locator(selector).click();
      await page.evaluate((val) => {
        navigator.clipboard.writeText(val);
      }, value);
      await page.keyboard.press('Meta+v');
    } else {
      await page.fill(selector, value);
    }
    
    return { success: true, filled: selector };
  },

  // Press key (SPACE works where click fails!)
  async browser_key({ key }) {
    const pages = Array.from(browserManager.pages.values());
    if (pages.length === 0) {
      return { error: 'No browser page open' };
    }
    
    const page = pages[pages.length - 1];
    await page.keyboard.press(key);
    return { success: true, pressed: key };
  },

  // Take screenshot
  async browser_screenshot({ name, fullPage = false }) {
    const pages = Array.from(browserManager.pages.values());
    if (pages.length === 0) {
      return { error: 'No browser page open' };
    }
    
    const page = pages[pages.length - 1];
    const filename = `${name || Date.now()}.png`;
    const path = join(SCREENSHOTS_DIR, filename);
    
    await page.screenshot({ path, fullPage });
    return { success: true, path };
  },

  // Download PDF (for shipping labels!)
  async browser_pdf({ name }) {
    const pages = Array.from(browserManager.pages.values());
    if (pages.length === 0) {
      return { error: 'No browser page open' };
    }
    
    const page = pages[pages.length - 1];
    const filename = `${name || Date.now()}.pdf`;
    const path = join(DATA_DIR, filename);
    
    await page.pdf({ path, format: 'A4' });
    return { success: true, path };
  },

  // Wait for element
  async browser_wait({ selector, state = 'visible', timeout = 10000 }) {
    const pages = Array.from(browserManager.pages.values());
    if (pages.length === 0) {
      return { error: 'No browser page open' };
    }
    
    const page = pages[pages.length - 1];
    await page.locator(selector).waitFor({ state, timeout });
    return { success: true, found: selector };
  },

  // Save cookies for domain
  async browser_save_session({ domain }) {
    const success = await browserManager.saveCookies(domain);
    return { success, domain };
  },

  // Close browser
  async browser_close() {
    await browserManager.close();
    return { success: true, message: 'Browser closed, cookies saved' };
  },

  // List saved sessions
  async browser_sessions() {
    const files = existsSync(COOKIES_DIR) 
      ? readdirSync(COOKIES_DIR).filter(f => f.endsWith('.json'))
      : [];
    
    return {
      sessions: files.map(f => f.replace('.json', '').replace(/_/g, '.'))
    };
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // 🏷️ AUSPOST SPECIFIC
  // ═══════════════════════════════════════════════════════════════════════════

  async auspost_ready_to_ship() {
    const url = 'https://auspost.com.au/mypost-business/shipping-and-tracking/orders/ready';
    const domain = 'auspost.com.au';
    
    const page = await browserManager.getPage(domain, { slowMo: 200 });
    
    // Navigate
    await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
    
    // Check for private browsing error
    const content = await page.textContent('body');
    if (content.includes('private browsing')) {
      return {
        error: 'Private browsing detected',
        suggestion: 'AusPost falsely detects private mode. Try: 1) Clear datadome cookie, 2) Wait and retry'
      };
    }
    
    // Get orders
    const orders = await page.$$eval('.order-item, [data-testid="order"]', els => 
      els.map(el => ({
        text: el.textContent.trim().substring(0, 200)
      }))
    ).catch(() => []);
    
    return {
      success: true,
      url: page.url(),
      title: await page.title(),
      orders,
      content_preview: content.substring(0, 1500)
    };
  },

  async auspost_complete_payment({ cardLast4 = '4107', useTouchId = true }) {
    const pages = Array.from(browserManager.pages.values());
    const page = pages.find(p => p.url().includes('auspost'));
    
    if (!page) {
      return { error: 'No AusPost page open. Use auspost_ready_to_ship first.' };
    }

    // Click pay/checkout button
    const payButton = page.locator('button:has-text("Pay"), button:has-text("Checkout"), button:has-text("Complete")');
    if (await payButton.count() > 0) {
      await payButton.first().click();
      await page.waitForTimeout(2000);
    }

    // If Touch ID requested, wait for user
    if (useTouchId) {
      return {
        status: 'awaiting_touch_id',
        message: 'Touch ID prompt should appear. Complete authentication manually.',
        next_step: 'After Touch ID, call auspost_download_label'
      };
    }

    return { success: true, message: 'Payment initiated' };
  },

  async auspost_download_label() {
    const pages = Array.from(browserManager.pages.values());
    const page = pages.find(p => p.url().includes('auspost'));
    
    if (!page) {
      return { error: 'No AusPost page open' };
    }

    // Look for download button
    const downloadBtn = page.locator('button:has-text("Download"), a:has-text("Download"), button:has-text("Print")');
    
    // Set up download handler
    const downloadPromise = page.waitForEvent('download', { timeout: 30000 });
    
    if (await downloadBtn.count() > 0) {
      await downloadBtn.first().click();
    }

    try {
      const download = await downloadPromise;
      const filename = `auspost_label_${Date.now()}.pdf`;
      const path = join(DATA_DIR, filename);
      await download.saveAs(path);
      
      return { success: true, label_path: path };
    } catch (e) {
      return { error: 'Download failed or timed out', details: e.message };
    }
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // 🧠 NEO4J KNOWLEDGE TOOLS
  // ═══════════════════════════════════════════════════════════════════════════

  async browser_knowledge({ domain }) {
    const siteKnowledge = await knowledge.getSiteKnowledge(domain);
    return siteKnowledge || { message: `No knowledge found for ${domain}` };
  },

  async browser_learn({ domain, action, method, selector, success, error }) {
    if (success) {
      await knowledge.recordSuccess(domain, action, method, selector);
      return { recorded: 'success', domain, action, method };
    } else {
      await knowledge.recordFailure(domain, action, method, selector, error || 'Unknown error');
      return { recorded: 'failure', domain, action, method };
    }
  },

  async browser_best_method({ domain, action }) {
    const best = await knowledge.getBestMethod(domain, action);
    return best || { message: `No learned method for ${domain}/${action}` };
  },

  async browser_antibot_learn({ domain, method, success, details }) {
    await knowledge.learnAntiBot(domain, method, success, details);
    return { recorded: true, domain, method, success };
  }
};

// ═══════════════════════════════════════════════════════════════════════════════
// 📡 MCP PROTOCOL HANDLER
// ═══════════════════════════════════════════════════════════════════════════════

const toolDefinitions = [
  {
    name: 'browser_goto',
    description: 'Navigate browser to URL. Maintains session/cookies per domain.',
    inputSchema: {
      type: 'object',
      properties: {
        url: { type: 'string', description: 'URL to navigate to' },
        waitUntil: { type: 'string', enum: ['load', 'domcontentloaded', 'networkidle'], default: 'networkidle' },
        timeout: { type: 'number', default: 30000 }
      },
      required: ['url']
    }
  },
  {
    name: 'browser_content',
    description: 'Get page content (text or HTML)',
    inputSchema: {
      type: 'object',
      properties: {
        selector: { type: 'string', default: 'body' },
        format: { type: 'string', enum: ['text', 'html'], default: 'text' }
      }
    }
  },
  {
    name: 'browser_click',
    description: 'Click element by selector or text',
    inputSchema: {
      type: 'object',
      properties: {
        selector: { type: 'string' },
        text: { type: 'string', description: 'Click element containing this text' },
        index: { type: 'number', default: 0 }
      }
    }
  },
  {
    name: 'browser_fill',
    description: 'Fill form field. Use useClipboard=true for hostile sites (Angular/React)',
    inputSchema: {
      type: 'object',
      properties: {
        selector: { type: 'string' },
        value: { type: 'string' },
        useClipboard: { type: 'boolean', default: false, description: 'Use clipboard paste for hostile sites' }
      },
      required: ['selector', 'value']
    }
  },
  {
    name: 'browser_key',
    description: 'Press keyboard key. SPACE works where click() fails on Angular sites!',
    inputSchema: {
      type: 'object',
      properties: {
        key: { type: 'string', description: 'Key to press: Space, Enter, Tab, Escape, etc.' }
      },
      required: ['key']
    }
  },
  {
    name: 'browser_screenshot',
    description: 'Take screenshot of current page',
    inputSchema: {
      type: 'object',
      properties: {
        name: { type: 'string' },
        fullPage: { type: 'boolean', default: false }
      }
    }
  },
  {
    name: 'browser_wait',
    description: 'Wait for element to appear',
    inputSchema: {
      type: 'object',
      properties: {
        selector: { type: 'string' },
        state: { type: 'string', enum: ['visible', 'hidden', 'attached'], default: 'visible' },
        timeout: { type: 'number', default: 10000 }
      },
      required: ['selector']
    }
  },
  {
    name: 'browser_save_session',
    description: 'Save cookies/session for domain (auto-saved on close too)',
    inputSchema: {
      type: 'object',
      properties: {
        domain: { type: 'string' }
      },
      required: ['domain']
    }
  },
  {
    name: 'browser_close',
    description: 'Close browser and save all sessions',
    inputSchema: { type: 'object', properties: {} }
  },
  {
    name: 'auspost_ready_to_ship',
    description: 'Navigate to AusPost Ready to Ship page with anti-bot handling',
    inputSchema: { type: 'object', properties: {} }
  },
  {
    name: 'auspost_complete_payment',
    description: 'Complete AusPost payment (supports Touch ID)',
    inputSchema: {
      type: 'object',
      properties: {
        cardLast4: { type: 'string', default: '4107' },
        useTouchId: { type: 'boolean', default: true }
      }
    }
  },
  {
    name: 'auspost_download_label',
    description: 'Download shipping label PDF after payment',
    inputSchema: { type: 'object', properties: {} }
  },
  // Neo4j Knowledge Tools
  {
    name: 'browser_knowledge',
    description: 'Get all learned knowledge about a domain (working methods, failures, known issues)',
    inputSchema: {
      type: 'object',
      properties: {
        domain: { type: 'string', description: 'Domain to query, e.g. auspost.com.au' }
      },
      required: ['domain']
    }
  },
  {
    name: 'browser_learn',
    description: 'Record a success or failure for a domain/action/method combination',
    inputSchema: {
      type: 'object',
      properties: {
        domain: { type: 'string' },
        action: { type: 'string', description: 'Action type: click, fill, navigate, etc.' },
        method: { type: 'string', description: 'Method used: locator_click, space_key, clipboard_paste, etc.' },
        selector: { type: 'string' },
        success: { type: 'boolean' },
        error: { type: 'string', description: 'Error message if success=false' }
      },
      required: ['domain', 'action', 'method', 'success']
    }
  },
  {
    name: 'browser_best_method',
    description: 'Get the best learned method for a domain/action combination',
    inputSchema: {
      type: 'object',
      properties: {
        domain: { type: 'string' },
        action: { type: 'string' }
      },
      required: ['domain', 'action']
    }
  },
  {
    name: 'browser_antibot_learn',
    description: 'Record anti-bot bypass attempt (success or failure)',
    inputSchema: {
      type: 'object',
      properties: {
        domain: { type: 'string' },
        method: { type: 'string', description: 'Anti-bot method: user_agent, slow_mo, webdriver_flag, etc.' },
        success: { type: 'boolean' },
        details: { type: 'object' }
      },
      required: ['domain', 'method', 'success']
    }
  }
];

// MCP message handler
async function handleMessage(message) {
  const { method, params, id } = message;

  switch (method) {
    case 'initialize':
      return {
        jsonrpc: '2.0',
        id,
        result: {
          protocolVersion: '2024-11-05',
          capabilities: { tools: {} },
          serverInfo: {
            name: 'brain-browser-automation',
            version: '1.0.0'
          }
        }
      };

    case 'tools/list':
      return {
        jsonrpc: '2.0',
        id,
        result: { tools: toolDefinitions }
      };

    case 'tools/call':
      const { name, arguments: args } = params;
      const tool = tools[name];
      
      if (!tool) {
        return {
          jsonrpc: '2.0',
          id,
          error: { code: -32601, message: `Unknown tool: ${name}` }
        };
      }

      try {
        const result = await tool(args || {});
        return {
          jsonrpc: '2.0',
          id,
          result: {
            content: [{ type: 'text', text: JSON.stringify(result, null, 2) }]
          }
        };
      } catch (error) {
        return {
          jsonrpc: '2.0',
          id,
          error: { code: -32000, message: error.message }
        };
      }

    default:
      return {
        jsonrpc: '2.0',
        id,
        error: { code: -32601, message: `Unknown method: ${method}` }
      };
  }
}

// Start server
const rl = createInterface({ input: process.stdin, output: process.stdout, terminal: false });

let buffer = '';

rl.on('line', async (line) => {
  buffer += line;
  
  try {
    const message = JSON.parse(buffer);
    buffer = '';
    
    const response = await handleMessage(message);
    console.log(JSON.stringify(response));
  } catch (e) {
    // Incomplete JSON, wait for more
    if (!(e instanceof SyntaxError)) {
      console.error('Error:', e);
      buffer = '';
    }
  }
});

// Cleanup on exit
process.on('SIGINT', async () => {
  await browserManager.close();
  process.exit(0);
});

console.error('🌐 Browser Automation MCP Server started');
