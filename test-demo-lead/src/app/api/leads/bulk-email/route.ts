import { NextResponse } from 'next/server';
import { supabaseAdmin } from '@/lib/supabaseAdmin';
import { sendLeadEmail } from '@/lib/email/emailService';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { 
      leads, 
      subject, 
      message, 
      signature, 
      delayMs = 1500,
      isDirectTest = false 
    } = body;

    if (!Array.isArray(leads) || leads.length === 0) {
      return NextResponse.json(
        { success: false, error: 'No leads provided for bulk email' },
        { status: 400 }
      );
    }

    if (!subject || !message) {
      return NextResponse.json(
        { success: false, error: 'Subject and message are required' },
        { status: 400 }
      );
    }

    console.log(`[BULK_EMAIL] Starting bulk email dispatch to ${leads.length} recipients...`);

    const results: Array<{
      id: string;
      email: string;
      success: boolean;
      error?: string;
    }> = [];

    let sentCount = 0;
    let failedCount = 0;

    for (let i = 0; i < leads.length; i++) {
      const lead = leads[i];
      const leadId = lead.id;
      const recipientEmail = (lead.email || '').trim();

      if (!recipientEmail || recipientEmail === 'N/A' || !recipientEmail.includes('@')) {
        results.push({
          id: leadId,
          email: recipientEmail,
          success: false,
          error: 'Missing or invalid email address'
        });
        failedCount++;
        continue;
      }

      // Dynamic placeholder replacements
      const name = (lead.full_name || lead.company_name || 'there').trim();
      const company = (lead.company_name || 'your company').trim();
      const project = (lead.project_title || 'your software requirements').trim();

      const customizedSubject = subject
        .replace(/{name}/gi, name)
        .replace(/{company}/gi, company)
        .replace(/{project}/gi, project);

      let customizedMessage = message
        .replace(/{name}/gi, name)
        .replace(/{company}/gi, company)
        .replace(/{project}/gi, project);

      // Append official Sangeeta Infotech signature if provided
      if (signature && !customizedMessage.includes(signature.trim().slice(0, 20))) {
        customizedMessage = `${customizedMessage}\n\n---\n${signature.trim()}`;
      }

      console.log(`[BULK_EMAIL] Sending (${i + 1}/${leads.length}) to ${recipientEmail}...`);

      const emailResult = await sendLeadEmail(recipientEmail, customizedSubject, customizedMessage);

      if (emailResult.success) {
        sentCount++;
        results.push({
          id: leadId,
          email: recipientEmail,
          success: true
        });

        // Update lead status in Supabase
        if (!isDirectTest && leadId && leadId !== 'test-ping') {
          try {
            await supabaseAdmin
              .from('leads')
              .update({
                lead_status: 'EMAIL_SENT',
                status: 'EMAIL_SENT',
                updated_at: new Date().toISOString()
              })
              .eq('id', leadId);
          } catch (dbErr: any) {
            console.error(`[BULK_EMAIL] DB status update error for lead ${leadId}:`, dbErr);
          }
        }
      } else {
        failedCount++;
        results.push({
          id: leadId,
          email: recipientEmail,
          success: false,
          error: emailResult.error || 'Failed to deliver'
        });
      }

      // Courteous rate-limiting delay between sends for SMTP security
      if (i < leads.length - 1 && delayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
    }

    console.log(`[BULK_EMAIL] Batch completed: ${sentCount} sent, ${failedCount} failed.`);

    return NextResponse.json({
      success: true,
      total: leads.length,
      sent: sentCount,
      failed: failedCount,
      results
    });

  } catch (error: any) {
    console.error('[BULK_EMAIL] Unexpected exception:', error);
    return NextResponse.json(
      { success: false, error: error.message || 'Internal server error' },
      { status: 500 }
    );
  }
}
