export interface CompanySettings {
  companyName: string;
  tagline: string;
  senderName: string;
  senderRole: string;
  email: string;
  phone: string;
  whatsapp: string;
  website: string;
  address: string;
  services: string[];
  signatureTemplate: string;
  defaultSubject: string;
  defaultMessage: string;
  delayBetweenEmailsMs: number;
}

export const DEFAULT_COMPANY_SETTINGS: CompanySettings = {
  companyName: "Sangeeta Infotech",
  tagline: "Engineering Intelligent Web & Mobile Solutions",
  senderName: "Business Development Team",
  senderRole: "Client Solutions Specialist",
  email: "sangeetainfotech19@gmail.com",
  phone: "+91 98765 43210",
  whatsapp: "+91 98765 43210",
  website: "https://sangeetainfotech.com",
  address: "Ahmedabad, Gujarat, India",
  services: [
    "Full-Stack Web Development (Next.js, React, Node.js, Python)",
    "Mobile App Development (Flutter, React Native, iOS, Android)",
    "AI & Workflow Automation",
    "Cloud Solutions & Dedicated Developers"
  ],
  signatureTemplate: `Warm regards,
{senderName} | {senderRole}
{companyName} — {tagline}
Email: {email}
Phone/WhatsApp: {phone}
Website: {website}
Location: {address}`,
  defaultSubject: "Software & Web Development Collaboration - Sangeeta Infotech",
  defaultMessage: `Hi {name},

I came across {company} and your project requirements.

At Sangeeta Infotech, we specialize in high-performance web applications, mobile apps, and custom software systems. We help companies scale their engineering capabilities and launch products faster with modern tech stacks.

Key areas we can help with:
• Full-stack Web & Mobile Development
• Custom CRM, SaaS & Cloud Solutions
• AI Integrations & Automated Systems

Could we schedule a quick 10-minute call this week to discuss how we can assist your project?`,
  delayBetweenEmailsMs: 1500
};

export function formatSignature(settings: CompanySettings): string {
  return settings.signatureTemplate
    .replace(/{senderName}/g, settings.senderName)
    .replace(/{senderRole}/g, settings.senderRole)
    .replace(/{companyName}/g, settings.companyName)
    .replace(/{tagline}/g, settings.tagline)
    .replace(/{email}/g, settings.email)
    .replace(/{phone}/g, settings.phone)
    .replace(/{whatsapp}/g, settings.whatsapp)
    .replace(/{website}/g, settings.website)
    .replace(/{address}/g, settings.address);
}

export function getStoredSettings(): CompanySettings {
  if (typeof window === 'undefined') return DEFAULT_COMPANY_SETTINGS;
  try {
    const raw = localStorage.getItem('sangeeta_infotech_settings');
    if (!raw) return DEFAULT_COMPANY_SETTINGS;
    return { ...DEFAULT_COMPANY_SETTINGS, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_COMPANY_SETTINGS;
  }
}

export function saveStoredSettings(settings: CompanySettings): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem('sangeeta_infotech_settings', JSON.stringify(settings));
}
