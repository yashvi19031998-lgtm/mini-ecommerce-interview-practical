import { NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabaseAdmin';

// GET /api/leads - Fetch all leads from Supabase
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const status = searchParams.get('status');
    const quality = searchParams.get('quality');
    const platform = searchParams.get('platform');

    let query = supabaseAdmin
      .from('leads')
      .select('*')
      .order('created_at', { ascending: false });

    if (status) query = query.eq('lead_status', status);
    if (quality) query = query.eq('lead_quality', quality);
    if (platform) query = query.eq('source_platform', platform);

    const { data, error } = await query;

    if (error) {
      return NextResponse.json(
        { success: false, error: error.message },
        { status: 500 }
      );
    }

    return NextResponse.json({ success: true, leads: data || [] });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 }
    );
  }
}

// PATCH /api/leads - Update lead status (approve/reject)
export async function PATCH(request: Request) {
  try {
    const { id, lead_status } = await request.json();

    if (!id || !lead_status) {
      return NextResponse.json(
        { success: false, error: 'id and lead_status are required' },
        { status: 400 }
      );
    }

    const { data, error } = await supabaseAdmin
      .from('leads')
      .update({ lead_status, updated_at: new Date().toISOString() })
      .eq('id', id)
      .select()
      .single();

    if (error) {
      return NextResponse.json({ success: false, error: error.message }, { status: 500 });
    }

    return NextResponse.json({ success: true, lead: data });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
