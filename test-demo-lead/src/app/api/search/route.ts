import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const { query } = await request.json();

    if (!query) {
      return NextResponse.json({ error: 'Query is required' }, { status: 400 });
    }

    const apiKey = process.env.SERPER_API_KEY;

    if (!apiKey) {
      console.error('Error: SERPER_API_KEY is missing in .env.local');
      return NextResponse.json({ error: 'Search API configuration is missing on the server' }, { status: 500 });
    }

    const url = 'https://google.serper.dev/search';
    
    console.log(`\n--- Serper API Log ---`);
    console.log(`Query: ${query}`);
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'X-API-KEY': apiKey,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ q: query })
    });
    
    const data = await response.json();

    console.log(`Response Status: ${response.status}`);
    console.log('-----------------------------\n');

    if (!response.ok) {
      return NextResponse.json({ error: data.message || 'Search failed' }, { status: 500 });
    }

    // Map Serper results to match our frontend format
    const results = data.organic ? data.organic.map((item: any) => ({
      title: item.title,
      link: item.link
    })) : [];

    return NextResponse.json({ results });
  } catch (error: any) {
    console.error('Search API Exception:', error);
    return NextResponse.json({ error: error.message || 'Failed to process search' }, { status: 500 });
  }
}
