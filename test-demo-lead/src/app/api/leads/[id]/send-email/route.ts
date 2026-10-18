import { NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabaseAdmin';
import { sendLeadEmail } from '@/lib/email/emailService';

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: leadId } = await params;
    const body = await request.json();
    const { to, subject, message } = body;

    if (!to || !subject || !message) {
      return NextResponse.json(
        { success: false, error: { code: 'INVALID_REQUEST', message: 'Missing email parameters' } },
        { status: 400 }
      );
    }

    // 1. Verify lead exists
    const { data: lead, error: leadError } = await supabaseAdmin
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

    const recipientEmail = to || lead.email;
    if (!recipientEmail) {
      return NextResponse.json(
        { success: false, error: { code: 'NO_PUBLIC_EMAIL', message: 'No email address available for this lead' } },
        { status: 400 }
      );
    }

    // 2. Send Email
    console.log(`[EMAIL] Attempting to send email for lead ${leadId} to ${recipientEmail}`);
    const emailResult = await sendLeadEmail(recipientEmail, subject, message);

    if (!emailResult.success) {
      return NextResponse.json(
        { success: false, error: { code: 'EMAIL_FAILED', message: emailResult.error } },
        { status: 500 }
      );
    }

    // 3. Update status to EMAIL_SENT
    await supabaseAdmin
      .from('leads')
      .update({ lead_status: 'EMAIL_SENT', status: 'EMAIL_SENT', updated_at: new Date().toISOString() })
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
