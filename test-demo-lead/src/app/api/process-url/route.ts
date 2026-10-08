import { NextResponse } from 'next/server';
import { scrapeUrl } from '@/lib/scraper/scraperService';
import { extractLeadWithGemini } from '@/lib/gemini/geminiExtractor';
import { supabaseAdmin } from '@/lib/supabaseAdmin';

export async function POST(request: Request) {
  try {
    const { url, source_platform } = await request.json();

    if (!url) {
      return NextResponse.json(
        { success: false, error: { code: 'INVALID_URL', message: 'URL is required' } },
        { status: 400 }
      );
    }

    console.log(`[PROCESS_URL] URL received: ${url}`);

    // STEP 1: Scrape the page
    console.log(`[SCRAPER] Trying direct extraction...`);
    const scrapeResult = await scrapeUrl(url);

    if (!scrapeResult.success) {
      return NextResponse.json({
        success: false,
        scraping_method: 'FAILED',
        error: { code: 'SCRAPE_FAILED', message: scrapeResult.error }
      }, { status: 422 });
    }

    console.log(`[SCRAPER] Success via ${scrapeResult.scraping_method}`);

    // STEP 2: Extract lead data with Gemini
    console.log(`[GEMINI] Extracting lead from content...`);
    const geminiResult = await extractLeadWithGemini({
      url,
      source_platform: source_platform || 'unknown',
      content: scrapeResult.content || '',
      title: scrapeResult.title || ''
    });

    if (!geminiResult.success) {
      return NextResponse.json({
        success: false,
        error: { code: 'GEMINI_FAILED', message: geminiResult.error }
      }, { status: 500 });
    }

    const leadData = geminiResult.lead;
    console.log(`[LEAD] Extracted: ${leadData.project_title}, quality: ${leadData.lead_quality}`);

    // STEP 3: Duplicate check
    console.log(`[LEAD] Checking for duplicates...`);
    const { data: existing } = await supabaseAdmin
      .from('leads')
      .select('id')
      .eq('source_url', url)
      .maybeSingle();

    if (existing) {
      console.log(`[DUPLICATE] Lead already exists with id: ${existing.id}`);
      return NextResponse.json({
        success: false,
        error: { code: 'DUPLICATE_LEAD', message: 'This URL has already been processed' },
        duplicate: true,
        existing_lead_id: existing.id
      }, { status: 409 });
    }

    // STEP 4: Save to Supabase
    console.log(`[LEAD] Saving to database...`);
    const { data: savedLead, error: dbError } = await supabaseAdmin
      .from('leads')
      .insert([{
        ...leadData,
        source_url: url,
        source_platform: source_platform || leadData.source_platform || 'unknown',
        scraping_method: scrapeResult.scraping_method,
        scraping_status: scrapeResult.status,
        lead_status: 'NEW',
        updated_at: new Date().toISOString()
      }])
      .select()
      .single();

    if (dbError) {
      console.error('[LEAD] Database save failed:', dbError);
      return NextResponse.json({
        success: false,
        error: { code: 'DATABASE_FAILED', message: dbError.message }
      }, { status: 500 });
    }

    console.log(`[LEAD] Saved successfully with id: ${savedLead.id}`);

    return NextResponse.json({
      success: true,
      scraping_method: scrapeResult.scraping_method,
      scraping_status: scrapeResult.status,
      lead_saved: true,
      duplicate: false,
      lead: savedLead
    });

  } catch (error: any) {
    console.error('[PROCESS_URL] Unexpected error:', error);
    return NextResponse.json(
      { success: false, error: { code: 'SERVER_ERROR', message: error.message } },
      { status: 500 }
    );
  }
}
