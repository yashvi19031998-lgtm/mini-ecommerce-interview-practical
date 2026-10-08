import { scrapeDirectly } from './directScraper';
import { scrapeWithDecodo } from './decodoScraper';

export async function scrapeUrl(url: string) {
  console.log(`[SCRAPER] Trying direct extraction for ${url}`);
  
  const directResult = await scrapeDirectly(url);
  
  if (directResult.success) {
    console.log('[SCRAPER] Direct extraction successful');
    return {
      success: true,
      scraping_method: "AI_DIRECT",
      status: "SUCCESS",
      title: directResult.title,
      content: directResult.content,
      final_url: url,
      http_status: directResult.http_status
    };
  }

  console.log(`[SCRAPER] Direct extraction failed: ${directResult.error}. Trying Decodo fallback.`);
  const decodoResult = await scrapeWithDecodo(url);

  if (decodoResult.success) {
    console.log('[DECODO] Decodo extraction successful');
    return {
      success: true,
      scraping_method: "DECODO_FALLBACK",
      status: "PARTIAL",
      title: decodoResult.title,
      content: decodoResult.content,
      final_url: url,
      http_status: decodoResult.http_status
    };
  }

  console.log(`[DECODO] Decodo extraction failed: ${decodoResult.error}`);
  return {
    success: false,
    scraping_method: "FAILED",
    status: "FAILED",
    error: `Direct failed: ${directResult.error} | Decodo failed: ${decodoResult.error}`
  };
}
