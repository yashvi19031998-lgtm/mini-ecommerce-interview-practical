import { NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';
import { sendLeadEmail } from '@/lib/email/emailService';

export async function POST(
  request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const leadId = params.id;
    const body = await request.json();
    const { to, subject, message } = body;

    if (!to || !subject || !message) {
      return NextResponse.json(
        { success: false, error: { code: 'INVALID_REQUEST', message: 'Missing email parameters' } },
        { status: 400 }
      );
    }

    // 1. Verify lead exists and is APPROVED
    const { data: lead, error: leadError } = await supabase
      .from('leads')
      .select('*')
      .eq('id', leadId)
      .single();

    if (leadError || !lead) {
      return NextResponse.json(
        { success: false, error: { code: 'DATABASE_FAILED', message: 'Lead not found' } },
        { status: 404 }
      );
    }

    if (lead.status !== 'APPROVED') {
      return NextResponse.json(
        { success: false, error: { code: 'EMAIL_FAILED', message: 'Lead must be APPROVED before sending email' } },
        { status: 400 }
      );
    }

    if (!lead.email) {
      return NextResponse.json(
        { success: false, error: { code: 'NO_PUBLIC_EMAIL', message: 'No email address available for this lead' } },
        { status: 400 }
      );
    }

    // 2. Send Email
    console.log(`[EMAIL] Attempting to send email for lead ${leadId}`);
    const emailResult = await sendLeadEmail(to, subject, message);

    if (!emailResult.success) {
      return NextResponse.json(
        { success: false, error: { code: 'EMAIL_FAILED', message: emailResult.error } },
        { status: 500 }
      );
    }

    // 3. Update status to EMAIL_SENT
    await supabase
      .from('leads')
      .update({ status: 'EMAIL_SENT', updated_at: new Date().toISOString() })
      .eq('id', leadId);

    console.log(`[EMAIL] Successfully processed email for lead ${leadId}`);
    
    return NextResponse.json({ 
      success: true, 
      message: 'Email sent successfully',
      testMode: emailResult.testMode 
    });

  } catch (error: any) {
    console.error('[EMAIL] Unexpected error:', error);
    return NextResponse.json(
      { success: false, error: { code: 'SERVER_ERROR', message: error.message } },
      { status: 500 }
    );
  }
}
