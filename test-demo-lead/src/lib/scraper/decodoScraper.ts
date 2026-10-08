export async function scrapeWithDecodo(url: string) {
  try {
    const apiKey = process.env.DECODO_API_KEY;
    if (!apiKey) {
      return { success: false, error: 'DECODO_API_KEY is missing' };
    }

    // Example Decodo API integration (adjust to actual Decodo API docs)
    // Using a generic Scraping API structure as placeholder
    const response = await fetch('https://api.decodo.com/v1/scrape', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({ url })
    });

    if (!response.ok) {
      return { success: false, error: `Decodo HTTP ${response.status}` };
    }

    const data = await response.json();
    
    if (!data.content) {
      return { success: false, error: 'Decodo returned empty content' };
    }

    return {
      success: true,
      title: data.title || 'Extracted Page',
      content: data.content.substring(0, 10000),
      http_status: response.status
    };
  } catch (error: any) {
    return { success: false, error: error.message };
  }
}
