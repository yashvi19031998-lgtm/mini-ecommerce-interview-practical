import * as cheerio from 'cheerio';

export async function scrapeDirectly(url: string) {
  try {
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      }
    });

    if (!response.ok) {
      return { success: false, error: `HTTP ${response.status}` };
    }

    const html = await response.text();
    const $ = cheerio.load(html);
    
    // Remove scripts, styles, etc.
    $('script, style, noscript, iframe, img, svg, video').remove();
    
    const content = $('body').text().replace(/\s+/g, ' ').trim();
    const title = $('title').text().trim();

    // If content is very short, it might be a JS-only page or blocked
    if (content.length < 200) {
      return { success: false, error: 'Content too short, possible JS-only page' };
    }

    return {
      success: true,
      title,
      content: content.substring(0, 10000), // Limit to 10k chars for LLM
      http_status: response.status
    };
  } catch (error: any) {
    return { success: false, error: error.message };
  }
}
