import nodemailer from 'nodemailer';

export async function sendLeadEmail(to: string, subject: string, message: string) {
  // We use test/safe mode if no SMTP credentials exist
  const isTestMode = !process.env.SMTP_HOST;
  
  if (isTestMode) {
    console.log('[EMAIL] TEST MODE: Email not actually sent. Would have sent to:', to);
    console.log('[EMAIL] Subject:', subject);
    console.log('[EMAIL] Message:', message);
    return { success: true, testMode: true, message: 'Email logged in test mode' };
  }

  try {
    const transporter = nodemailer.createTransport({
      host: process.env.SMTP_HOST,
      port: Number(process.env.SMTP_PORT) || 587,
      secure: process.env.SMTP_SECURE === 'true', // true for 465, false for other ports
      auth: {
        user: process.env.SMTP_USER,
        pass: process.env.SMTP_PASS,
      },
    });

    const info = await transporter.sendMail({
      from: process.env.SMTP_FROM_EMAIL || '"Lead System" <noreply@example.com>',
      to,
      subject,
      text: message, // Plain text body
      // html: `<p>${message.replace(/\n/g, '<br>')}</p>`, // Optional HTML version
    });

    console.log('[EMAIL] Message sent: %s', info.messageId);
    return { success: true, messageId: info.messageId };
  } catch (error: any) {
    console.error('[EMAIL] Failed to send email:', error);
    return { success: false, error: error.message };
  }
}
